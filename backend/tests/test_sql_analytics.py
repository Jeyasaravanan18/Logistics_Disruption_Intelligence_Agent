"""
Unit and integration tests for Phase 2 Relational SQL Analytics features.
Tests verify exact hand-computed values for:
1. Dashboard KPIs (aggregate + FILTER)
2. Risk trend per shipment (LAG window function)
3. Corridor exposure ranking (join + GROUP BY + HAVING + composite ORDER BY)
4. Disruption timeline (guaranteed zero-filled days)
5. Keyset pagination on shipments
"""

from datetime import datetime, timedelta, timezone
import pytest
import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import crud
from database import get_db
from models import (
    Base,
    Disruption,
    PipelineRun,
    RiskAssessment,
    Shipment,
    User,
    utcnow,
)
from main import app
from routers.auth import get_current_user


@pytest.fixture
def mock_owner():
    return {
        "id": "owner_sql_test",
        "email": "analytics_lead@logistics.com",
        "name": "Analytics Lead",
    }


@pytest.fixture
async def test_db_setup(mock_owner):
    """Set up an isolated in-memory SQLite database and test user."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    # Seed the test user into DB
    async with session_factory() as session:
        user = User(
            id=mock_owner["id"],
            email=mock_owner["email"],
            name=mock_owner["name"],
            hashed_password="test_password_hash",
        )
        session.add(user)
        await session.commit()

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_current_user] = lambda: mock_owner
    app.dependency_overrides[get_db] = override_get_db

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client, session_factory

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.anyio
async def test_dashboard_kpis_aggregate_and_filter(test_db_setup, mock_owner):
    """
    Test Dashboard KPIs aggregate + FILTER query against hand-computed values:
    Assessments:
      - S1, D1: score 7.0, level HIGH
      - S2, D1: score 8.0, level HIGH
      - S3, D2: score 3.0, level MEDIUM
      - S1, D2: score 0.0, level SAFE
    Expected:
      total = 4
      HIGH = 2, MEDIUM = 1, LOW = 0, SAFE = 1
      avg_score = 4.50
      max_score = 8.00
    """
    client, session_factory = test_db_setup
    owner_id = mock_owner["id"]

    async with session_factory() as db:
        run = PipelineRun(owner_id=owner_id, status="COMPLETED")
        db.add(run)
        await db.flush()

        s1 = Shipment(owner_id=owner_id, shipment_id="S1", origin="A", destination="B", route_highway="NH44", latitude=13.0, longitude=80.0, delivery_priority="HIGH")
        s2 = Shipment(owner_id=owner_id, shipment_id="S2", origin="C", destination="D", route_highway="NH44", latitude=12.0, longitude=79.0, delivery_priority="MEDIUM")
        s3 = Shipment(owner_id=owner_id, shipment_id="S3", origin="E", destination="F", route_highway="NH48", latitude=11.0, longitude=78.0, delivery_priority="LOW")
        d1 = Disruption(source="weather", type="weather", title="Storm", subtype="Rain", location="Chennai", lat=13.0, lon=80.0, severity="HIGH", content_hash="hash_d1")
        d2 = Disruption(source="news", type="news", title="Protest", subtype="Strike", location="Vellore", lat=12.0, lon=79.0, severity="MEDIUM", content_hash="hash_d2")
        db.add_all([s1, s2, s3, d1, d2])
        await db.flush()

        a1 = RiskAssessment(run_id=run.id, shipment_id=s1.id, disruption_id=d1.id, score=7.0, level="HIGH", distance_km=10.0, reason="High storm risk")
        a2 = RiskAssessment(run_id=run.id, shipment_id=s2.id, disruption_id=d1.id, score=8.0, level="HIGH", distance_km=15.0, reason="Severe storm on corridor")
        a3 = RiskAssessment(run_id=run.id, shipment_id=s3.id, disruption_id=d2.id, score=3.0, level="MEDIUM", distance_km=50.0, reason="Moderate strike impact")
        a4 = RiskAssessment(run_id=run.id, shipment_id=s1.id, disruption_id=d2.id, score=0.0, level="SAFE", distance_km=200.0, reason="Far outside disruption zone")
        db.add_all([a1, a2, a3, a4])
        await db.commit()

    resp = await client.get("/analytics/kpis")
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_assessments"] == 4
    assert data["counts_by_level"]["HIGH"] == 2
    assert data["counts_by_level"]["MEDIUM"] == 1
    assert data["counts_by_level"]["LOW"] == 0
    assert data["counts_by_level"]["SAFE"] == 1
    assert data["avg_risk_score"] == 4.5
    assert data["max_risk_score"] == 8.0


@pytest.mark.anyio
async def test_risk_trends_lag_window_function(test_db_setup, mock_owner):
    """
    Test Risk Trends using SQL LAG() over sequential runs:
    Run 1 (earlier):
      - S1: score 2.0 (LOW)
      - S2: score 7.0 (HIGH)
    Run 2 (later):
      - S1: score 6.5 (HIGH) -> delta +4.5, trend INCREASED
      - S2: score 3.0 (MEDIUM) -> delta -4.0, trend DECREASED
      - S3: score 4.0 (MEDIUM) -> prev None, trend NEW
    """
    client, session_factory = test_db_setup
    owner_id = mock_owner["id"]

    t0 = utcnow() - timedelta(hours=2)
    t1 = utcnow()

    async with session_factory() as db:
        run1 = PipelineRun(owner_id=owner_id, started_at=t0, status="COMPLETED")
        run2 = PipelineRun(owner_id=owner_id, started_at=t1, status="COMPLETED")
        db.add_all([run1, run2])
        await db.flush()

        s1 = Shipment(owner_id=owner_id, shipment_id="S101", origin="A", destination="B", route_highway="NH44", latitude=13.0, longitude=80.0, delivery_priority="HIGH")
        s2 = Shipment(owner_id=owner_id, shipment_id="S102", origin="C", destination="D", route_highway="NH48", latitude=12.0, longitude=79.0, delivery_priority="MEDIUM")
        s3 = Shipment(owner_id=owner_id, shipment_id="S103", origin="E", destination="F", route_highway="NH16", latitude=11.0, longitude=78.0, delivery_priority="LOW")
        d1 = Disruption(source="weather", type="weather", title="Disruption 1", subtype="Rain", location="Chennai", lat=13.0, lon=80.0, severity="MEDIUM", content_hash="hash_w1")
        db.add_all([s1, s2, s3, d1])
        await db.flush()

        # Run 1 assessments
        r1_a1 = RiskAssessment(run_id=run1.id, shipment_id=s1.id, disruption_id=d1.id, score=2.0, level="LOW", distance_km=50.0, reason="Low rain risk")
        r1_a2 = RiskAssessment(run_id=run1.id, shipment_id=s2.id, disruption_id=d1.id, score=7.0, level="HIGH", distance_km=10.0, reason="High flood risk")

        # Run 2 assessments
        r2_a1 = RiskAssessment(run_id=run2.id, shipment_id=s1.id, disruption_id=d1.id, score=6.5, level="HIGH", distance_km=12.0, reason="Increased rain storm")
        r2_a2 = RiskAssessment(run_id=run2.id, shipment_id=s2.id, disruption_id=d1.id, score=3.0, level="MEDIUM", distance_km=45.0, reason="Clearing weather")
        r2_a3 = RiskAssessment(run_id=run2.id, shipment_id=s3.id, disruption_id=d1.id, score=4.0, level="MEDIUM", distance_km=30.0, reason="New assessment")

        db.add_all([r1_a1, r1_a2, r2_a1, r2_a2, r2_a3])
        await db.commit()

    resp = await client.get("/analytics/risk-trends")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 3

    trends_map = {t["shipment_id"]: t for t in data["trends"]}

    # Verify S101
    assert trends_map["S101"]["current_score"] == 6.5
    assert trends_map["S101"]["previous_score"] == 2.0
    assert trends_map["S101"]["score_delta"] == 4.5
    assert trends_map["S101"]["trend"] == "INCREASED"

    # Verify S102
    assert trends_map["S102"]["current_score"] == 3.0
    assert trends_map["S102"]["previous_score"] == 7.0
    assert trends_map["S102"]["score_delta"] == -4.0
    assert trends_map["S102"]["trend"] == "DECREASED"

    # Verify S103 (newly introduced in Run 2)
    assert trends_map["S103"]["current_score"] == 4.0
    assert trends_map["S103"]["previous_score"] is None
    assert trends_map["S103"]["score_delta"] is None
    assert trends_map["S103"]["trend"] == "NEW"


@pytest.mark.anyio
async def test_corridor_exposure_ranking(test_db_setup, mock_owner):
    """
    Test Corridor Exposure ranking (3-way join, GROUP BY, HAVING, composite ORDER BY):
    Corridor NH44:
      - S1 (NH44), D1: score 8.0, level HIGH
      - S2 (NH44), D2: score 4.0, level MEDIUM
      -> avg_risk = 6.00, high_count = 1, unique_disruptions = 2
    Corridor NH48:
      - S3 (NH48), D1: score 2.0, level LOW
      -> avg_risk = 2.00, high_count = 0, unique_disruptions = 1
    Expected ranking: NH44 (avg 6.0) first, NH48 (avg 2.0) second.
    """
    client, session_factory = test_db_setup
    owner_id = mock_owner["id"]

    async with session_factory() as db:
        run = PipelineRun(owner_id=owner_id, status="COMPLETED")
        db.add(run)
        await db.flush()

        s1 = Shipment(owner_id=owner_id, shipment_id="S1", origin="A", destination="B", route_highway="NH44", latitude=13.0, longitude=80.0, delivery_priority="HIGH")
        s2 = Shipment(owner_id=owner_id, shipment_id="S2", origin="C", destination="D", route_highway="NH44", latitude=12.0, longitude=79.0, delivery_priority="MEDIUM")
        s3 = Shipment(owner_id=owner_id, shipment_id="S3", origin="E", destination="F", route_highway="NH48", latitude=11.0, longitude=78.0, delivery_priority="LOW")
        d1 = Disruption(source="weather", type="weather", title="D1", subtype="Fog", location="Chennai", lat=13.0, lon=80.0, severity="HIGH", content_hash="hash_cor_1")
        d2 = Disruption(source="news", type="news", title="D2", subtype="Strike", location="Bangalore", lat=12.0, lon=79.0, severity="MEDIUM", content_hash="hash_cor_2")
        db.add_all([s1, s2, s3, d1, d2])
        await db.flush()

        a1 = RiskAssessment(run_id=run.id, shipment_id=s1.id, disruption_id=d1.id, score=8.0, level="HIGH", distance_km=5.0, reason="Dense fog hazard")
        a2 = RiskAssessment(run_id=run.id, shipment_id=s2.id, disruption_id=d2.id, score=4.0, level="MEDIUM", distance_km=25.0, reason="Strike detour")
        a3 = RiskAssessment(run_id=run.id, shipment_id=s3.id, disruption_id=d1.id, score=2.0, level="LOW", distance_km=80.0, reason="Minor fog delay")
        db.add_all([a1, a2, a3])
        await db.commit()

    resp = await client.get("/analytics/corridors")
    assert resp.status_code == 200
    corridors = resp.json()["corridors"]

    assert len(corridors) == 2
    assert corridors[0]["corridor"] == "NH44"
    assert corridors[0]["avg_risk_score"] == 6.0
    assert corridors[0]["active_shipments"] == 2
    assert corridors[0]["high_risk_count"] == 1

    assert corridors[1]["corridor"] == "NH48"
    assert corridors[1]["avg_risk_score"] == 2.0
    assert corridors[1]["active_shipments"] == 1
    assert corridors[1]["high_risk_count"] == 0


@pytest.mark.anyio
async def test_disruption_timeline_zero_filled(test_db_setup, mock_owner):
    """
    Test Disruption Timeline query:
    Validates that all days in requested window are returned, including days with zero events.
    """
    client, session_factory = test_db_setup

    today = utcnow().date()
    two_days_ago = today - timedelta(days=2)

    async with session_factory() as db:
        # Today: 1 HIGH event
        d_today = Disruption(
            source="weather",
            type="weather",
            title="Today Storm",
            subtype="Rain",
            location="Chennai",
            lat=13.0,
            lon=80.0,
            severity="HIGH",
            valid_from=datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc),
            content_hash="hash_time_today",
        )
        # 2 days ago: 1 LOW event
        d_prev = Disruption(
            source="news",
            type="news",
            title="Past Incident",
            subtype="Flood",
            location="Madurai",
            lat=12.0,
            lon=79.0,
            severity="LOW",
            valid_from=datetime.combine(two_days_ago, datetime.min.time(), tzinfo=timezone.utc),
            content_hash="hash_time_prev",
        )
        # Note: 1 day ago has NO disruptions
        db.add_all([d_today, d_prev])
        await db.commit()

    resp = await client.get("/analytics/timeline?days=3")
    assert resp.status_code == 200
    data = resp.json()

    assert data["days_analyzed"] == 3
    timeline = data["timeline"]
    assert len(timeline) == 3

    # The middle day (1 day ago) must be present with zero counts
    middle_day_entry = timeline[1]
    assert middle_day_entry["total_disruptions"] == 0
    assert middle_day_entry["high_count"] == 0
    assert middle_day_entry["medium_count"] == 0
    assert middle_day_entry["low_count"] == 0


@pytest.mark.anyio
async def test_keyset_pagination_ordering(test_db_setup, mock_owner):
    """
    Test Keyset pagination on GET /shipments:
    Validates cursor-based seek pagination with deterministic ordering.
    """
    client, session_factory = test_db_setup
    owner_id = mock_owner["id"]

    # Insert 5 shipments: S101, S102, S103, S104, S105
    async with session_factory() as db:
        for sid in ["S101", "S102", "S103", "S104", "S105"]:
            shipment = Shipment(
                owner_id=owner_id,
                shipment_id=sid,
                origin="Chennai",
                destination="Bangalore",
                route_highway="NH44",
                latitude=13.0,
                longitude=80.0,
                delivery_priority="MEDIUM",
            )
            db.add(shipment)
        await db.commit()

    # Page 1: limit 2, cursor None -> S101, S102, next_cursor S102
    resp1 = await client.get("/shipments?limit=2&cursor=")
    assert resp1.status_code == 200
    d1 = resp1.json()
    assert d1["count"] == 2
    assert [s["shipment_id"] for s in d1["shipments"]] == ["S101", "S102"]
    assert d1["next_cursor"] == "S102"

    # Page 2: limit 2, cursor S102 -> S103, S104, next_cursor S104
    resp2 = await client.get("/shipments?limit=2&cursor=S102")
    assert resp2.status_code == 200
    d2 = resp2.json()
    assert d2["count"] == 2
    assert [s["shipment_id"] for s in d2["shipments"]] == ["S103", "S104"]
    assert d2["next_cursor"] == "S104"

    # Page 3: limit 2, cursor S104 -> S105, next_cursor None
    resp3 = await client.get("/shipments?limit=2&cursor=S104")
    assert resp3.status_code == 200
    d3 = resp3.json()
    assert d3["count"] == 1
    assert [s["shipment_id"] for s in d3["shipments"]] == ["S105"]
    assert d3["next_cursor"] is None
