"""
Unit and integration tests for PostgreSQL / SQLAlchemy 2.0 relational schema.
Validates tables, check constraints, foreign key cascades, and SQLite fallback.
"""

from datetime import datetime, timezone
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import crud
from database import init_db
from models import (
    Base,
    Disruption,
    PipelineRun,
    Recommendation,
    RefreshToken,
    RiskAssessment,
    Shipment,
    User,
    utcnow,
)


@pytest.fixture
async def test_session():
    """Provide an isolated in-memory SQLite async session for model testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.mark.anyio
async def test_user_and_token_cascade(test_session: AsyncSession):
    """Test user creation and cascade deletion of refresh tokens."""
    user = User(
        email="test_driver@fleet.com",
        name="Test Driver",
        hashed_password="hashed_pw_test",
        created_at=utcnow(),
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    token = RefreshToken(
        user_id=user.id,
        token_hash="hash_123456",
        expires_at=utcnow(),
        created_at=utcnow(),
    )
    test_session.add(token)
    await test_session.commit()

    # Verify token exists
    stmt = select(RefreshToken).where(RefreshToken.user_id == user.id)
    assert (await test_session.execute(stmt)).scalar_one_or_none() is not None

    # Delete user and verify cascade
    await test_session.delete(user)
    await test_session.commit()

    stmt = select(RefreshToken).where(RefreshToken.user_id == user.id)
    assert (await test_session.execute(stmt)).scalar_one_or_none() is None


@pytest.mark.anyio
async def test_shipment_unique_constraint(test_session: AsyncSession):
    """Test unique constraint on (owner_id, shipment_id)."""
    user = User(
        email="owner1@fleet.com",
        name="Fleet Owner",
        hashed_password="pw",
    )
    test_session.add(user)
    await test_session.commit()

    s1 = Shipment(
        owner_id=user.id,
        shipment_id="S101",
        origin="Delhi",
        destination="Mumbai",
        route_highway="NH48",
        latitude=28.61,
        longitude=77.20,
        delivery_priority="HIGH",
    )
    test_session.add(s1)
    await test_session.commit()

    # Attempt duplicate (owner_id, shipment_id)
    s2 = Shipment(
        owner_id=user.id,
        shipment_id="S101",
        origin="Jaipur",
        destination="Mumbai",
        route_highway="NH48",
        latitude=26.91,
        longitude=75.78,
        delivery_priority="LOW",
    )
    test_session.add(s2)
    with pytest.raises(IntegrityError):
        await test_session.commit()
    await test_session.rollback()


@pytest.mark.anyio
async def test_risk_assessment_check_constraints(test_session: AsyncSession):
    """Test CHECK (score >= 0) and level validation constraint."""
    user = User(email="owner2@fleet.com", name="Owner", hashed_password="pw")
    test_session.add(user)
    await test_session.commit()

    run = PipelineRun(owner_id=user.id)
    shipment = Shipment(
        owner_id=user.id,
        shipment_id="S201",
        origin="Chennai",
        destination="Madurai",
        route_highway="NH44",
        latitude=13.08,
        longitude=80.27,
        delivery_priority="MEDIUM",
    )
    test_session.add_all([run, shipment])
    await test_session.commit()

    # Negative score must violate check constraint
    invalid_assessment = RiskAssessment(
        run_id=run.id,
        shipment_id=shipment.id,
        score=-1.5,
        level="HIGH",
        reason="Invalid negative score",
    )
    test_session.add(invalid_assessment)
    with pytest.raises(IntegrityError):
        await test_session.commit()
    await test_session.rollback()


@pytest.mark.anyio
async def test_disruption_deduplication(test_session: AsyncSession):
    """Test that upserting disruptions deduplicates records by content_hash."""
    d1 = {
        "id": "W1",
        "type": "weather",
        "source": "OpenWeatherMap",
        "description": "Heavy rainfall in Mumbai",
        "subtype": "Rain",
        "location": "Mumbai",
        "lat": 19.07,
        "lon": 72.87,
        "radius_km": 150.0,
        "severity": "HIGH",
    }
    saved1 = await crud.upsert_disruptions(test_session, [d1])
    assert len(saved1) == 1

    # Inserting the exact same disruption must not duplicate in database
    saved2 = await crud.upsert_disruptions(test_session, [d1])
    assert len(saved2) == 1

    stmt = select(Disruption)
    all_disruptions = (await test_session.execute(stmt)).scalars().all()
    assert len(all_disruptions) == 1


@pytest.mark.anyio
async def test_seed_demo_shipments(test_session: AsyncSession):
    """Test loading demo shipments from shipments.json into SQL."""
    user = User(email="seed_user@fleet.com", name="Seed User", hashed_password="pw")
    test_session.add(user)
    await test_session.commit()

    count = await crud.seed_demo_shipments(test_session, user.id, force=True)
    assert count == 15  # 15 demo shipments in shipments.json

    shipments = await crud.get_shipments(test_session, user.id)
    assert len(shipments) == 15
    assert shipments[0]["shipment_id"] == "S101"
