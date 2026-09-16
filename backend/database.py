from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from config import MONGODB_DB_NAME, MONGODB_URL

client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global client
    if client is None:
        client = AsyncIOMotorClient(MONGODB_URL, serverSelectionTimeoutMS=5000)
    return client


def get_database() -> AsyncIOMotorDatabase:
    return get_client()[MONGODB_DB_NAME]


async def connect_db() -> None:
    global client
    client = AsyncIOMotorClient(MONGODB_URL, serverSelectionTimeoutMS=5000)
    await client.admin.command("ping")
    print(f"[MongoDB] Connected to {MONGODB_URL} (db={MONGODB_DB_NAME})")


async def close_db() -> None:
    global client
    if client:
        client.close()
        client = None
        print("[MongoDB] Connection closed.")
