from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

import crud
import schemas
from database import get_database
from routers.auth import get_current_user, owner_id_from_user

router = APIRouter()


def _public_shipment(doc: dict) -> dict:
    return {k: v for k, v in doc.items() if k not in {"owner_id", "updated_at"}}


@router.get("/shipments", response_model=schemas.ShipmentListResponse)
async def list_shipments(
    skip: int = 0,
    limit: int = 100,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user),
):
    limit = min(max(limit, 1), 200)
    shipments = await crud.get_shipments(db, owner_id_from_user(current_user), skip=skip, limit=limit)
    return {"count": len(shipments), "shipments": shipments}


@router.post("/shipments", response_model=schemas.ShipmentOut, status_code=201)
async def create_shipment(
    payload: schemas.ShipmentCreate,
    db: AsyncIOMotorDatabase = Depends(get_database),
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
    db: AsyncIOMotorDatabase = Depends(get_database),
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
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user),
):
    deleted = await crud.delete_shipment(db, owner_id_from_user(current_user), shipment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Shipment not found")


@router.post("/shipments/seed-demo", response_model=schemas.ShipmentListResponse)
async def seed_demo(
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user),
):
    await crud.seed_demo_shipments(db, owner_id_from_user(current_user), force=True)
    shipments = await crud.get_shipments(db, owner_id_from_user(current_user))
    return {"count": len(shipments), "shipments": shipments}
