"""
Database engine and session management using Async SQLAlchemy 2.0.
Supports PostgreSQL with asyncpg and graceful fallback to SQLite with aiosqlite.
"""

from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config import DATABASE_URL, SQLITE_FALLBACK_URL
from models import Base

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None
_active_url: str = ""


def get_engine() -> AsyncEngine:
    """Return initialized AsyncEngine instance."""
    global _engine
    if _engine is None:
        raise RuntimeError("Database engine has not been initialized. Call init_db() first.")
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return initialized async_sessionmaker instance."""
    global _sessionmaker
    if _sessionmaker is None:
        raise RuntimeError("Sessionmaker has not been initialized. Call init_db() first.")
    return _sessionmaker


async def init_db(override_url: str | None = None) -> AsyncEngine:
    """
    Initialize SQLAlchemy async engine and create tables.
    Attempts PostgreSQL first; falls back to SQLite if PostgreSQL is unreachable.
    """
    global _engine, _sessionmaker, _active_url

    target_url = override_url or DATABASE_URL

    # Attempt primary database connection
    try:
        connect_args = {}
        if "sqlite" in target_url:
            connect_args["check_same_thread"] = False

        test_engine = create_async_engine(
            target_url,
            echo=False,
            future=True,
            connect_args=connect_args,
        )

        async with test_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        _engine = test_engine
        _active_url = target_url
        print(f"[Database] Successfully connected to primary database: {_active_url}")
    except Exception as exc:
        print(f"[Database WARNING] Failed to connect to primary database ({target_url}): {exc}")
        print(f"[Database] Falling back to SQLite database ({SQLITE_FALLBACK_URL})...")
        fallback_engine = create_async_engine(
            SQLITE_FALLBACK_URL,
            echo=False,
            future=True,
            connect_args={"check_same_thread": False},
        )
        async with fallback_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        _engine = fallback_engine
        _active_url = SQLITE_FALLBACK_URL
        print(f"[Database] SQLite fallback active: {_active_url}")

    _sessionmaker = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Create tables if not already created
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[Database] All relational schema tables verified/created.")

    return _engine


async def close_db() -> None:
    """Dispose active database engine and pool."""
    global _engine, _sessionmaker, _active_url
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _sessionmaker = None
        _active_url = ""
        print("[Database] Database connection pool disposed.")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async database session."""
    global _sessionmaker
    if _sessionmaker is None:
        await init_db()
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_active_url() -> str:
    """Return currently active database URL connection string."""
    return _active_url
