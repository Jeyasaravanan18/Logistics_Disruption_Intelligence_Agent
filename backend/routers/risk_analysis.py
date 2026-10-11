"""
Risk analysis router: execute 4-agent pipeline or retrieve cached risk matrix.
Uses SQLAlchemy 2.0 AsyncSession for shipment retrieval and Redis for caching and pub/sub.
"""

import json
import os
import time

from fastapi import APIRouter, Depends
import redis
from sqlalchemy.ext.asyncio import AsyncSession

import crud
from database import get_db
from pipeline import run_pipeline
from routers.auth import get_current_user, owner_id_from_user

router = APIRouter()
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")

# In-memory cache fallback when Redis is offline
_MEM_CACHE: dict[str, tuple[float, dict]] = {}
CACHE_TTL = 120.0  # 2 minutes cache


def _cache_key(owner_id: str) -> str:
    return f"latest_risk_analysis:{owner_id}"


def _redis():
    return redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=1)


@router.get("/risk-analysis")
async def get_risk_analysis(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    owner_id = owner_id_from_user(current_user)

    # 1. Try Redis cache
    try:
        cached = _redis().get(_cache_key(owner_id))
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    # 2. Try In-Memory cache
    now = time.time()
    if owner_id in _MEM_CACHE:
        ts, data = _MEM_CACHE[owner_id]
        if now - ts < CACHE_TTL:
            return data

    # 3. Compute live pipeline
    shipments = await crud.get_shipments(db, owner_id)
    result = await run_pipeline(shipments, db=db, owner_id=owner_id)
    _MEM_CACHE[owner_id] = (now, result)
    return result


@router.post("/risk-analysis/run")
async def run_risk_analysis(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    owner_id = owner_id_from_user(current_user)
    shipments = await crud.get_shipments(db, owner_id)
    result = await run_pipeline(shipments, db=db, owner_id=owner_id)

    # Update in-memory cache
    _MEM_CACHE[owner_id] = (time.time(), result)

    try:
        client = _redis()
        client.setex(_cache_key(owner_id), 3600, json.dumps(result, default=str))
        client.publish("risk_updates", json.dumps({"status": "updated", "owner_id": owner_id}))
    except Exception:
        pass
    return result


@router.get("/pipeline-runs/{run_id}/trace")
async def get_pipeline_run_trace(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Retrieve real per-node execution telemetry traces for the specified workflow run.
    Returns timing, prompt token estimates, LLM usage, and fallback indicators.
    """
    traces = await crud.get_agent_traces(db, run_id)
    return {
        "run_id": run_id,
        "count": len(traces),
        "traces": traces,
    }

