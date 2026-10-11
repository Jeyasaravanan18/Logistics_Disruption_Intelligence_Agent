"""
Comprehensive tests for Phase 3: LangGraph stateful disruption intelligence workflow.
Verifies:
1. End-to-end graph compilation and execution
2. Per-node telemetry trace generation (plan, collect, analyze, score, recommend, persist_finish)
3. LLM failure fallback behavior (graceful deterministic execution with fallback_used flag)
4. Conditional branching (skipping recommendations for nominal SAFE/LOW shipments)
5. Bounded review loop (terminating within N <= 2 iterations without infinite cycles)
6. REST endpoint GET /pipeline-runs/{id}/trace
"""

from unittest.mock import AsyncMock, patch
import pytest
import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import crud
from database import get_db
from models import Base, User
from main import app
from routers.auth import get_current_user
from workflow.graph import compiled_workflow, execute_workflow
from workflow.state import WorkflowState


@pytest.fixture
def mock_operator():
    return {
        "id": "user_workflow_test",
        "email": "dispatch_lead@logistics.com",
        "name": "Dispatch Lead",
    }


@pytest.fixture
async def workflow_client_setup(mock_operator):
    """Set up isolated async DB session and authenticated HTTP client."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        user = User(
            id=mock_operator["id"],
            email=mock_operator["email"],
            name=mock_operator["name"],
            hashed_password="pw",
        )
        session.add(user)
        await session.commit()

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_current_user] = lambda: mock_operator
    app.dependency_overrides[get_db] = override_get_db

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client, session_factory

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.anyio
async def test_workflow_end_to_end_execution():
    """
    Test complete LangGraph workflow execution with deterministic tool outputs.
    Verifies state transitions, node execution order, and telemetry collection.
    """
    test_shipments = [
        {
            "shipment_id": "S101",
            "origin": "Chennai",
            "destination": "Bangalore",
            "route_highway": "NH44",
            "latitude": 13.08,
            "longitude": 80.27,
            "delivery_priority": "HIGH",
            "cargo_type": "Electronics",
        },
        {
            "shipment_id": "S102",
            "origin": "Mumbai",
            "destination": "Pune",
            "route_highway": "NH48",
            "latitude": 19.07,
            "longitude": 72.87,
            "delivery_priority": "LOW",
            "cargo_type": "FMCG",
        },
    ]

    result = await execute_workflow(shipments=test_shipments, owner_id="user_test_e2e")
    assert "pipeline" in result
    assert "recommendations" in result

    pipeline = result["pipeline"]
    assert pipeline["shipments_evaluated"] == 2
    assert "risk_breakdown" in pipeline
    assert "traces" in pipeline

    traces = pipeline["traces"]
    assert len(traces) >= 5  # At least plan, collect_weather, collect_news, analyze, score, persist_finish

    node_names = [t["node"] for t in traces]
    assert "plan" in node_names
    assert "collect_weather" in node_names
    assert "collect_news" in node_names
    assert "analyze" in node_names
    assert "score" in node_names
    assert "persist_finish" in node_names

    # Verify telemetry metadata fields
    for t in traces:
        assert "duration_ms" in t
        assert t["duration_ms"] >= 0.0
        assert "started_at" in t
        assert "output_summary" in t


@pytest.mark.anyio
async def test_llm_failure_graceful_fallback():
    """
    Simulate LLM outage/missing API keys:
    Workflow must fall back gracefully to deterministic rule-based analysis and rule templates,
    flagging fallback_used = True without crashing.
    """
    test_shipments = [
        {
            "shipment_id": "S201",
            "origin": "Chennai",
            "destination": "Madurai",
            "route_highway": "NH44",
            "latitude": 13.08,
            "longitude": 80.27,
            "delivery_priority": "HIGH",
        }
    ]

    with patch("workflow.nodes.generate_gemini_json", new_callable=AsyncMock) as mock_gemini:
        # Simulate LLM failure returning None
        mock_gemini.return_value = None

        result = await execute_workflow(shipments=test_shipments, owner_id="user_test_fallback")
        assert result["pipeline"]["shipments_evaluated"] == 1
        assert len(result["recommendations"]) == 1

        rec = result["recommendations"][0]
        assert "suggested_action" in rec
        assert "customer_message" in rec

        # Check telemetry flagged fallback
        traces = result["pipeline"]["traces"]
        plan_trace = next(t for t in traces if t["node"] == "plan")
        assert plan_trace["fallback_used"] is True
        assert plan_trace["used_llm"] is False


@pytest.mark.anyio
async def test_conditional_recommendation_bypass_on_safe_shipments():
    """
    Test conditional edge:
    When shipments are strictly SAFE / unaffected by disruptions,
    the recommendation LLM node is completely bypassed, routing directly to persist_finish.
    """
    # Shipments far away from any disruption in remote location
    safe_shipments = [
        {
            "shipment_id": "S_REMOTE",
            "origin": "Leh",
            "destination": "Kargil",
            "route_highway": "NH1D",
            "latitude": 34.15,
            "longitude": 77.57,
            "delivery_priority": "LOW",
        }
    ]

    with patch("workflow.nodes.fetch_weather_disruptions", new_callable=AsyncMock) as mock_w, \
         patch("workflow.nodes.fetch_news_disruptions", new_callable=AsyncMock) as mock_n:
        # Zero disruptions in this region
        mock_w.return_value = []
        mock_n.return_value = []

        result = await execute_workflow(shipments=safe_shipments, owner_id="user_test_safe")
        pipeline = result["pipeline"]
        assert pipeline["risk_breakdown"]["SAFE"] == 1
        assert pipeline["risk_breakdown"]["HIGH"] == 0
        assert pipeline["risk_breakdown"]["MEDIUM"] == 0

        traces = pipeline["traces"]
        node_names = [t["node"] for t in traces]
        # recommend node must NOT have executed
        assert "recommend" not in node_names
        assert "persist_finish" in node_names


@pytest.mark.anyio
async def test_bounded_review_loop_termination():
    """
    Test bounded review loop:
    When classifications have low confidence, the review conditional edge
    loops back at most N=2 times with refined queries and cleanly terminates.
    """
    shipment = [
        {
            "shipment_id": "S301",
            "origin": "Chennai",
            "destination": "Bangalore",
            "route_highway": "NH44",
            "latitude": 13.08,
            "longitude": 80.27,
            "delivery_priority": "HIGH",
        }
    ]

    # Force low confidence (< 0.6) on news items to trigger review loop
    low_conf_news = [
        {
            "id": "NEWS_AMBIGUOUS_1",
            "title": "Unclear disturbance reported near highway",
            "description": "Possible delay somewhere in south corridor",
            "location": "Chennai",
            "lat": 13.08,
            "lon": 80.27,
            "severity": "MEDIUM",
        }
    ]

    with patch("workflow.nodes.fetch_news_disruptions", new_callable=AsyncMock) as mock_n, \
         patch("workflow.nodes.generate_gemini_json", new_callable=AsyncMock) as mock_gemini:
        mock_n.return_value = low_conf_news
        # Return low confidence classification
        mock_gemini.return_value = {
            "id": "NEWS_AMBIGUOUS_1",
            "subtype": "Road Block",
            "severity": "MEDIUM",
            "location": "Chennai",
            "lat": 13.08,
            "lon": 80.27,
            "confidence": 0.35,  # Trigger review loop (< 0.60)
            "impact_duration_hours": 3,
            "summary": "Low confidence disturbance",
        }

        result = await execute_workflow(shipments=shipment, owner_id="user_test_review")
        traces = result["pipeline"]["traces"]

        # Count refine_query node occurrences
        refine_count = sum(1 for t in traces if t["node"] == "analyze")
        # Must terminate within bounded loop (1 initial + up to 2 review loops)
        assert refine_count <= 3
        assert result["pipeline"]["shipments_evaluated"] == 1


@pytest.mark.anyio
async def test_pipeline_trace_rest_endpoint(workflow_client_setup, mock_operator):
    """
    Test GET /pipeline-runs/{run_id}/trace REST contract:
    Executes a real workflow through the API and asserts that trace telemetry is persisted and returned.
    """
    client, session_factory = workflow_client_setup
    owner_id = mock_operator["id"]

    # 1. Create a shipment in the DB
    shipment_payload = {
        "shipment_id": "S_TRACE_01",
        "origin": "Chennai",
        "destination": "Madurai",
        "route_highway": "NH44",
        "latitude": 13.0827,
        "longitude": 80.2707,
        "delivery_priority": "HIGH",
    }
    await client.post("/shipments", json=shipment_payload)

    # 2. Trigger risk analysis execution
    run_resp = await client.post("/risk-analysis/run")
    assert run_resp.status_code == 200
    run_data = run_resp.json()
    run_id = run_data["pipeline"]["run_id"]
    assert run_id is not None

    # 3. Query telemetry trace endpoint GET /pipeline-runs/{run_id}/trace
    trace_resp = await client.get(f"/pipeline-runs/{run_id}/trace")
    assert trace_resp.status_code == 200
    trace_data = trace_resp.json()

    assert trace_data["run_id"] == run_id
    assert trace_data["count"] > 0
    assert len(trace_data["traces"]) > 0

    first_trace = trace_data["traces"][0]
    assert "node" in first_trace
    assert "duration_ms" in first_trace
    assert "output_summary" in first_trace
    assert "started_at" in first_trace
