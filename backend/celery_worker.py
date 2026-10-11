"""
Celery worker for periodic asynchronous risk analysis across tenant fleets.
Uses SQLAlchemy 2.0 AsyncSession and Redis for pub/sub notifications.
"""

import asyncio
import json

from celery import Celery
import redis

from config import REDIS_URL
import crud
from database import get_sessionmaker, init_db
from pipeline import run_pipeline

celery_app = Celery("logistics_tasks", broker=REDIS_URL, backend=REDIS_URL)
celery_app.conf.beat_schedule = {
    "run-ai-pipeline-every-15-mins": {
        "task": "celery_worker.run_risk_analysis_pipeline",
        "schedule": 900.0,
    },
}
celery_app.conf.timezone = "UTC"

redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)


async def _run_async_pipeline() -> None:
    print("[CeleryTask] Starting background AI pipeline...")
    try:
        session_factory = get_sessionmaker()
    except Exception:
        await init_db()
        session_factory = get_sessionmaker()

    async with session_factory() as db:
        owner_ids = await crud.list_owner_ids(db)
        if not owner_ids:
            print("[CeleryTask] No tenant fleets found.")
            return

        for owner_id in owner_ids:
            shipments = await crud.get_shipments(db, owner_id)
            payload = await run_pipeline(shipments, db=db, owner_id=owner_id)
            try:
                redis_client.setex(
                    f"latest_risk_analysis:{owner_id}",
                    3600,
                    json.dumps(payload, default=str),
                )
                redis_client.publish(
                    "risk_updates",
                    json.dumps({"status": "updated", "owner_id": owner_id}),
                )
            except Exception as re:
                print(f"[CeleryTask] Redis cache update notice: {re}")
            print(f"[CeleryTask] Cached analysis for owner {owner_id}")


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def run_risk_analysis_pipeline(self=None):
    asyncio.run(_run_async_pipeline())
    return "Pipeline Complete"
