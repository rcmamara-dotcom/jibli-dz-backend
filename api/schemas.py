from datetime import date, datetime
from pydantic import BaseModel, EmailStr


# ── Auth ──────────────────────────────────────────────────────────────────────

class RegisterIn(BaseModel):
    email: EmailStr
    password: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Trip ──────────────────────────────────────────────────────────────────────

class TripIn(BaseModel):
    name: str
    from_city: str
    to_city: str
    date: date
    capacity: str
    weight: float | None = None
    cap_desc: str | None = None
    wa: str


class TripOut(BaseModel):
    id: int
    name: str
    from_city: str
    to_city: str
    date: date
    capacity: str
    weight: float | None
    cap_desc: str | None
    wa: str
    owner_id: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Parcel ────────────────────────────────────────────────────────────────────

class ParcelIn(BaseModel):
    from_city: str
    to_city: str
    description: str
    budget: float = 0
    wa: str


class ParcelOut(BaseModel):
    id: int
    from_city: str
    to_city: str
    description: str
    budget: float
    wa: str
    owner_id: int | None
    created_at: datetime

    model_config = {"from_attributes": True}
