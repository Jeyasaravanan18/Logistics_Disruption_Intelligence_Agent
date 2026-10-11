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

DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/logistics"
SQLITE_FALLBACK_URL = os.getenv("SQLITE_FALLBACK_URL", "sqlite+aiosqlite:///./logistics.db")

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")

_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]

COOKIE_SECURE = IS_PRODUCTION
COOKIE_SAMESITE = "lax"
COOKIE_ACCESS_NAME = "access_token"
COOKIE_REFRESH_NAME = "refresh_token"

# Geospatial & Risk Scoring Constants (Single Source of Truth)
DEFAULT_RADIUS_KM: float = float(os.getenv("DEFAULT_RADIUS_KM", "150.0"))
RISK_THRESHOLD_HIGH: float = float(os.getenv("RISK_THRESHOLD_HIGH", "4.5"))
RISK_THRESHOLD_MEDIUM: float = float(os.getenv("RISK_THRESHOLD_MEDIUM", "1.8"))
CORRIDOR_NUM_SAMPLES: int = int(os.getenv("CORRIDOR_NUM_SAMPLES", "8"))
