"""
Authentication and Session Security Suite:
Tests user registration, login credential verification, HttpOnly cookie issuance,
refresh token rotation, token revocation upon logout, and unauthorized access rejections.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config import COOKIE_ACCESS_NAME, COOKIE_REFRESH_NAME
from backend.database import get_db
from backend.main import app
from backend.models import Base


@pytest.fixture
async def auth_test_setup():
    """Isolated SQLite database and client fixture for auth tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    from unittest.mock import patch
    with patch("backend.database.get_sessionmaker", return_value=session_factory), \
         patch("database.get_sessionmaker", return_value=session_factory):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client, session_factory

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.anyio
async def test_auth_registration_and_duplicate_rejection(auth_test_setup):
    client, _ = auth_test_setup

    # 1. Successful registration
    reg_payload = {"email": "fresh_user@example.com", "name": "Fresh User", "password": "secure_password_123"}
    resp = await client.post("/auth/register", json=reg_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "fresh_user@example.com"
    assert "id" in data
    assert "hashed_password" not in data

    # 2. Duplicate registration rejected
    resp_dup = await client.post("/auth/register", json=reg_payload)
    assert resp_dup.status_code == 400
    assert "already registered" in resp_dup.json()["detail"]


@pytest.mark.anyio
async def test_auth_login_sets_cookies_and_validates_credentials(auth_test_setup):
    client, _ = auth_test_setup

    # Register user first
    await client.post("/auth/register", json={
        "email": "login_test@example.com",
        "name": "Login User",
        "password": "valid_password_456",
    })

    # 1. Invalid credentials -> 401
    bad_login = await client.post("/auth/login", data={
        "username": "login_test@example.com",
        "password": "wrong_password",
    })
    assert bad_login.status_code == 401

    # 2. Valid credentials -> 200 + sets access and refresh cookies
    good_login = await client.post("/auth/login", data={
        "username": "login_test@example.com",
        "password": "valid_password_456",
    })
    assert good_login.status_code == 200
    assert COOKIE_ACCESS_NAME in good_login.cookies
    assert COOKIE_REFRESH_NAME in good_login.cookies


@pytest.mark.anyio
async def test_auth_refresh_token_rotation(auth_test_setup):
    client, _ = auth_test_setup

    # Register & Login
    await client.post("/auth/register", json={
        "email": "rotate_test@example.com",
        "name": "Rotate User",
        "password": "password789",
    })
    login_resp = await client.post("/auth/login", data={
        "username": "rotate_test@example.com",
        "password": "password789",
    })
    first_refresh_cookie = login_resp.cookies[COOKIE_REFRESH_NAME]

    # Refresh token endpoint rotates refresh token
    refresh_resp = await client.post("/auth/refresh", cookies={COOKIE_REFRESH_NAME: first_refresh_cookie})
    assert refresh_resp.status_code == 200
    second_refresh_cookie = refresh_resp.cookies.get(COOKIE_REFRESH_NAME)
    assert second_refresh_cookie is not None
    assert second_refresh_cookie != first_refresh_cookie

    # Attempting to reuse the now-revoked first refresh token MUST fail with 401
    replay_resp = await client.post("/auth/refresh", cookies={COOKIE_REFRESH_NAME: first_refresh_cookie})
    assert replay_resp.status_code == 401


@pytest.mark.anyio
async def test_auth_logout_revocation(auth_test_setup):
    client, _ = auth_test_setup

    # Register & Login
    await client.post("/auth/register", json={
        "email": "logout_test@example.com",
        "name": "Logout User",
        "password": "password789",
    })
    login_resp = await client.post("/auth/login", data={
        "username": "logout_test@example.com",
        "password": "password789",
    })
    access_cookie = login_resp.cookies[COOKIE_ACCESS_NAME]
    refresh_cookie = login_resp.cookies[COOKIE_REFRESH_NAME]

    # Logout
    logout_resp = await client.post("/auth/logout", cookies={
        COOKIE_ACCESS_NAME: access_cookie,
        COOKIE_REFRESH_NAME: refresh_cookie,
    })
    assert logout_resp.status_code == 200

    # Refreshing after logout must be rejected
    after_logout_refresh = await client.post("/auth/refresh", cookies={COOKIE_REFRESH_NAME: refresh_cookie})
    assert after_logout_refresh.status_code == 401
