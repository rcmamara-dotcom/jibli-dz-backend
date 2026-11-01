"""Tests for /api/parcels routes."""
import pytest
from .conftest import register, auth_headers, PARCEL_PAYLOAD


def test_list_parcels_empty(client):
    r = client.get("/api/parcels")
    assert r.status_code == 200
    assert r.json() == []


def test_create_parcel_unauthenticated(client):
    r = client.post("/api/parcels", json=PARCEL_PAYLOAD)
    assert r.status_code == 401


def test_create_parcel_success(client):
    token = register(client)
    r = client.post("/api/parcels", json=PARCEL_PAYLOAD, headers=auth_headers(token))
    assert r.status_code == 201
    data = r.json()
    assert data["from_city"] == "Paris"
    assert data["to_city"] == "Alger"
    assert data["budget"] == 20.0
    assert data["owner_id"] is not None


def test_create_parcel_appears_in_list(client):
    token = register(client)
    client.post("/api/parcels", json=PARCEL_PAYLOAD, headers=auth_headers(token))
    r = client.get("/api/parcels")
    assert len(r.json()) == 1


def test_create_parcel_invalid_wa(client):
    token = register(client)
    bad = {**PARCEL_PAYLOAD, "wa": "0033612345678"}  # no leading +
    r = client.post("/api/parcels", json=bad, headers=auth_headers(token))
    assert r.status_code == 422


def test_delete_parcel_owner(client):
    token = register(client)
    parcel_id = client.post("/api/parcels", json=PARCEL_PAYLOAD, headers=auth_headers(token)).json()["id"]
    r = client.delete(f"/api/parcels/{parcel_id}", headers=auth_headers(token))
    assert r.status_code == 204
    assert client.get("/api/parcels").json() == []


def test_delete_parcel_not_owner(client):
    token1 = register(client, "owner@test.com")
    token2 = register(client, "intrus@test.com")
    parcel_id = client.post("/api/parcels", json=PARCEL_PAYLOAD, headers=auth_headers(token1)).json()["id"]
    r = client.delete(f"/api/parcels/{parcel_id}", headers=auth_headers(token2))
    assert r.status_code == 404


def test_list_parcels_pagination(client):
    token = register(client)
    for i in range(5):
        client.post("/api/parcels", json={**PARCEL_PAYLOAD, "description": f"Colis {i}"}, headers=auth_headers(token))

    r = client.get("/api/parcels?page=1&limit=3")
    assert len(r.json()) == 3

    r2 = client.get("/api/parcels?page=2&limit=3")
    assert len(r2.json()) == 2
