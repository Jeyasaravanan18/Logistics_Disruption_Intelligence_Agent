from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


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

    class Config:
        from_attributes = True


class ShipmentListResponse(BaseModel):
    count: int
    shipments: list[ShipmentOut]


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

    class Config:
        from_attributes = True


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
