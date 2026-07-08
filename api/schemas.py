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
    avg_rating: float | None = None
    review_count: int = 0

    model_config = {"from_attributes": True}


# ── Parcel ────────────────────────────────────────────────────────────────────

class ParcelIn(BaseModel):
    from_city: str
    to_city: str
    description: str
    budget: float = 0
    wa: str


# ── Review ────────────────────────────────────────────────────────────────────

class ReviewIn(BaseModel):
    rating: int       # 1–5
    comment: str | None = None


class ReviewOut(BaseModel):
    id: int
    trip_id: int
    reviewer_id: int
    reviewer_email: str
    rating: int
    comment: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Parcel ────────────────────────────────────────────────────────────────────

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
