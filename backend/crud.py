import json
import os
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from security import hash_token, utcnow


def _owner_filter(owner_id: str) -> dict:
    return {"owner_id": owner_id}


async def get_shipments(
    db: AsyncIOMotorDatabase,
    owner_id: str,
    skip: int = 0,
    limit: int = 100,
) -> list[dict]:
    cursor = (
        db.shipments.find(_owner_filter(owner_id), {"_id": 0})
        .skip(skip)
        .limit(limit)
    )
    return await cursor.to_list(length=limit)


async def get_shipment_by_id(
    db: AsyncIOMotorDatabase, owner_id: str, shipment_id: str
) -> dict | None:
    return await db.shipments.find_one(
        {"owner_id": owner_id, "shipment_id": shipment_id}, {"_id": 0}
    )


async def create_shipment(
    db: AsyncIOMotorDatabase, owner_id: str, shipment_data: dict
) -> dict:
    existing = await get_shipment_by_id(db, owner_id, shipment_data["shipment_id"])
    if existing:
        raise ValueError("Shipment ID already exists")
    doc = {**shipment_data, "owner_id": owner_id, "updated_at": utcnow()}
    await db.shipments.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def update_shipment(
    db: AsyncIOMotorDatabase, owner_id: str, shipment_id: str, updates: dict
) -> dict | None:
    updates = {k: v for k, v in updates.items() if v is not None}
    updates["updated_at"] = utcnow()
    result = await db.shipments.find_one_and_update(
        {"owner_id": owner_id, "shipment_id": shipment_id},
        {"$set": updates},
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    return result


async def delete_shipment(db: AsyncIOMotorDatabase, owner_id: str, shipment_id: str) -> bool:
    result = await db.shipments.delete_one({"owner_id": owner_id, "shipment_id": shipment_id})
    return result.deleted_count == 1


async def list_owner_ids(db: AsyncIOMotorDatabase) -> list[str]:
    return [oid for oid in await db.shipments.distinct("owner_id") if oid]


async def seed_demo_shipments(db: AsyncIOMotorDatabase, owner_id: str, force: bool = False) -> int:
    count = await db.shipments.count_documents(_owner_filter(owner_id))
    if count > 0 and not force:
        return 0
    if force:
        await db.shipments.delete_many(_owner_filter(owner_id))

    json_path = os.path.join(os.path.dirname(__file__), "data", "shipments.json")
    if not os.path.exists(json_path):
        return 0

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    now = utcnow()
    docs = []
    for item in data:
        row = dict(item)
        edt = row.get("estimated_delivery_time")
        if edt:
            try:
                row["estimated_delivery_time"] = datetime.fromisoformat(str(edt))
            except Exception:
                pass
        row["owner_id"] = owner_id
        row["updated_at"] = now
        docs.append(row)

    if docs:
        await db.shipments.insert_many(docs)
    return len(docs)


async def get_user_by_email(db: AsyncIOMotorDatabase, email: str) -> dict | None:
    user = await db.users.find_one({"email": email.lower().strip()})
    if user and "_id" in user:
        user["id"] = str(user["_id"])
    return user


async def get_user_by_id(db: AsyncIOMotorDatabase, user_id: str) -> dict | None:
    from bson import ObjectId

    try:
        oid = ObjectId(user_id)
    except Exception:
        return None
    user = await db.users.find_one({"_id": oid})
    if user:
        user["id"] = str(user["_id"])
    return user


async def create_user(db: AsyncIOMotorDatabase, user_doc: dict) -> dict:
    user_doc["email"] = user_doc["email"].lower().strip()
    result = await db.users.insert_one(user_doc)
    user_doc["id"] = str(result.inserted_id)
    return user_doc


async def update_user_password(db: AsyncIOMotorDatabase, user_id: str, hashed_password: str) -> None:
    from bson import ObjectId

    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"hashed_password": hashed_password, "updated_at": utcnow()}},
    )


async def store_refresh_token(db: AsyncIOMotorDatabase, user_id: str, raw_token: str, expires_at: datetime) -> None:
    await db.refresh_tokens.insert_one(
        {
            "user_id": user_id,
            "token_hash": hash_token(raw_token),
            "expires_at": expires_at,
            "created_at": utcnow(),
            "revoked": False,
        }
    )


async def get_valid_refresh(db: AsyncIOMotorDatabase, raw_token: str) -> dict | None:
    doc = await db.refresh_tokens.find_one(
        {"token_hash": hash_token(raw_token), "revoked": False}
    )
    if not doc:
        return None
    expires = doc.get("expires_at")
    if expires and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if not expires or expires < utcnow():
        return None
    return doc


async def revoke_refresh_token(db: AsyncIOMotorDatabase, raw_token: str) -> None:
    await db.refresh_tokens.update_one(
        {"token_hash": hash_token(raw_token)},
        {"$set": {"revoked": True}},
    )


async def revoke_user_refresh_tokens(db: AsyncIOMotorDatabase, user_id: str) -> None:
    await db.refresh_tokens.update_many({"user_id": user_id}, {"$set": {"revoked": True}})
