import re
from datetime import date, datetime
from pydantic import BaseModel, EmailStr, Field, field_validator

_WA_RE = re.compile(r"^\+\d{7,15}$")


def _validate_wa(v: str) -> str:
    v = v.replace(" ", "").replace("-", "")
    if not _WA_RE.match(v):
        raise ValueError("Numéro WhatsApp invalide (format : +33612345678)")
    return v


def _validate_phone(v: str) -> str:
    v = v.replace(" ", "").replace("-", "").replace(".", "")
    if not _WA_RE.match(v):
        raise ValueError("Numéro de téléphone invalide (format international : +33612345678)")
    return v


# ── Auth ──────────────────────────────────────────────────────────────────────

class RegisterIn(BaseModel):
    email: EmailStr
    phone: str
    password: str = Field(max_length=128)
    confirm_password: str = Field(max_length=128)
    name: str | None = Field(default=None, max_length=100)
    birth_date: date | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return _validate_phone(v)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str
    password: str


class GoogleAuthIn(BaseModel):
    id_token: str


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str
    confirm_new_password: str


class MeOut(BaseModel):
    id: int
    email: str
    email_verified: bool = False
    phone: str | None = None
    name: str | None = None
    birth_date: date | None = None
    has_password: bool = True   # False pour un compte créé via Google
    role: str = "user"
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UpdateMeIn(BaseModel):
    """Seuls les champs envoyés sont modifiés ; birth_date: null l'efface."""
    name: str | None = Field(default=None, max_length=100)
    phone: str | None = None
    birth_date: date | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v is None:
            raise ValueError("Le téléphone est obligatoire")
        return _validate_phone(v)


class VerifyEmailIn(BaseModel):
    code: str


class ChangeEmailIn(BaseModel):
    new_email: EmailStr
    password: str


# ── Trip ──────────────────────────────────────────────────────────────────────

class TripIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    from_city: str = Field(min_length=1, max_length=100)
    to_city: str = Field(min_length=1, max_length=100)
    date: date
    capacity: str = Field(min_length=1, max_length=10)
    weight: float | None = Field(default=None, ge=0, le=1000)
    cap_desc: str | None = Field(default=None, max_length=1000)
    wa: str | None = None  # WhatsApp désactivé — messagerie interne


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

PARCEL_TYPES = ("vetements", "alimentaire", "electronique", "medicaments", "documents", "autre")


class ParcelIn(BaseModel):
    from_city: str = Field(min_length=1, max_length=100)
    to_city: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=1000)
    budget: float = Field(default=0, ge=0, le=100_000)
    weight: float | None = Field(default=None, ge=0, le=1000)   # kg
    length: float | None = Field(default=None, ge=0, le=500)    # cm
    width: float | None = Field(default=None, ge=0, le=500)
    height: float | None = Field(default=None, ge=0, le=500)
    wa: str | None = None  # WhatsApp désactivé — messagerie interne
    parcel_type: str | None = None

    @field_validator("parcel_type")
    @classmethod
    def validate_parcel_type(cls, v: str | None) -> str | None:
        if v and v not in PARCEL_TYPES:
            raise ValueError(f"Type invalide. Valeurs acceptées : {', '.join(PARCEL_TYPES)}")
        return v


# ── Admin ─────────────────────────────────────────────────────────────────────

class UserAdminOut(BaseModel):
    id: int
    email: str
    name: str | None = None
    role: str = "user"
    is_admin: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class RoleIn(BaseModel):
    role: str


class AdminStatsOut(BaseModel):
    users: int
    trips: int
    parcels: int
    reviews: int


# ── Review ────────────────────────────────────────────────────────────────────

class ReviewIn(BaseModel):
    rating: int       # 1–5
    comment: str | None = Field(default=None, max_length=1000)


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
    weight: float | None = None
    length: float | None = None
    width: float | None = None
    height: float | None = None
    parcel_type: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Shipment (suivi d'envoi) ──────────────────────────────────────────────────

class ShipmentIn(BaseModel):
    trip_id: int
    description: str

    @field_validator("description")
    @classmethod
    def not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Décris le colis")
        return v[:500]


class ShipmentStatusIn(BaseModel):
    status: str


class ShipmentEventOut(BaseModel):
    status: str
    created_at: datetime


class ShipmentOut(BaseModel):
    id: int
    trip_id: int | None
    from_city: str
    to_city: str
    trip_date: date | None
    description: str
    status: str
    role: str                      # "sender" ou "carrier" pour l'utilisateur courant
    counterpart_name: str | None   # l'autre personne de l'envoi
    events: list[ShipmentEventOut]
    created_at: datetime


# ── Messagerie ────────────────────────────────────────────────────────────────

class ConversationStartIn(BaseModel):
    """Démarrer une conversation sur un trajet ou un colis."""
    trip_id: int | None = None
    parcel_id: int | None = None
    message: str = Field(min_length=1, max_length=2000)

    @field_validator("message")
    @classmethod
    def not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Le message ne peut pas être vide")
        return v


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)

    @field_validator("content")
    @classmethod
    def not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Le message ne peut pas être vide")
        return v


class MessageOut(BaseModel):
    id: int
    sender_id: int
    sender_name: str | None
    content: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationOut(BaseModel):
    id: int
    other_user_id: int
    other_user_name: str | None
    trip_id: int | None
    parcel_id: int | None
    last_message: str | None
    last_message_at: datetime | None
    unread_count: int
    created_at: datetime
