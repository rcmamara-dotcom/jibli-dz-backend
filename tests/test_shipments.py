"""Tests for /api/shipments (suivi d'envoi étape par étape)."""
from .conftest import register, auth_headers

TRIP = {"name": "Karim", "from_city": "Paris", "to_city": "Alger", "date": "2030-06-01", "capacity": "3", "wa": "+33612345678"}
STEPS = ["accepted", "picked_up", "in_transit", "arrived", "delivered"]


def _setup(client):
    carrier = auth_headers(register(client, "carrier@test.com"))
    sender = auth_headers(register(client, "sender@test.com"))
    trip_id = client.post("/api/trips", json=TRIP, headers=carrier).json()["id"]
    r = client.post("/api/shipments", json={"trip_id": trip_id, "description": "Médicaments 2 kg"}, headers=sender)
    assert r.status_code == 201, r.text
    return carrier, sender, r.json()


def test_create_shipment_starts_deposited(client):
    _, sender, s = _setup(client)
    assert s["status"] == "deposited"
    assert s["role"] == "sender"
    assert s["from_city"] == "Paris" and s["to_city"] == "Alger"
    assert [e["status"] for e in s["events"]] == ["deposited"]


def test_both_parties_see_shipment(client):
    carrier, sender, s = _setup(client)
    assert client.get("/api/shipments", headers=carrier).json()[0]["role"] == "carrier"
    assert client.get("/api/shipments", headers=sender).json()[0]["id"] == s["id"]
    other = auth_headers(register(client, "other@test.com"))
    assert client.get("/api/shipments", headers=other).json() == []


def test_cannot_ship_with_own_trip(client):
    carrier = auth_headers(register(client, "c@test.com"))
    trip_id = client.post("/api/trips", json=TRIP, headers=carrier).json()["id"]
    r = client.post("/api/shipments", json={"trip_id": trip_id, "description": "x"}, headers=carrier)
    assert r.status_code == 400


def test_unverified_sender_can_create(client):
    carrier = auth_headers(register(client, "c@test.com"))
    trip_id = client.post("/api/trips", json=TRIP, headers=carrier).json()["id"]
    nv = auth_headers(register(client, "nv@test.com", verified=False))
    assert client.post("/api/shipments", json={"trip_id": trip_id, "description": "x"}, headers=nv).status_code == 201


def test_carrier_walks_all_steps_in_order(client):
    carrier, sender, s = _setup(client)
    url = f"/api/shipments/{s['id']}/status"
    for step in STEPS:
        r = client.post(url, json={"status": step}, headers=carrier)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == step
    events = client.get("/api/shipments", headers=sender).json()[0]["events"]
    assert [e["status"] for e in events] == ["deposited"] + STEPS
    # terminé : plus rien ne bouge
    assert client.post(url, json={"status": "cancelled"}, headers=sender).status_code == 400


def test_cannot_skip_or_go_back(client):
    carrier, _, s = _setup(client)
    url = f"/api/shipments/{s['id']}/status"
    assert client.post(url, json={"status": "in_transit"}, headers=carrier).status_code == 400
    client.post(url, json={"status": "accepted"}, headers=carrier)
    assert client.post(url, json={"status": "deposited"}, headers=carrier).status_code == 400
    assert client.post(url, json={"status": "nimportequoi"}, headers=carrier).status_code == 400


def test_sender_cannot_advance(client):
    _, sender, s = _setup(client)
    r = client.post(f"/api/shipments/{s['id']}/status", json={"status": "accepted"}, headers=sender)
    assert r.status_code == 403


def test_stranger_gets_404(client):
    _, _, s = _setup(client)
    other = auth_headers(register(client, "other@test.com"))
    r = client.post(f"/api/shipments/{s['id']}/status", json={"status": "cancelled"}, headers=other)
    assert r.status_code == 404


def test_cancel_only_before_pickup(client):
    carrier, sender, s = _setup(client)
    url = f"/api/shipments/{s['id']}/status"
    client.post(url, json={"status": "accepted"}, headers=carrier)
    client.post(url, json={"status": "picked_up"}, headers=carrier)
    assert client.post(url, json={"status": "cancelled"}, headers=sender).status_code == 400


def test_sender_can_cancel_early(client):
    _, sender, s = _setup(client)
    r = client.post(f"/api/shipments/{s['id']}/status", json={"status": "cancelled"}, headers=sender)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"


def test_shipment_survives_trip_deletion(client):
    carrier, sender, s = _setup(client)
    assert client.delete(f"/api/trips/{s['trip_id']}", headers=carrier).status_code == 204
    kept = client.get("/api/shipments", headers=sender).json()[0]
    assert kept["trip_id"] is None and kept["to_city"] == "Alger"
