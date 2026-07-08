"""
Test fixtures — SQLite file DB (temp), no external services required.
"""
import os
import tempfile
import pytest

os.environ["JWT_SECRET"] = "test-secret-key"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["JWT_EXPIRE_MINUTES"] = "60"
os.environ["SMTP_HOST"] = ""
os.environ["RATELIMIT_ENABLED"] = "false"   # disable slowapi in tests

from peewee import SqliteDatabase
from godata.models import User, Trip, Parcel, Review
import godata.db as _godata_db

MODELS = [User, Trip, Parcel, Review]


@pytest.fixture(autouse=True)
def fresh_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db = SqliteDatabase(tmp.name, pragmas={"foreign_keys": 1})

    _godata_db.database = db
    for m in MODELS:
        m._meta.database = db

    db.connect()
    db.create_tables(MODELS)
    yield db
    db.close()
    os.unlink(tmp.name)


@pytest.fixture()
def client(fresh_db):
    from unittest.mock import patch
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient
    from fastapi.middleware.cors import CORSMiddleware
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from api.routes import auth, trips, parcels, reviews, admin
    from api.limiter import limiter

    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.include_router(auth.router)
    app.include_router(trips.router)
    app.include_router(parcels.router)
    app.include_router(reviews.router)
    app.include_router(admin.router)

    @app.middleware("http")
    async def db_middleware(request: Request, call_next):
        fresh_db.connect(reuse_if_open=True)
        return await call_next(request)

    with patch("api.routes.trips.notify_matching_parcels", lambda trip: None):
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


# ── Helpers ───────────────────────────────────────────────────────────────────

def register(client, email="user@test.com", password="secret123"):
    r = client.post("/api/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


TRIP_PAYLOAD = {
    "name": "Ali",
    "from_city": "Paris",
    "to_city": "Alger",
    "date": "2099-12-01",
    "capacity": "10kg",
    "wa": "+33612345678",
}

PARCEL_PAYLOAD = {
    "from_city": "Paris",
    "to_city": "Alger",
    "description": "Vêtements",
    "budget": 20.0,
    "wa": "+33612345678",
}
