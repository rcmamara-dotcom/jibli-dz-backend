"""Tests for /api/admin routes."""
import pytest
from godata.models import User
from .conftest import register, auth_headers, TRIP_PAYLOAD, PARCEL_PAYLOAD


def _make_admin(email: str):
    User.update(is_admin=True).where(User.email == email).execute()


def test_admin_stats_forbidden_for_user(client):
    token = register(client)
    r = client.get("/api/admin/stats", headers=auth_headers(token))
    assert r.status_code == 403


def test_admin_stats_forbidden_unauthenticated(client):
    r = client.get("/api/admin/stats")
    assert r.status_code == 401


def test_admin_stats_ok(client):
    token = register(client, "admin@test.com")
    _make_admin("admin@test.com")
    r = client.get("/api/admin/stats", headers=auth_headers(token))
    assert r.status_code == 200
    data = r.json()
    assert "users" in data and "trips" in data and "parcels" in data and "reviews" in data


def test_admin_list_users(client):
    register(client, "u1@test.com")
    admin_token = register(client, "admin@test.com")
    _make_admin("admin@test.com")
    r = client.get("/api/admin/users", headers=auth_headers(admin_token))
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_admin_delete_trip(client):
    user_token = register(client, "user@test.com")
    admin_token = register(client, "admin@test.com")
    _make_admin("admin@test.com")

    trip_id = client.post("/api/trips", json=TRIP_PAYLOAD, headers=auth_headers(user_token)).json()["id"]
    r = client.delete(f"/api/admin/trips/{trip_id}", headers=auth_headers(admin_token))
    assert r.status_code == 204
    assert client.get("/api/trips").json() == []


def test_admin_delete_parcel(client):
    user_token = register(client, "user@test.com")
    admin_token = register(client, "admin@test.com")
    _make_admin("admin@test.com")

    parcel_id = client.post("/api/parcels", json=PARCEL_PAYLOAD, headers=auth_headers(user_token)).json()["id"]
    r = client.delete(f"/api/admin/parcels/{parcel_id}", headers=auth_headers(admin_token))
    assert r.status_code == 204
    assert client.get("/api/parcels").json() == []


def test_admin_cannot_delete_self(client):
    admin_token = register(client, "admin@test.com")
    _make_admin("admin@test.com")
    admin_id = User.get(User.email == "admin@test.com").id
    r = client.delete(f"/api/admin/users/{admin_id}", headers=auth_headers(admin_token))
    # Returns 400: cannot delete your own account
    assert r.status_code == 400
