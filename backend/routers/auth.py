from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError
from motor.motor_asyncio import AsyncIOMotorDatabase

import crud
import schemas
from config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    COOKIE_ACCESS_NAME,
    COOKIE_REFRESH_NAME,
    COOKIE_SAMESITE,
    COOKIE_SECURE,
)
from database import get_database
from security import (
    client_key,
    create_access_token,
    create_refresh_token,
    decode_token,
    enforce_rate_limit,
    extract_bearer_or_cookie,
    get_password_hash,
    refresh_expiry,
    utcnow,
    verify_password,
)

router = APIRouter(prefix="/auth")


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        COOKIE_ACCESS_NAME,
        access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        COOKIE_REFRESH_NAME,
        refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=7 * 24 * 60 * 60,
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(COOKIE_ACCESS_NAME, path="/")
    response.delete_cookie(COOKIE_REFRESH_NAME, path="/")


async def get_current_user(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = extract_bearer_or_cookie(request, COOKIE_ACCESS_NAME)
    if not token:
        raise credentials_exception
    try:
        payload = decode_token(token, expected_type="access")
        email = payload.get("sub")
        if not email:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await crud.get_user_by_email(db, email)
    if user is None:
        raise credentials_exception
    return user


async def get_user_from_token(token: str, db: AsyncIOMotorDatabase) -> dict:
    payload = decode_token(token, expected_type="access")
    email = payload.get("sub")
    if not email:
        raise JWTError("missing subject")
    user = await crud.get_user_by_email(db, email)
    if not user:
        raise JWTError("user not found")
    return user


def owner_id_from_user(user: dict) -> str:
    return str(user["id"])


@router.post("/register", response_model=schemas.UserResponse, status_code=201)
async def register(
    request: Request,
    user: schemas.UserCreate,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    enforce_rate_limit(client_key(request, "register"), limit=60, window_seconds=60)
    existing = await crud.get_user_by_email(db, user.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user_doc = {
        "email": user.email.lower().strip(),
        "name": user.name.strip(),
        "hashed_password": get_password_hash(user.password),
        "created_at": utcnow(),
    }
    created = await crud.create_user(db, user_doc)
    await crud.seed_demo_shipments(db, created["id"])
    return {"id": created["id"], "email": created["email"], "name": created["name"]}


@router.post("/login", response_model=schemas.Token)
async def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    enforce_rate_limit(client_key(request, "login"), limit=120, window_seconds=60)
    user = await crud.get_user_by_email(db, form_data.username)
    if not user or not verify_password(form_data.password, user.get("hashed_password", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        user["email"], timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    refresh_token = create_refresh_token()
    await crud.store_refresh_token(db, user["id"], refresh_token, refresh_expiry())
    _set_auth_cookies(response, access_token, refresh_token)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=schemas.Token)
async def refresh_session(
    request: Request,
    response: Response,
    body: schemas.RefreshRequest | None = None,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    raw = (body.refresh_token if body else None) or request.cookies.get(COOKIE_REFRESH_NAME)
    if not raw:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    stored = await crud.get_valid_refresh(db, raw)
    if not stored:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user = await crud.get_user_by_id(db, stored["user_id"])
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists")

    await crud.revoke_refresh_token(db, raw)
    access_token = create_access_token(user["email"])
    new_refresh = create_refresh_token()
    await crud.store_refresh_token(db, user["id"], new_refresh, refresh_expiry())
    _set_auth_cookies(response, access_token, new_refresh)
    return {
        "access_token": access_token,
        "refresh_token": new_refresh,
        "token_type": "bearer",
    }


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user),
):
    raw = request.cookies.get(COOKIE_REFRESH_NAME)
    if raw:
        await crud.revoke_refresh_token(db, raw)
    else:
        await crud.revoke_user_refresh_tokens(db, current_user["id"])
    _clear_auth_cookies(response)
    return {"ok": True}


@router.post("/change-password")
async def change_password(
    payload: schemas.ChangePasswordRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user),
):
    if not verify_password(payload.current_password, current_user.get("hashed_password", "")):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    hashed = get_password_hash(payload.new_password)
    await crud.update_user_password(db, current_user["id"], hashed)
    await crud.revoke_user_refresh_tokens(db, current_user["id"])
    return {"ok": True}


@router.get("/me", response_model=schemas.UserResponse)
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return {
        "id": current_user.get("id"),
        "email": current_user["email"],
        "name": current_user["name"],
    }
