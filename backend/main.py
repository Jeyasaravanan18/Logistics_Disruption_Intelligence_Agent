import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from jose import JWTError
import redis.asyncio as aioredis

from config import ALLOWED_ORIGINS, COOKIE_ACCESS_NAME, IS_PRODUCTION, REDIS_URL
from database import close_db, connect_db, get_database
from routers import auth, disruptions, risk_analysis, shipments
from routers.auth import get_user_from_token


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    db = get_database()
    try:
        await db.users.create_index("email", unique=True)
        try:
            await db.shipments.drop_index("shipment_id_1")
        except Exception:
            pass
        await db.shipments.create_index(
            [("owner_id", 1), ("shipment_id", 1)], unique=True, name="owner_shipment_unique"
        )
        await db.refresh_tokens.create_index("token_hash", unique=True)
        await db.refresh_tokens.create_index("expires_at", expireAfterSeconds=0)
    except Exception as exc:
        print(f"[MongoDB] Index setup notice: {exc}")
    yield
    await close_db()


app = FastAPI(
    title="Logistics Disruption Intelligence Agent API",
    description="Multi-tenant disruption intelligence API",
    version="3.0.0",
    lifespan=lifespan,
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router, tags=["Auth"])
app.include_router(shipments.router, tags=["Shipments"])
app.include_router(disruptions.router, tags=["Disruptions"])
app.include_router(risk_analysis.router, tags=["Risk Analysis"])


@app.websocket("/ws/risk-updates")
async def websocket_endpoint(websocket: WebSocket):
    token = websocket.query_params.get("token") or websocket.cookies.get(COOKIE_ACCESS_NAME)
    if not token:
        await websocket.close(code=4401)
        return

    try:
        user = await get_user_from_token(token, get_database())
    except JWTError:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    owner_id = str(user["id"])
    redis_client = None
    pubsub = None
    try:
        redis_client = await aioredis.from_url(REDIS_URL, decode_responses=True)
        pubsub = redis_client.pubsub()
        await pubsub.subscribe("risk_updates")
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            data = json.loads(message["data"])
            if data.get("owner_id") and data["owner_id"] != owner_id:
                continue
            await websocket.send_json({"event": "analysis_complete", "data": data})
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        print(f"[WebSocket] Redis unavailable, keeping socket idle: {exc}")
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
    finally:
        if pubsub:
            try:
                await pubsub.unsubscribe("risk_updates")
            except Exception:
                pass
        if redis_client:
            try:
                await redis_client.close()
            except Exception:
                pass


@app.get("/", tags=["Health"])
async def root():
    return {
        "status": "online",
        "database": "MongoDB",
        "version": "3.0.0",
        "endpoints": ["/health", "/auth/login", "/shipments", "/disruptions", "/risk-analysis"],
    }


@app.get("/health", tags=["Health"])
async def health():
    checks = {"api": "ok", "mongodb": "down", "redis": "down"}
    try:
        await get_database().command("ping")
        checks["mongodb"] = "ok"
    except Exception as exc:
        checks["mongodb"] = str(exc)

    try:
        client = aioredis.from_url(REDIS_URL, decode_responses=True)
        pong = await client.ping()
        await client.close()
        checks["redis"] = "ok" if pong else "down"
    except Exception as exc:
        checks["redis"] = str(exc)

    healthy = checks["mongodb"] == "ok"
    payload = {
        "status": "healthy" if healthy else "degraded",
        "checks": checks,
    }
    return JSONResponse(payload, status_code=200 if healthy else 503)
