"""Tests for /api/trips/{id}/reviews routes."""
import pytest
from .conftest import register, auth_headers, TRIP_PAYLOAD


def _create_trip(client, token):
    r = client.post("/api/trips", json=TRIP_PAYLOAD, headers=auth_headers(token))
    assert r.status_code == 201
    return r.json()["id"]


def test_list_reviews_empty(client):
    token = register(client)
    trip_id = _create_trip(client, token)
    r = client.get(f"/api/trips/{trip_id}/reviews")
    assert r.status_code == 200
    assert r.json() == []


def test_add_review_success(client):
    owner = register(client, "owner@test.com")
    reviewer = register(client, "reviewer@test.com")
    trip_id = _create_trip(client, owner)

    r = client.post(f"/api/trips/{trip_id}/reviews",
                    json={"rating": 4, "comment": "Super !"},
                    headers=auth_headers(reviewer))
    assert r.status_code == 201
    data = r.json()
    assert data["rating"] == 4
    assert data["comment"] == "Super !"


def test_add_review_unauthenticated(client):
    token = register(client)
    trip_id = _create_trip(client, token)
    r = client.post(f"/api/trips/{trip_id}/reviews", json={"rating": 3})
    assert r.status_code == 401


def test_add_review_own_trip(client):
    token = register(client)
    trip_id = _create_trip(client, token)
    r = client.post(f"/api/trips/{trip_id}/reviews",
                    json={"rating": 5},
                    headers=auth_headers(token))
    assert r.status_code == 400
    assert "propre trajet" in r.json()["detail"]


def test_add_review_duplicate(client):
    owner = register(client, "owner@test.com")
    reviewer = register(client, "reviewer@test.com")
    trip_id = _create_trip(client, owner)

    client.post(f"/api/trips/{trip_id}/reviews", json={"rating": 4}, headers=auth_headers(reviewer))
    r = client.post(f"/api/trips/{trip_id}/reviews", json={"rating": 5}, headers=auth_headers(reviewer))
    assert r.status_code == 409


def test_add_review_invalid_rating(client):
    owner = register(client, "owner@test.com")
    reviewer = register(client, "reviewer@test.com")
    trip_id = _create_trip(client, owner)

    r = client.post(f"/api/trips/{trip_id}/reviews",
                    json={"rating": 6},
                    headers=auth_headers(reviewer))
    assert r.status_code == 422


def test_add_review_trip_not_found(client):
    token = register(client)
    r = client.post("/api/trips/9999/reviews", json={"rating": 3}, headers=auth_headers(token))
    assert r.status_code == 404


def test_review_appears_in_list(client):
    owner = register(client, "owner@test.com")
    reviewer = register(client, "reviewer@test.com")
    trip_id = _create_trip(client, owner)

    client.post(f"/api/trips/{trip_id}/reviews", json={"rating": 5, "comment": "Excellent"},
                headers=auth_headers(reviewer))
    r = client.get(f"/api/trips/{trip_id}/reviews")
    assert len(r.json()) == 1
    assert r.json()[0]["rating"] == 5
