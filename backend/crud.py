"""
Database CRUD and analytical queries using Async SQLAlchemy 2.0.
Replaces legacy NoSQL operations with typed, relational operations.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import delete, desc, distinct, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    AgentTrace,
    Disruption,
    PipelineRun,
    Recommendation,
    RefreshToken,
    RiskAssessment,
    Shipment,
    User,
    utcnow,
)
from security import hash_token


def _shipment_to_dict(s: Shipment) -> dict:
    """Serialize a Shipment ORM instance to a dictionary."""
    return {
        "shipment_id": s.shipment_id,
        "origin": s.origin,
        "destination": s.destination,
        "route_highway": s.route_highway,
        "latitude": s.latitude,
        "longitude": s.longitude,
        "delivery_priority": s.delivery_priority,
        "estimated_delivery_time": s.estimated_delivery_time,
        "cargo_type": s.cargo_type,
        "weight_kg": s.weight_kg,
        "status": s.status,
    }


def _user_to_dict(u: User) -> dict:
    """Serialize a User ORM instance to a dictionary."""
    return {
        "id": u.id,
        "email": u.email,
        "name": u.name,
        "hashed_password": u.hashed_password,
        "created_at": u.created_at,
    }


# ============================================================================
# Shipments CRUD
# ============================================================================


async def get_shipments(
    db: AsyncSession,
    owner_id: str,
    skip: int = 0,
    limit: int = 100,
) -> list[dict]:
    """Retrieve paginated shipments belonging to the given owner."""
    stmt = (
        select(Shipment)
        .where(Shipment.owner_id == owner_id)
        .order_by(Shipment.shipment_id.asc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [_shipment_to_dict(s) for s in result.scalars().all()]


async def get_shipment_by_id(
    db: AsyncSession, owner_id: str, shipment_id: str
) -> dict | None:
    """Retrieve a single shipment by shipment_id and owner_id."""
    stmt = select(Shipment).where(
        Shipment.owner_id == owner_id, Shipment.shipment_id == shipment_id
    )
    result = await db.execute(stmt)
    shipment = result.scalar_one_or_none()
    return _shipment_to_dict(shipment) if shipment else None


async def create_shipment(
    db: AsyncSession, owner_id: str, shipment_data: dict
) -> dict:
    """Create a new shipment record under the specified owner."""
    existing = await get_shipment_by_id(db, owner_id, shipment_data["shipment_id"])
    if existing:
        raise ValueError("Shipment ID already exists")

    shipment = Shipment(
        owner_id=owner_id,
        shipment_id=shipment_data["shipment_id"],
        origin=shipment_data["origin"],
        destination=shipment_data["destination"],
        route_highway=shipment_data["route_highway"],
        latitude=shipment_data["latitude"],
        longitude=shipment_data["longitude"],
        delivery_priority=shipment_data["delivery_priority"],
        estimated_delivery_time=shipment_data.get("estimated_delivery_time"),
        cargo_type=shipment_data.get("cargo_type"),
        weight_kg=shipment_data.get("weight_kg"),
        status=shipment_data.get("status", "IN_TRANSIT"),
    )
    db.add(shipment)
    await db.commit()
    await db.refresh(shipment)
    return _shipment_to_dict(shipment)


async def update_shipment(
    db: AsyncSession, owner_id: str, shipment_id: str, updates: dict
) -> dict | None:
    """Update non-null fields on a shipment and return the updated dictionary."""
    clean_updates = {k: v for k, v in updates.items() if v is not None}
    if not clean_updates:
        return await get_shipment_by_id(db, owner_id, shipment_id)

    clean_updates["updated_at"] = utcnow()

    stmt = (
        update(Shipment)
        .where(Shipment.owner_id == owner_id, Shipment.shipment_id == shipment_id)
        .values(**clean_updates)
    )
    result = await db.execute(stmt)
    if result.rowcount == 0:
        return None
    await db.commit()
    return await get_shipment_by_id(db, owner_id, shipment_id)


async def delete_shipment(
    db: AsyncSession, owner_id: str, shipment_id: str
) -> bool:
    """Delete a shipment record by shipment_id and owner_id."""
    stmt = delete(Shipment).where(
        Shipment.owner_id == owner_id, Shipment.shipment_id == shipment_id
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount > 0


async def list_owner_ids(db: AsyncSession) -> list[str]:
    """List distinct user owner IDs that have registered shipments."""
    stmt = select(distinct(Shipment.owner_id)).where(Shipment.owner_id.is_not(None))
    result = await db.execute(stmt)
    return [str(row[0]) for row in result.all() if row[0]]


async def seed_demo_shipments(
    db: AsyncSession, owner_id: str, force: bool = False
) -> int:
    """
    Seed initial Indian freight shipments from shipments.json into SQL for a user.
    Uses shipments.json strictly as seed data input.
    """
    stmt = select(func.count()).select_from(Shipment).where(Shipment.owner_id == owner_id)
    count = (await db.execute(stmt)).scalar() or 0
    if count > 0 and not force:
        return 0

    if force:
        await db.execute(delete(Shipment).where(Shipment.owner_id == owner_id))
        await db.commit()

    json_path = os.path.join(os.path.dirname(__file__), "data", "shipments.json")
    if not os.path.exists(json_path):
        return 0

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    now = utcnow()
    records = []
    for item in data:
        edt = item.get("estimated_delivery_time")
        parsed_edt = None
        if edt:
            try:
                parsed_edt = datetime.fromisoformat(str(edt))
                if parsed_edt.tzinfo is None:
                    parsed_edt = parsed_edt.replace(tzinfo=timezone.utc)
            except Exception:
                pass

        records.append(
            Shipment(
                owner_id=owner_id,
                shipment_id=item["shipment_id"],
                origin=item["origin"],
                destination=item["destination"],
                route_highway=item["route_highway"],
                latitude=float(item["latitude"]),
                longitude=float(item["longitude"]),
                delivery_priority=item["delivery_priority"],
                estimated_delivery_time=parsed_edt,
                cargo_type=item.get("cargo_type"),
                weight_kg=item.get("weight_kg"),
                status="IN_TRANSIT",
                created_at=now,
                updated_at=now,
            )
        )

    if records:
        db.add_all(records)
        await db.commit()
    return len(records)


# ============================================================================
# Users & Authentication CRUD
# ============================================================================


async def get_user_by_email(db: AsyncSession, email: str) -> dict | None:
    """Retrieve user dictionary by case-insensitive email."""
    stmt = select(User).where(func.lower(User.email) == email.lower().strip())
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    return _user_to_dict(user) if user else None


async def get_user_by_id(db: AsyncSession, user_id: str) -> dict | None:
    """Retrieve user dictionary by primary key UUID."""
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    return _user_to_dict(user) if user else None


async def create_user(db: AsyncSession, user_doc: dict) -> dict:
    """Insert a new user record into the users table."""
    user = User(
        email=user_doc["email"].lower().strip(),
        name=user_doc["name"].strip(),
        hashed_password=user_doc["hashed_password"],
        created_at=utcnow(),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return _user_to_dict(user)


async def update_user_password(
    db: AsyncSession, user_id: str, hashed_password: str
) -> None:
    """Update password hash for the specified user ID."""
    stmt = (
        update(User)
        .where(User.id == user_id)
        .values(hashed_password=hashed_password)
    )
    await db.execute(stmt)
    await db.commit()


async def store_refresh_token(
    db: AsyncSession, user_id: str, raw_token: str, expires_at: datetime
) -> None:
    """Store hashed refresh token for session tracking."""
    token = RefreshToken(
        user_id=user_id,
        token_hash=hash_token(raw_token),
        expires_at=expires_at,
        created_at=utcnow(),
        revoked=False,
    )
    db.add(token)
    await db.commit()


async def get_valid_refresh(db: AsyncSession, raw_token: str) -> dict | None:
    """Check and retrieve an active, unrevoked, unexpired refresh token."""
    h = hash_token(raw_token)
    stmt = select(RefreshToken).where(
        RefreshToken.token_hash == h,
        RefreshToken.revoked.is_(False),
        RefreshToken.expires_at > utcnow(),
    )
    result = await db.execute(stmt)
    token = result.scalar_one_or_none()
    if not token:
        return None
    return {
        "id": token.id,
        "user_id": token.user_id,
        "expires_at": token.expires_at,
    }


async def revoke_refresh_token(db: AsyncSession, raw_token: str) -> None:
    """Revoke a single refresh token by raw token value."""
    h = hash_token(raw_token)
    stmt = (
        update(RefreshToken)
        .where(RefreshToken.token_hash == h)
        .values(revoked=True)
    )
    await db.execute(stmt)
    await db.commit()


async def revoke_user_refresh_tokens(db: AsyncSession, user_id: str) -> None:
    """Revoke all active refresh tokens for the given user ID (logout all)."""
    stmt = (
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id)
        .values(revoked=True)
    )
    await db.execute(stmt)
    await db.commit()


# ============================================================================
# Disruptions & Deduplication Persistence
# ============================================================================


async def upsert_disruptions(db: AsyncSession, disruptions_data: list[dict]) -> list[dict]:
    """
    Persist collected disruption records in SQL, deduplicating by unique content_hash.
    Returns the list of active disruptions.
    """
    if not disruptions_data:
        return []

    saved_items = []
    now = utcnow()

    for d in disruptions_data:
        # Generate stable content hash if not already present
        content_hash = d.get("content_hash")
        if not content_hash:
            import hashlib
            hash_str = f"{d.get('type')}:{d.get('subtype')}:{d.get('location')}:{d.get('lat')}:{d.get('lon')}:{d.get('description', '')[:50]}"
            content_hash = hashlib.sha256(hash_str.encode("utf-8")).hexdigest()
            d["content_hash"] = content_hash

        # Check if already exists in DB
        stmt = select(Disruption).where(Disruption.content_hash == content_hash)
        existing = (await db.execute(stmt)).scalar_one_or_none()

        if existing:
            saved_items.append(d)
            continue

        disruption_row = Disruption(
            id=d.get("id") or str(d.get("content_hash")[:16]),
            type=d.get("type", "unknown"),
            source=d.get("source", "Live"),
            title=d.get("description", "") or d.get("subtype", "Disruption"),
            subtype=d.get("subtype", "Incident"),
            location=d.get("location", "Unknown"),
            lat=float(d.get("lat") or d.get("latitude") or 0.0),
            lon=float(d.get("lon") or d.get("longitude") or 0.0),
            radius_km=float(d.get("radius_km") or 150.0),
            severity=d.get("severity", "LOW"),
            valid_from=now,
            raw_json=d,
            content_hash=content_hash,
            created_at=now,
        )
        db.add(disruption_row)
        saved_items.append(d)

    await db.commit()
    return saved_items


async def get_active_disruptions(db: AsyncSession, limit: int = 100) -> list[dict]:
    """Retrieve active disruption records stored in SQL."""
    stmt = select(Disruption).order_by(desc(Disruption.created_at)).limit(limit)
    result = await db.execute(stmt)
    records = []
    for d in result.scalars().all():
        item = d.raw_json or {}
        item.update({
            "id": d.id,
            "type": d.type,
            "subtype": d.subtype,
            "location": d.location,
            "severity": d.severity,
            "description": d.title,
            "lat": d.lat,
            "lon": d.lon,
            "latitude": d.lat,
            "longitude": d.lon,
            "radius_km": d.radius_km,
            "source": d.source,
            "content_hash": d.content_hash,
        })
        records.append(item)
    return records


# ============================================================================
# Pipeline Runs, Risk Assessments & Agent Traces
# ============================================================================


async def create_pipeline_run(db: AsyncSession, owner_id: str) -> PipelineRun:
    """Create a new PipelineRun record in RUNNING status."""
    run = PipelineRun(
        owner_id=owner_id,
        started_at=utcnow(),
        status="RUNNING",
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def finish_pipeline_run(
    db: AsyncSession,
    run_id: str,
    counts: dict,
    reasoning: str = "",
    status: str = "COMPLETED",
) -> None:
    """Close out a pipeline run record with summary statistics."""
    stmt = (
        update(PipelineRun)
        .where(PipelineRun.id == run_id)
        .values(
            finished_at=utcnow(),
            status=status,
            disruptions_collected=counts.get("disruptions_collected", 0),
            shipments_evaluated=counts.get("shipments_evaluated", 0),
            high_risk_count=counts.get("risk_breakdown", {}).get("HIGH", 0),
            medium_risk_count=counts.get("risk_breakdown", {}).get("MEDIUM", 0),
            low_risk_count=counts.get("risk_breakdown", {}).get("LOW", 0),
            safe_count=counts.get("risk_breakdown", {}).get("SAFE", 0),
            collector_reasoning=reasoning,
        )
    )
    await db.execute(stmt)
    await db.commit()


async def get_pipeline_run(db: AsyncSession, run_id: str) -> PipelineRun | None:
    """Retrieve PipelineRun by ID."""
    stmt = select(PipelineRun).where(PipelineRun.id == run_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_latest_pipeline_run(db: AsyncSession, owner_id: str) -> PipelineRun | None:
    """Retrieve the most recent completed pipeline run for the given owner."""
    stmt = (
        select(PipelineRun)
        .where(PipelineRun.owner_id == owner_id, PipelineRun.status == "COMPLETED")
        .order_by(desc(PipelineRun.started_at))
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def save_assessments_and_recommendations(
    db: AsyncSession,
    run_id: str,
    recommendations: list[dict],
) -> None:
    """Persist risk assessments and corresponding recommendations into SQL."""
    for rec in recommendations:
        sid = rec.get("shipment_id")
        if not sid:
            continue

        # Look up shipment row by shipment_id
        stmt = select(Shipment.id).where(Shipment.shipment_id == sid).limit(1)
        shipment_pk = (await db.execute(stmt)).scalar_one_or_none()
        if not shipment_pk:
            continue

        assessment = RiskAssessment(
            run_id=run_id,
            shipment_id=shipment_pk,
            disruption_id=rec.get("disruption_id") or None,
            score=max(0.0, float(rec.get("risk_score") or 0.0)),
            level=rec.get("risk_level", "SAFE"),
            distance_km=rec.get("distance_to_disruption_km"),
            reason=rec.get("reason", "No disruption detected."),
            impact_duration_hours=int(rec.get("impact_duration_hours") or 0),
        )
        db.add(assessment)
        await db.flush()

        recommendation_row = Recommendation(
            assessment_id=assessment.id,
            action=rec.get("suggested_action", "Continue route"),
            alternate_route=rec.get("alternate_route"),
            estimated_delay_hours=int(rec.get("estimated_delay_hours") or 0),
            customer_message=rec.get("customer_message", "On schedule"),
            rationale=rec.get("reason"),
            source="llm" if "gemini" in str(rec.get("recommendation_by", "")) else "rules",
        )
        db.add(recommendation_row)

    await db.commit()


async def save_agent_traces(
    db: AsyncSession,
    run_id: str,
    traces: list[dict],
) -> None:
    """Persist per-node workflow execution traces for observable telemetry."""
    for t in traces:
        row = AgentTrace(
            run_id=run_id,
            node=t.get("node", "unknown"),
            started_at=t.get("started_at", utcnow()),
            duration_ms=float(t.get("duration_ms", 0.0)),
            input_hash=t.get("input_hash"),
            output_summary=t.get("output_summary"),
            used_llm=bool(t.get("used_llm", False)),
            fallback_used=bool(t.get("fallback_used", False)),
            tokens_estimate=int(t.get("tokens_estimate", 0)),
            error=t.get("error"),
        )
        db.add(row)
    await db.commit()


async def get_agent_traces(db: AsyncSession, run_id: str) -> list[dict]:
    """Retrieve all execution traces for a given pipeline run."""
    stmt = (
        select(AgentTrace)
        .where(AgentTrace.run_id == run_id)
        .order_by(AgentTrace.started_at.asc())
    )
    result = await db.execute(stmt)
    return [
        {
            "id": r.id,
            "node": r.node,
            "started_at": r.started_at.isoformat(),
            "duration_ms": r.duration_ms,
            "input_hash": r.input_hash,
            "output_summary": r.output_summary,
            "used_llm": r.used_llm,
            "fallback_used": r.fallback_used,
            "tokens_estimate": r.tokens_estimate,
            "error": r.error,
        }
        for r in result.scalars().all()
    ]
