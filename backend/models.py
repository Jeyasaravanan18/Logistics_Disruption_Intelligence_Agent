from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class UserInDB(BaseModel):
    email: str
    name: str
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ShipmentInDB(BaseModel):
    owner_id: str
    shipment_id: str
    origin: str
    destination: str
    route_highway: str
    latitude: float
    longitude: float
    delivery_priority: str
    estimated_delivery_time: Optional[datetime] = None
    cargo_type: Optional[str] = None
    weight_kg: Optional[int] = None
