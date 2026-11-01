"""Tests for /api/trips routes."""
import pytest
from .conftest import register, auth_headers, TRIP_PAYLOAD


def test_list_trips_empty(client):
    r = client.get("/api/trips")
    assert r.status_code == 200
    assert r.json() == []


def test_create_trip_unauthenticated(client):
    r = client.post("/api/trips", json=TRIP_PAYLOAD)
    assert r.status_code == 401


def test_create_trip_success(client):
    token = register(client)
    r = client.post("/api/trips", json=TRIP_PAYLOAD, headers=auth_headers(token))
    assert r.status_code == 201
    data = r.json()
    assert data["from_city"] == "Paris"
    assert data["to_city"] == "Alger"
    assert data["name"] == "Ali"
    assert data["owner_id"] is not None


def test_create_trip_appears_in_list(client):
    token = register(client)
    client.post("/api/trips", json=TRIP_PAYLOAD, headers=auth_headers(token))
    r = client.get("/api/trips")
    assert len(r.json()) == 1


def test_create_trip_invalid_wa(client):
    token = register(client)
    bad = {**TRIP_PAYLOAD, "wa": "0612345678"}  # missing +
    r = client.post("/api/trips", json=bad, headers=auth_headers(token))
    assert r.status_code == 422


def test_delete_trip_owner(client):
    token = register(client)
    trip_id = client.post("/api/trips", json=TRIP_PAYLOAD, headers=auth_headers(token)).json()["id"]
    r = client.delete(f"/api/trips/{trip_id}", headers=auth_headers(token))
    assert r.status_code == 204
    assert client.get("/api/trips").json() == []


def test_delete_trip_not_owner(client):
    token1 = register(client, "owner@test.com")
    token2 = register(client, "other@test.com")
    trip_id = client.post("/api/trips", json=TRIP_PAYLOAD, headers=auth_headers(token1)).json()["id"]
    r = client.delete(f"/api/trips/{trip_id}", headers=auth_headers(token2))
    assert r.status_code == 404


def test_delete_trip_unauthenticated(client):
    token = register(client)
    trip_id = client.post("/api/trips", json=TRIP_PAYLOAD, headers=auth_headers(token)).json()["id"]
    r = client.delete(f"/api/trips/{trip_id}")
    assert r.status_code == 401


def test_list_trips_pagination(client):
    token = register(client)
    for i in range(5):
        client.post("/api/trips", json={**TRIP_PAYLOAD, "name": f"Voyageur {i}"}, headers=auth_headers(token))

    r = client.get("/api/trips?page=1&limit=3")
    assert r.status_code == 200
    assert len(r.json()) == 3

    r2 = client.get("/api/trips?page=2&limit=3")
    assert r2.status_code == 200
    assert len(r2.json()) == 2


def test_notify_matching_parcels_called_on_create(client):
    from unittest.mock import patch
    token = register(client)
    with patch("api.routes.trips.notify_matching_parcels") as mock_notify:
        client.post("/api/trips", json=TRIP_PAYLOAD, headers=auth_headers(token))
    mock_notify.assert_called_once()
