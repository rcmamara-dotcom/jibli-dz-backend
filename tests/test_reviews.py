"""Tests des notes de profil : /api/users/{id}/profile et /api/users/{id}/review."""
from godata.repos import UserRepo
from .conftest import register, auth_headers, TRIP_PAYLOAD


def _uid(email):
    return UserRepo.get_by_email(email).id


def _exchange(client, sender_token, owner_token):
    """sender contacte le trajet d'owner, owner répond : ils ont vraiment échangé."""
    trip_id = client.post("/api/trips", json=TRIP_PAYLOAD, headers=auth_headers(owner_token)).json()["id"]
    conv = client.post("/api/conversations", json={"trip_id": trip_id, "message": "Bonjour"},
                       headers=auth_headers(sender_token)).json()
    client.post(f"/api/conversations/{conv['id']}/messages", json={"content": "Salut"},
                headers=auth_headers(owner_token))
    return trip_id


def test_profile_empty(client):
    register(client, "owner@test.com")
    r = client.get(f"/api/users/{_uid('owner@test.com')}/profile")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 0 and data["avg"] is None and data["reviews"] == []
    assert data["can_review"] is False


def test_profile_not_found(client):
    assert client.get("/api/users/9999/profile").status_code == 404


def test_rate_after_exchange(client):
    owner = register(client, "owner@test.com")
    rater = register(client, "rater@test.com")
    _exchange(client, rater, owner)
    UserRepo.update_profile(_uid("rater@test.com"), name="Samira Lounes")

    target = _uid("owner@test.com")
    assert client.get(f"/api/users/{target}/profile", headers=auth_headers(rater)).json()["can_review"] is True
    r = client.put(f"/api/users/{target}/review", json={"rating": 4, "comment": " Super ! "},
                   headers=auth_headers(rater))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["avg"] == 4 and data["count"] == 1 and data["distribution"]["4"] == 1
    assert data["my_review"]["comment"] == "Super !"
    review = data["reviews"][0]
    assert review["reviewer_name"] == "Samira L."
    assert "rater@test.com" not in r.text, "jamais d'e-mail dans la réponse"


def test_rating_is_updated_not_duplicated(client):
    owner = register(client, "owner@test.com")
    rater = register(client, "rater@test.com")
    _exchange(client, rater, owner)
    target = _uid("owner@test.com")
    client.put(f"/api/users/{target}/review", json={"rating": 2}, headers=auth_headers(rater))
    data = client.put(f"/api/users/{target}/review", json={"rating": 5}, headers=auth_headers(rater)).json()
    assert data["count"] == 1 and data["avg"] == 5


def test_cannot_rate_without_exchange(client):
    owner = register(client, "owner@test.com")
    rater = register(client, "rater@test.com")
    trip_id = client.post("/api/trips", json=TRIP_PAYLOAD, headers=auth_headers(owner)).json()["id"]
    # message envoyé mais jamais de réponse : pas encore un échange
    client.post("/api/conversations", json={"trip_id": trip_id, "message": "Bonjour"}, headers=auth_headers(rater))
    r = client.put(f"/api/users/{_uid('owner@test.com')}/review", json={"rating": 1}, headers=auth_headers(rater))
    assert r.status_code == 403


def test_cannot_rate_self(client):
    token = register(client, "me@test.com")
    r = client.put(f"/api/users/{_uid('me@test.com')}/review", json={"rating": 5}, headers=auth_headers(token))
    assert r.status_code == 400


def test_rate_unauthenticated(client):
    register(client, "owner@test.com")
    assert client.put(f"/api/users/{_uid('owner@test.com')}/review", json={"rating": 3}).status_code == 401


def test_rate_invalid_rating(client):
    owner = register(client, "owner@test.com")
    rater = register(client, "rater@test.com")
    _exchange(client, rater, owner)
    for bad in (0, 6):
        r = client.put(f"/api/users/{_uid('owner@test.com')}/review", json={"rating": bad},
                       headers=auth_headers(rater))
        assert r.status_code == 422


def test_rating_shown_on_trips_and_survives_trip_deletion(client):
    owner = register(client, "owner@test.com")
    rater = register(client, "rater@test.com")
    trip_id = _exchange(client, rater, owner)
    target = _uid("owner@test.com")
    client.put(f"/api/users/{target}/review", json={"rating": 5}, headers=auth_headers(rater))

    trip = next(t for t in client.get("/api/trips").json() if t["id"] == trip_id)
    assert trip["avg_rating"] == 5 and trip["review_count"] == 1

    client.delete(f"/api/trips/{trip_id}", headers=auth_headers(owner))
    assert client.get(f"/api/users/{target}/profile").json()["count"] == 1, "la note suit la personne"


def test_delete_my_review(client):
    owner = register(client, "owner@test.com")
    rater = register(client, "rater@test.com")
    _exchange(client, rater, owner)
    target = _uid("owner@test.com")
    client.put(f"/api/users/{target}/review", json={"rating": 3}, headers=auth_headers(rater))
    assert client.delete(f"/api/users/{target}/review", headers=auth_headers(rater)).status_code == 204
    assert client.get(f"/api/users/{target}/profile").json()["count"] == 0
