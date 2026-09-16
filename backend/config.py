import os
from dotenv import load_dotenv

load_dotenv()

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
IS_PRODUCTION = ENVIRONMENT == "production"

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "").strip()
if not JWT_SECRET_KEY:
    if IS_PRODUCTION:
        raise RuntimeError("JWT_SECRET_KEY is required when ENVIRONMENT=production")
    JWT_SECRET_KEY = "dev-only-not-for-production"

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://127.0.0.1:27017")
if "localhost" in MONGODB_URL:
    MONGODB_URL = MONGODB_URL.replace("localhost", "127.0.0.1")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "logistics")

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")

_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]

COOKIE_SECURE = IS_PRODUCTION
COOKIE_SAMESITE = "lax"
COOKIE_ACCESS_NAME = "access_token"
COOKIE_REFRESH_NAME = "refresh_token"
