import asyncio
import json

from celery import Celery
import redis

from config import REDIS_URL
from pipeline import run_pipeline
from database import get_database
import crud

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
    db = get_database()
    owner_ids = await crud.list_owner_ids(db)
    if not owner_ids:
        print("[CeleryTask] No tenant fleets found.")
        return

    for owner_id in owner_ids:
        shipments = await crud.get_shipments(db, owner_id)
        payload = await run_pipeline(shipments)
        redis_client.setex(
            f"latest_risk_analysis:{owner_id}",
            3600,
            json.dumps(payload, default=str),
        )
        redis_client.publish(
            "risk_updates",
            json.dumps({"status": "updated", "owner_id": owner_id}),
        )
        print(f"[CeleryTask] Cached analysis for owner {owner_id}")


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def run_risk_analysis_pipeline(self):
    asyncio.run(_run_async_pipeline())
    return "Pipeline Complete"
