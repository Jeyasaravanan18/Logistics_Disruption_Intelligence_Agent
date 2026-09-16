import hashlib
import secrets
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from time import time

from fastapi import HTTPException, Request, status
from jose import JWTError, jwt
import bcrypt

from config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
    REFRESH_TOKEN_EXPIRE_DAYS,
)

_rate_hits: dict[str, list[float]] = defaultdict(list)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8")[:72],
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8")[:72], salt).decode("utf-8")


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    expire = utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {"sub": subject, "type": "access", "exp": expire}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def refresh_expiry() -> datetime:
    return utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)


def decode_token(token: str, expected_type: str = "access") -> dict:
    payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    if payload.get("type") != expected_type:
        raise JWTError("Invalid token type")
    return payload


def extract_bearer_or_cookie(request: Request, cookie_name: str) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
        if token:
            return token
    return request.cookies.get(cookie_name)


def enforce_rate_limit(key: str, limit: int = 10, window_seconds: int = 900) -> None:
    now = time()
    recent = [t for t in _rate_hits[key] if now - t < window_seconds]
    if len(recent) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please wait and try again.",
        )
    recent.append(now)
    _rate_hits[key] = recent


def client_key(request: Request, suffix: str) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
    return f"{suffix}:{ip}"
