from datetime import datetime
from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from workflow.graph import execute_workflow


def serialize_shipment(doc: dict) -> dict:
    edt = doc.get("estimated_delivery_time")
    if isinstance(edt, datetime):
        edt = edt.isoformat()
    return {
        "shipment_id": doc.get("shipment_id"),
        "origin": doc.get("origin"),
        "destination": doc.get("destination"),
        "route_highway": doc.get("route_highway"),
        "cargo_type": doc.get("cargo_type"),
        "delivery_priority": doc.get("delivery_priority"),
        "estimated_delivery_time": edt,
        "latitude": doc.get("latitude"),
        "longitude": doc.get("longitude"),
        "weight_kg": doc.get("weight_kg"),
    }


async def run_pipeline(
    shipments_raw: list[dict],
    db: Optional[AsyncSession] = None,
    owner_id: str = "default_operator",
    run_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Execute the LangGraph disruption intelligence workflow.
    Executes planning -> collection -> analysis -> scoring -> bounded review -> recommendation -> persistence.
    """
    shipments = [serialize_shipment(s) for s in shipments_raw]
    return await execute_workflow(
        shipments=shipments,
        owner_id=owner_id,
        db=db,
        run_id=run_id,
    )
