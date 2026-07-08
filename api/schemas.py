import re
from datetime import date, datetime
from pydantic import BaseModel, EmailStr, field_validator

_WA_RE = re.compile(r"^\+\d{7,15}$")


def _validate_wa(v: str) -> str:
    if not _WA_RE.match(v):
        raise ValueError("Numéro WhatsApp invalide (format : +33612345678)")
    return v


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


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str
    password: str


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

    @field_validator("wa")
    @classmethod
    def validate_wa(cls, v: str) -> str:
        return _validate_wa(v)


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

    @field_validator("wa")
    @classmethod
    def validate_wa(cls, v: str) -> str:
        return _validate_wa(v)


# ── Admin ─────────────────────────────────────────────────────────────────────

class UserAdminOut(BaseModel):
    id: int
    email: str
    is_admin: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class AdminStatsOut(BaseModel):
    users: int
    trips: int
    parcels: int
    reviews: int


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
