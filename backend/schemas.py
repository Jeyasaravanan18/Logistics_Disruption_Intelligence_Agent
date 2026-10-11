from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ShipmentBase(BaseModel):
    origin: str = Field(min_length=2, max_length=80)
    destination: str = Field(min_length=2, max_length=80)
    route_highway: str = Field(min_length=2, max_length=80)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    delivery_priority: str
    estimated_delivery_time: Optional[datetime] = None
    cargo_type: Optional[str] = Field(default=None, max_length=80)
    weight_kg: Optional[int] = Field(default=None, ge=0, le=100000)

    @field_validator("delivery_priority")
    @classmethod
    def validate_priority(cls, value: str) -> str:
        normalized = value.upper().strip()
        if normalized not in {"HIGH", "MEDIUM", "LOW"}:
            raise ValueError("delivery_priority must be HIGH, MEDIUM, or LOW")
        return normalized


class ShipmentCreate(ShipmentBase):
    shipment_id: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")


class ShipmentUpdate(BaseModel):
    origin: Optional[str] = Field(default=None, min_length=2, max_length=80)
    destination: Optional[str] = Field(default=None, min_length=2, max_length=80)
    route_highway: Optional[str] = Field(default=None, min_length=2, max_length=80)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    delivery_priority: Optional[str] = None
    estimated_delivery_time: Optional[datetime] = None
    cargo_type: Optional[str] = Field(default=None, max_length=80)
    weight_kg: Optional[int] = Field(default=None, ge=0, le=100000)

    @field_validator("delivery_priority")
    @classmethod
    def validate_priority(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.upper().strip()
        if normalized not in {"HIGH", "MEDIUM", "LOW"}:
            raise ValueError("delivery_priority must be HIGH, MEDIUM, or LOW")
        return normalized


class ShipmentOut(ShipmentBase):
    shipment_id: str
    model_config = ConfigDict(from_attributes=True)


class ShipmentListResponse(BaseModel):
    count: int
    shipments: list[ShipmentOut]
    next_cursor: Optional[str] = None


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    name: str = Field(min_length=2, max_length=80)

    @field_validator("password")
    @classmethod
    def strong_enough(cls, value: str) -> str:
        if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError("Password must include letters and numbers")
        return value


class UserResponse(BaseModel):
    id: Optional[str] = None
    email: str
    name: str
    model_config = ConfigDict(from_attributes=True)



class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    email: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=72)

    @field_validator("new_password")
    @classmethod
    def strong_enough(cls, value: str) -> str:
        if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError("Password must include letters and numbers")
        return value


class RefreshRequest(BaseModel):
    refresh_token: Optional[str] = None


# ============================================================================
# Analytical SQL Schemas (Phase 2)
# ============================================================================


class RiskBreakdownCounts(BaseModel):
    HIGH: int = 0
    MEDIUM: int = 0
    LOW: int = 0
    SAFE: int = 0


class DashboardKPIsResponse(BaseModel):
    run_id: Optional[str] = None
    started_at: Optional[str] = None
    status: Optional[str] = None
    total_assessments: int = 0
    counts_by_level: RiskBreakdownCounts
    avg_risk_score: float = 0.0
    max_risk_score: float = 0.0


class RiskTrendItem(BaseModel):
    shipment_id: str
    origin: str
    destination: str
    route_highway: str
    current_score: float
    current_level: str
    previous_score: Optional[float] = None
    score_delta: Optional[float] = None
    trend: str  # "INCREASED", "DECREASED", "STABLE", "NEW"
    latest_run_id: str


class RiskTrendsResponse(BaseModel):
    count: int
    trends: list[RiskTrendItem]


class CorridorExposureItem(BaseModel):
    corridor: str
    active_shipments: int
    total_assessments: int
    unique_disruptions: int
    avg_risk_score: float
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int


class CorridorExposureResponse(BaseModel):
    corridors: list[CorridorExposureItem]


class DisruptionTimelineItem(BaseModel):
    day: str
    total_disruptions: int
    high_count: int
    medium_count: int
    low_count: int


class DisruptionTimelineResponse(BaseModel):
    days_analyzed: int
    timeline: list[DisruptionTimelineItem]

