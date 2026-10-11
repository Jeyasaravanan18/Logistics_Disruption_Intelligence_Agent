"""
Risk analysis router: execute LangGraph workflow or retrieve cached risk matrix.
Uses SQLAlchemy 2.0 AsyncSession and ResilienceCache (deterministic SHA-256 keys,
Redis storage with in-memory TTL fallback) and Redis pub/sub.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Optional

from fastapi import APIRouter, Depends
import redis
from sqlalchemy.ext.asyncio import AsyncSession

import crud
from database import get_db
from pipeline import run_pipeline
from resilience.cache import ResilienceCache
from routers.auth import get_current_user, owner_id_from_user

router = APIRouter()
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")


def _get_redis_client() -> Optional[redis.Redis]:
    """Provide Redis client with fast timeout if reachable."""
    try:
        client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=1)
        client.ping()
        return client
    except Exception:
        return None


# Global instance of the SHA-256 Resilience Cache
risk_cache = ResilienceCache(redis_client=_get_redis_client(), default_ttl=180)
_MEM_CACHE = risk_cache._memory_store


def _compute_cache_key(
    owner_id: str,
    shipments: list[dict],
    disruptions: list[dict],
) -> str:
    """
    Derive deterministic SHA-256 cache key from:
    sha256(owner_id + shipments_version + sorted_disruption_content_hashes)
    """
    # 1. Shipments fingerprint
    shipment_tuples = [
        f"{s.get('shipment_id', '')}:{s.get('status', '')}:{s.get('latitude', '')}:{s.get('longitude', '')}"
        for s in shipments
    ]
    shipments_digest = hashlib.sha256(":".join(sorted(shipment_tuples)).encode("utf-8")).hexdigest()[:16]
    shipments_version = f"{len(shipments)}_{shipments_digest}"

    # 2. Disruption content hashes
    disruption_hashes = [
        str(d.get("content_hash") or d.get("id") or hashlib.sha256(str(d).encode("utf-8")).hexdigest()[:16])
        for d in disruptions
    ]

    return ResilienceCache.generate_key(
        owner_id=owner_id,
        shipments_version=shipments_version,
        disruption_hashes=disruption_hashes,
    )


@router.get("/risk-analysis")
async def get_risk_analysis(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    owner_id = owner_id_from_user(current_user)
    shipments = await crud.get_shipments(db, owner_id)
    active_disruptions = await crud.get_active_disruptions(db, limit=50)

    # 1. Deterministic SHA-256 Cache Check
    cache_key = _compute_cache_key(owner_id, shipments, active_disruptions)
    cached_result = risk_cache.get(cache_key)
    if cached_result is not None:
        return cached_result

    # 2. Cache miss: execute pipeline
    result = await run_pipeline(shipments, db=db, owner_id=owner_id)

    # Recompute key with any newly persisted disruptions from this run
    fresh_disruptions = await crud.get_active_disruptions(db, limit=50)
    fresh_key = _compute_cache_key(owner_id, shipments, fresh_disruptions)
    risk_cache.set(fresh_key, result, ttl_seconds=180)

    return result


@router.post("/risk-analysis/run")
async def run_risk_analysis(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    owner_id = owner_id_from_user(current_user)
    shipments = await crud.get_shipments(db, owner_id)
    result = await run_pipeline(shipments, db=db, owner_id=owner_id)

    # Update deterministic cache
    fresh_disruptions = await crud.get_active_disruptions(db, limit=50)
    fresh_key = _compute_cache_key(owner_id, shipments, fresh_disruptions)
    risk_cache.set(fresh_key, result, ttl_seconds=180)

    # Publish notification on Redis pub/sub if available
    client = _get_redis_client()
    if client:
        try:
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
