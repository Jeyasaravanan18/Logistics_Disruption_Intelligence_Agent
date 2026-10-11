"""
Comprehensive Resilience Suite:
1. Circuit Breaker FSM (CLOSED -> OPEN -> HALF_OPEN -> CLOSED / OPEN) with injectable clock.
2. SHA-256 deterministic assessment cache with TTL expiry, hits/misses, and eviction.
3. Demo mode fixtures fallback for weather and news services.
4. WebSocket fail-fast closure (code 1011) when Redis is unreachable.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import crud
from backend.main import websocket_endpoint
from backend.models import Base
from backend.resilience.circuit_breaker import CircuitBreaker
from backend.resilience.cache import ResilienceCache
from backend.security import create_access_token, get_password_hash
from backend.services.weather_service import fetch_weather_disruptions
from backend.services.news_service import fetch_news_disruptions


# ============================================================================
# 1. Circuit Breaker Finite State Machine Tests
# ============================================================================


class FakeClock:
    """Deterministic simulated clock for time-travel unit tests."""

    def __init__(self, initial_time: float = 1000.0):
        self.current_time = initial_time

    def time(self) -> float:
        return self.current_time

    def advance(self, seconds: float) -> None:
        self.current_time += seconds


def test_circuit_breaker_initial_state_closed():
    clock = FakeClock()
    cb = CircuitBreaker(name="test_cb", failure_threshold=3, cooldown_seconds=30.0, clock=clock.time)
    assert cb.get_state() == CircuitBreaker.CLOSED
    assert cb.can_execute() is True


def test_circuit_breaker_trips_to_open_after_threshold_failures():
    clock = FakeClock()
    cb = CircuitBreaker(name="test_cb", failure_threshold=3, cooldown_seconds=30.0, clock=clock.time)

    cb.record_failure()
    assert cb.get_state() == CircuitBreaker.CLOSED
    assert cb.can_execute() is True

    cb.record_failure()
    assert cb.get_state() == CircuitBreaker.CLOSED

    # 3rd failure hits threshold -> trips to OPEN
    cb.record_failure()
    assert cb.get_state() == CircuitBreaker.OPEN
    assert cb.can_execute() is False


def test_circuit_breaker_quota_exhaustion_trips_immediately():
    clock = FakeClock()
    cb = CircuitBreaker(name="test_cb", failure_threshold=5, cooldown_seconds=30.0, clock=clock.time)

    # 429 quota exhaustion trips directly without waiting for threshold
    cb.record_failure(is_quota_error=True)
    assert cb.get_state() == CircuitBreaker.OPEN
    assert cb.can_execute() is False


def test_circuit_breaker_transitions_to_half_open_after_cooldown():
    clock = FakeClock()
    cb = CircuitBreaker(name="test_cb", failure_threshold=2, cooldown_seconds=30.0, clock=clock.time)

    cb.record_failure()
    cb.record_failure()
    assert cb.get_state() == CircuitBreaker.OPEN

    # Advance time by 15 seconds (less than 30s cooldown)
    clock.advance(15.0)
    assert cb.get_state() == CircuitBreaker.OPEN
    assert cb.can_execute() is False

    # Advance time past 30s cooldown
    clock.advance(16.0)
    assert cb.get_state() == CircuitBreaker.HALF_OPEN
    assert cb.can_execute() is True


def test_circuit_breaker_half_open_failure_immediately_retrips():
    clock = FakeClock()
    cb = CircuitBreaker(name="test_cb", failure_threshold=2, cooldown_seconds=30.0, clock=clock.time)

    cb.record_failure()
    cb.record_failure()
    clock.advance(31.0)
    assert cb.get_state() == CircuitBreaker.HALF_OPEN

    # In HALF_OPEN, a single failure immediately returns to OPEN
    cb.record_failure()
    assert cb.get_state() == CircuitBreaker.OPEN
    assert cb.can_execute() is False


def test_circuit_breaker_half_open_successes_close_circuit():
    clock = FakeClock()
    cb = CircuitBreaker(
        name="test_cb",
        failure_threshold=2,
        cooldown_seconds=30.0,
        success_threshold=2,
        clock=clock.time,
    )

    cb.record_failure()
    cb.record_failure()
    clock.advance(31.0)
    assert cb.get_state() == CircuitBreaker.HALF_OPEN

    # 1st success
    cb.record_success()
    assert cb.get_state() == CircuitBreaker.HALF_OPEN

    # 2nd success reaches success_threshold -> fully CLOSED
    cb.record_success()
    assert cb.get_state() == CircuitBreaker.CLOSED
    assert cb.can_execute() is True


def test_circuit_breaker_force_reset():
    clock = FakeClock()
    cb = CircuitBreaker(name="test_cb", failure_threshold=1, clock=clock.time)
    cb.record_failure()
    assert cb.get_state() == CircuitBreaker.OPEN

    cb.reset()
    assert cb.get_state() == CircuitBreaker.CLOSED
    assert cb.can_execute() is True


# ============================================================================
# 2. SHA-256 Resilience Cache Tests
# ============================================================================


def test_cache_key_generation_order_invariance():
    """Hashes of disruptions in different order MUST generate identical SHA-256 cache key."""
    disruptions_a = ["hash_abc", "hash_xyz", "hash_123"]
    disruptions_b = ["hash_123", "hash_xyz", "hash_abc"]

    key_a = ResilienceCache.generate_key("owner_1", "v1", disruptions_a)
    key_b = ResilienceCache.generate_key("owner_1", "v1", disruptions_b)

    assert key_a == key_b
    assert key_a.startswith("cache:assessment:")
    assert len(key_a.split(":")[-1]) == 64  # valid sha256 hex digest length


def test_cache_key_generation_sensitivity():
    """Different owners, versions, or disruptions yield different keys."""
    key1 = ResilienceCache.generate_key("owner_1", "v1", ["h1"])
    key2 = ResilienceCache.generate_key("owner_2", "v1", ["h1"])
    key3 = ResilienceCache.generate_key("owner_1", "v2", ["h1"])
    key4 = ResilienceCache.generate_key("owner_1", "v1", ["h2"])

    assert len({key1, key2, key3, key4}) == 4


def test_cache_hit_miss_and_ttl_expiry():
    clock = FakeClock()
    cache = ResilienceCache(default_ttl=60, clock=clock.time)
    key = "cache:assessment:test_key"

    # Initial miss
    assert cache.get(key) is None
    assert cache.misses == 1
    assert cache.hits == 0

    # Store entry
    payload = {"status": "success", "risk_score": 75}
    cache.set(key, payload, ttl_seconds=60)

    # Cache hit
    retrieved = cache.get(key)
    assert retrieved == payload
    assert cache.hits == 1

    # Advance time by 50 seconds (still valid)
    clock.advance(50.0)
    assert cache.get(key) == payload
    assert cache.hits == 2

    # Advance past TTL (total 70 seconds)
    clock.advance(20.0)
    assert cache.get(key) is None
    assert cache.misses == 2


def test_cache_invalidation():
    clock = FakeClock()
    cache = ResilienceCache(default_ttl=120, clock=clock.time)
    key = "cache:assessment:evict_me"

    cache.set(key, {"value": 42})
    assert cache.get(key) == {"value": 42}

    cache.invalidate(key)
    assert cache.get(key) is None


# ============================================================================
# 3. Demo Mode & Recorded Fixtures Tests
# ============================================================================


@pytest.mark.anyio
async def test_weather_service_loads_demo_fixtures_when_key_missing():
    """Verify that empty or placeholder OpenWeather API keys fall back to recorded fixtures."""
    with patch.dict(os.environ, {"OPENWEATHER_API_KEY": ""}):
        disruptions = await fetch_weather_disruptions()
        assert len(disruptions) > 0
        for d in disruptions:
            assert d["type"] == "weather"
            assert d["data_source"] == "demo_fixture"
            assert "Demo Fixture" in d["source"]


@pytest.mark.anyio
async def test_news_service_loads_demo_fixtures():
    """Verify that news service gracefully loads demo fixtures when DEMO_MODE is set."""
    with patch.dict(os.environ, {"DEMO_MODE": "true"}):
        disruptions = await fetch_news_disruptions()
        assert len(disruptions) > 0
        for d in disruptions:
            assert d["type"] == "news"
            assert d["data_source"] == "demo_fixture"
            assert "Demo Fixture" in d["source"]


# ============================================================================
# 4. WebSocket Resilience (Fail-fast closure on broker offline)
# ============================================================================


@pytest.mark.anyio
async def test_websocket_closes_fast_when_redis_offline():
    """When Redis is down/unreachable, WebSocket connection closes cleanly with code 1011."""
    # Set up isolated SQLite engine and user for sessionmaker
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        user = await crud.create_user(db, {
            "email": "ws_resilience@demo.com",
            "name": "WS Test",
            "hashed_password": get_password_hash("password123"),
        })

    token = create_access_token(user["email"])

    mock_ws = AsyncMock()
    mock_ws.query_params = {"token": token}
    mock_ws.cookies = {}
    mock_ws.accept = AsyncMock()
    mock_ws.close = AsyncMock()

    with patch("backend.main.get_sessionmaker", return_value=session_factory), \
         patch("backend.main.REDIS_URL", "redis://127.0.0.1:59999/0"):
        await websocket_endpoint(mock_ws)

        mock_ws.accept.assert_awaited_once()
        mock_ws.close.assert_awaited_with(code=1011)

    await engine.dispose()
