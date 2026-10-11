"""
Contract tests verifying API schemas, status codes, and payload contracts.
Ensures the REST API contract remains stable across refactorings.
Uses httpx.AsyncClient with ASGITransport for modern async FastAPI testing.
"""

from unittest.mock import AsyncMock, patch
import pytest
import httpx

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from database import get_db
from models import Base
from main import app
from routers.auth import get_current_user


@pytest.fixture
def mock_user():
    return {
        "id": "user_123",
        "email": "operator@logistics.com",
        "name": "Fleet Operator",
    }


@pytest.fixture
async def async_client(mock_user):
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = override_get_db

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    app.dependency_overrides.clear()
    await test_engine.dispose()


@pytest.mark.anyio
async def test_root_contract(async_client):
    """GET / contract: status, database, version, endpoints."""
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "version" in data
    assert "endpoints" in data
    assert isinstance(data["endpoints"], list)


@pytest.mark.anyio
async def test_health_contract(async_client):
    """GET /health contract: status and component checks."""
    response = await async_client.get("/health")
    assert response.status_code in (200, 503)
    data = response.json()
    assert "status" in data
    assert "checks" in data
    assert "api" in data["checks"]


@pytest.mark.anyio
async def test_shipments_list_contract(async_client):
    """GET /shipments contract: count and shipments list."""
    with patch("crud.get_shipments", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = [
            {
                "shipment_id": "S101",
                "origin": "Chennai",
                "destination": "Madurai",
                "route_highway": "NH44",
                "latitude": 13.0827,
                "longitude": 80.2707,
                "delivery_priority": "HIGH",
                "cargo_type": "Pharmaceuticals",
                "weight_kg": 500,
            }
        ]
        response = await async_client.get("/shipments")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert "shipments" in data
        assert isinstance(data["shipments"], list)
        assert data["count"] == 1
        s = data["shipments"][0]
        assert s["shipment_id"] == "S101"
        assert s["delivery_priority"] == "HIGH"


@pytest.mark.anyio
async def test_shipments_create_validation_error(async_client):
    """POST /shipments contract: 422 Unprocessable Entity on invalid payload."""
    invalid_payload = {
        "shipment_id": "S_BAD",
        "origin": "X",  # min_length 2 violated
        "destination": "Y",
        "route_highway": "NH1",
        "latitude": 200.0,  # latitude > 90 violated
        "longitude": 80.0,
        "delivery_priority": "SUPER_HIGH",  # not in HIGH, MEDIUM, LOW
    }
    response = await async_client.post("/shipments", json=invalid_payload)
    assert response.status_code == 422


@pytest.mark.anyio
async def test_shipments_create_success_contract(async_client):
    """POST /shipments contract: 201 Created on valid payload."""
    payload = {
        "shipment_id": "S999",
        "origin": "Chennai",
        "destination": "Madurai",
        "route_highway": "NH44",
        "latitude": 13.0827,
        "longitude": 80.2707,
        "delivery_priority": "HIGH",
        "cargo_type": "Medical Supplies",
        "weight_kg": 250,
    }
    with patch("crud.create_shipment", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = {**payload, "owner_id": "user_123"}
        response = await async_client.post("/shipments", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["shipment_id"] == "S999"
        assert "owner_id" not in data  # owner_id must be stripped for privacy


@pytest.mark.anyio
async def test_disruptions_contract(async_client):
    """GET /disruptions contract: total, weather_count, news_count, disruptions list."""
    with patch("routers.disruptions.collect_disruptions", new_callable=AsyncMock) as mock_collect, \
         patch("routers.disruptions.analyze_disruptions", new_callable=AsyncMock) as mock_analyze:
        mock_collect.return_value = {
            "weather_count": 2,
            "news_count": 1,
            "reasoning": "Collected 3 signals",
            "disruptions": [{"id": "D1", "subtype": "Rain", "severity": "MEDIUM"}],
        }
        mock_analyze.return_value = [
            {"id": "D1", "subtype": "Rain", "severity": "MEDIUM", "impact_duration_hours": 4}
        ]
        response = await async_client.get("/disruptions")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "weather_count" in data
        assert "news_count" in data
        assert "disruptions" in data
        assert data["total"] == 1


@pytest.mark.anyio
async def test_risk_analysis_contract(async_client):
    """GET /risk-analysis contract: pipeline summary and recommendations list."""
    fake_result = {
        "pipeline": {
            "disruptions_collected": 3,
            "shipments_evaluated": 2,
            "risk_breakdown": {"HIGH": 1, "MEDIUM": 0, "LOW": 0, "SAFE": 1},
            "collector_reasoning": "Deduplicated 3 signals",
        },
        "recommendations": [
            {
                "shipment_id": "S101",
                "risk_level": "HIGH",
                "risk_score": 6.5,
                "suggested_action": "Reroute via alternate",
                "alternate_route": "NH48",
                "estimated_delay_hours": 6,
                "customer_message": "Notice of delay",
            }
        ],
    }
    with patch("crud.get_shipments", new_callable=AsyncMock) as mock_ship, \
         patch("routers.risk_analysis.run_pipeline", new_callable=AsyncMock) as mock_run:
        mock_ship.return_value = [{"shipment_id": "S101"}]
        mock_run.return_value = fake_result
        from routers.risk_analysis import _MEM_CACHE
        _MEM_CACHE.clear()

        response = await async_client.get("/risk-analysis")
        assert response.status_code == 200
        data = response.json()
        assert "pipeline" in data
        assert "recommendations" in data
        assert data["pipeline"]["shipments_evaluated"] == 2
        assert len(data["recommendations"]) == 1
        assert data["recommendations"][0]["shipment_id"] == "S101"
