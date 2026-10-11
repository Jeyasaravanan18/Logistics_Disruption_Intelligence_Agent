"""
Celery Task Execution Suite.
Tests periodic background task execution, multi-tenant fleet looping,
pipeline invocation, and pub/sub notification dispatch.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import crud
from backend.celery_worker import _run_async_pipeline, run_risk_analysis_pipeline
from backend.models import Base
from backend.security import get_password_hash


@pytest.mark.anyio
async def test_celery_task_empty_tenants_graceful_exit():
    """Verify Celery task handles empty tenant fleets without crashing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    with patch("backend.celery_worker.get_sessionmaker", return_value=session_factory):
        # Should gracefully return without error
        await _run_async_pipeline()

    await engine.dispose()


@pytest.mark.anyio
async def test_celery_task_runs_pipeline_for_each_tenant():
    """Verify Celery task discovers tenant owners and executes risk pipeline."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        user1 = await crud.create_user(db, {
            "email": "tenant1@demo.com",
            "name": "Tenant 1",
            "hashed_password": get_password_hash("pass1"),
        })
        await crud.create_shipment(db, str(user1["id"]), {
            "shipment_id": "SH-T1",
            "origin": "Chennai",
            "destination": "Bangalore",
            "route_highway": "NH48",
            "latitude": 13.0827,
            "longitude": 80.2707,
            "delivery_priority": "HIGH",
        })

    fake_pipeline_result = {
        "pipeline": {
            "disruptions_collected": 1,
            "shipments_evaluated": 1,
            "risk_breakdown": {"HIGH": 1, "MEDIUM": 0, "LOW": 0, "SAFE": 0},
            "collector_reasoning": "Batch task",
        },
        "recommendations": [],
    }

    mock_redis = MagicMock()

    with patch("backend.celery_worker.get_sessionmaker", return_value=session_factory), \
         patch("backend.celery_worker.run_pipeline", new_callable=AsyncMock) as mock_pipe, \
         patch("backend.celery_worker.redis_client", mock_redis):
        mock_pipe.return_value = fake_pipeline_result

        await _run_async_pipeline()

        mock_pipe.assert_awaited_once()
        mock_redis.setex.assert_called_once()
        mock_redis.publish.assert_called_once_with(
            "risk_updates",
            f'{{"status": "updated", "owner_id": "{user1["id"]}"}}',
        )

    await engine.dispose()


def test_celery_sync_task_wrapper():
    """Verify synchronous celery wrapper invokes async loop and returns completion status."""
    with patch("backend.celery_worker._run_async_pipeline", new_callable=AsyncMock) as mock_async:
        result = run_risk_analysis_pipeline()
        assert result == "Pipeline Complete"
