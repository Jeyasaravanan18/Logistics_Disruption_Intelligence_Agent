"""
Shipments router: list, create, update, delete, seed demo.
Backed by PostgreSQL/SQLite via SQLAlchemy 2.0 AsyncSession.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

import crud
import schemas
from database import get_db
from routers.auth import get_current_user, owner_id_from_user

router = APIRouter()


def _public_shipment(doc: dict) -> dict:
    return {k: v for k, v in doc.items() if k not in {"owner_id", "updated_at"}}


@router.get("/shipments", response_model=schemas.ShipmentListResponse)
async def list_shipments(
    skip: int = 0,
    limit: int = 100,
    cursor: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    List shipments for authenticated user.
    Supports keyset seek pagination via 'cursor' or offset pagination via 'skip' and 'limit'.
    """
    owner_id = owner_id_from_user(current_user)
    if cursor is not None:
        return await crud.get_shipments_keyset(db, owner_id, limit=limit, cursor=cursor)

    limit = min(max(limit, 1), 200)
    shipments = await crud.get_shipments(db, owner_id, skip=skip, limit=limit)
    return {"count": len(shipments), "shipments": shipments, "next_cursor": None}


@router.post("/shipments", response_model=schemas.ShipmentOut, status_code=201)
async def create_shipment(
    payload: schemas.ShipmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        created = await crud.create_shipment(
            db, owner_id_from_user(current_user), payload.model_dump()
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _public_shipment(created)


@router.patch("/shipments/{shipment_id}", response_model=schemas.ShipmentOut)
async def update_shipment(
    shipment_id: str,
    payload: schemas.ShipmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    updated = await crud.update_shipment(
        db,
        owner_id_from_user(current_user),
        shipment_id,
        payload.model_dump(exclude_unset=True),
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return _public_shipment(updated)


@router.delete("/shipments/{shipment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shipment(
    shipment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    deleted = await crud.delete_shipment(db, owner_id_from_user(current_user), shipment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Shipment not found")


@router.post("/shipments/seed-demo", response_model=schemas.ShipmentListResponse)
async def seed_demo(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await crud.seed_demo_shipments(db, owner_id_from_user(current_user), force=True)
    shipments = await crud.get_shipments(db, owner_id_from_user(current_user))
    return {"count": len(shipments), "shipments": shipments}
