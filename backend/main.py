"""
FastAPI ASGI application entry point.
Lifespan manages SQLAlchemy 2.0 connection pool and relational migrations.
"""

from contextlib import asynccontextmanager
import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from jose import JWTError
import redis.asyncio as aioredis
from sqlalchemy import text

from config import ALLOWED_ORIGINS, COOKIE_ACCESS_NAME, IS_PRODUCTION, REDIS_URL
from database import close_db, get_active_url, get_engine, get_sessionmaker, init_db
from routers import analytics, auth, disruptions, risk_analysis, shipments
from routers.auth import get_user_from_token


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context: initialize database tables and teardown cleanly."""
    await init_db()
    yield
    await close_db()


app = FastAPI(
    title="Logistics Disruption Intelligence Agent API",
    description="Multi-tenant disruption intelligence API with PostgreSQL, SQLAlchemy 2.0 & Redis",
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
app.include_router(analytics.router, tags=["Analytics"])


@app.websocket("/ws/risk-updates")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint broadcasting real-time risk updates.
    Closes cleanly with status 4503 if Redis broker is unavailable.
    """
    token = websocket.query_params.get("token") or websocket.cookies.get(COOKIE_ACCESS_NAME)
    if not token:
        await websocket.close(code=4401)
        return

    session_factory = get_sessionmaker()
    try:
        async with session_factory() as db:
            user = await get_user_from_token(token, db)
    except (JWTError, Exception):
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
        print(f"[WebSocket] Redis pubsub error: {exc}")
        # Close with 1011 / 4503 Service Unavailable rather than idling forever
        try:
            await websocket.close(code=1011)
        except Exception:
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
    """Service metadata endpoint."""
    return {
        "status": "online",
        "database": "PostgreSQL (SQLAlchemy 2.0 with SQLite fallback)",
        "active_db": get_active_url(),
        "version": "3.0.0",
        "endpoints": ["/health", "/auth/login", "/shipments", "/disruptions", "/risk-analysis", "/analytics"],
    }


@app.get("/health", tags=["Health"])
async def health():
    """Healthcheck endpoint probing SQL database and Redis broker."""
    checks = {"api": "ok", "database": "down", "redis": "down"}

    # Probe SQL engine
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = str(exc)

    # Probe Redis broker
    try:
        client = aioredis.from_url(REDIS_URL, decode_responses=True)
        pong = await client.ping()
        await client.close()
        checks["redis"] = "ok" if pong else "down"
    except Exception as exc:
        checks["redis"] = str(exc)

    healthy = checks["database"] == "ok"
    payload = {
        "status": "healthy" if healthy else "degraded",
        "checks": checks,
    }
    return JSONResponse(payload, status_code=200 if healthy else 503)
