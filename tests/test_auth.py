"""Tests for /api/auth routes."""
import pytest
from unittest.mock import patch
from .conftest import register, auth_headers


def test_register_success(client):
    token = register(client, "a@test.com", "password1")
    assert token


def test_register_duplicate_email(client):
    register(client, "dup@test.com", "password1")
    r = client.post("/api/auth/register", json={
        "email": "dup@test.com", "phone": "+33612345678", "password": "password1", "confirm_password": "password1",
    })
    assert r.status_code == 400
    assert "déjà utilisé" in r.json()["detail"]


def test_login_success(client):
    register(client, "u@test.com", "mypassword")
    r = client.post("/api/auth/login", json={"email": "u@test.com", "password": "mypassword"})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_login_wrong_password(client):
    register(client, "u@test.com", "mypassword")
    r = client.post("/api/auth/login", json={"email": "u@test.com", "password": "wrongpass"})
    assert r.status_code == 401


def test_login_unknown_email(client):
    r = client.post("/api/auth/login", json={"email": "ghost@test.com", "password": "whatever"})
    assert r.status_code == 401


def test_forgot_password_always_204(client):
    # Returns 204 even for unknown emails (anti-enumeration)
    r = client.post("/api/auth/forgot-password", json={"email": "ghost@test.com"})
    assert r.status_code == 204


def test_forgot_password_known_email_sends_email(client):
    register(client, "real@test.com")
    with patch("api.routes.auth._send") as mock_send:
        r = client.post("/api/auth/forgot-password", json={"email": "real@test.com"})
    assert r.status_code == 204
    mock_send.assert_called_once()
    args = mock_send.call_args[0]
    assert args[0] == "real@test.com"
    assert "reset" in args[2]  # HTML contains reset link


def test_reset_password_invalid_token(client):
    r = client.post("/api/auth/reset-password", json={"token": "bad-token", "password": "newpass123"})
    assert r.status_code == 400


def test_reset_password_full_flow(client):
    register(client, "reset@test.com", "oldpassword")
    from api.reset_tokens import generate
    token = generate("reset@test.com")

    r = client.post("/api/auth/reset-password", json={"token": token, "password": "newpassword"})
    assert r.status_code == 204

    # Old password no longer works
    r = client.post("/api/auth/login", json={"email": "reset@test.com", "password": "oldpassword"})
    assert r.status_code == 401

    # New password works
    r = client.post("/api/auth/login", json={"email": "reset@test.com", "password": "newpassword"})
    assert r.status_code == 200


def test_reset_token_consumed_after_use(client):
    register(client, "once@test.com")
    from api.reset_tokens import generate
    token = generate("once@test.com")

    client.post("/api/auth/reset-password", json={"token": token, "password": "newpass1"})
    # Second use must fail
    r = client.post("/api/auth/reset-password", json={"token": token, "password": "newpass2"})
    assert r.status_code == 400


# ── Inscription : téléphone, double mot de passe, code e-mail ─────────────────

def _register_body(**over):
    body = {"email": "new@test.com", "phone": "+33 6 12 34 56 78", "password": "secret123", "confirm_password": "secret123"}
    body.update(over)
    return body


def test_register_requires_phone(client):
    body = _register_body()
    del body["phone"]
    assert client.post("/api/auth/register", json=body).status_code == 422


def test_register_rejects_invalid_phone(client):
    assert client.post("/api/auth/register", json=_register_body(phone="0612345678")).status_code == 422


def test_register_password_mismatch(client):
    r = client.post("/api/auth/register", json=_register_body(confirm_password="other123"))
    assert r.status_code == 422


def test_register_then_verify_email(client):
    from api import email_codes
    r = client.post("/api/auth/register", json=_register_body())
    assert r.status_code == 201
    h = auth_headers(r.json()["access_token"])
    me = client.get("/api/auth/me", headers=h).json()
    assert me["phone"] == "+33612345678"
    assert me["email_verified"] is False

    assert client.post("/api/auth/verify-email", json={"code": "000000"}, headers=h).status_code in (400, 200)
    code = email_codes._store[me["id"]][1]
    r = client.post("/api/auth/verify-email", json={"code": code}, headers=h)
    assert r.status_code == 200
    assert r.json()["email_verified"] is True


def test_verification_code_attempts_limited(client):
    from api import email_codes
    r = client.post("/api/auth/register", json=_register_body())
    h = auth_headers(r.json()["access_token"])
    uid = client.get("/api/auth/me", headers=h).json()["id"]
    code = email_codes._store[uid][1]
    wrong = "111111" if code != "111111" else "222222"
    for _ in range(5):
        client.post("/api/auth/verify-email", json={"code": wrong}, headers=h)
    assert client.post("/api/auth/verify-email", json={"code": code}, headers=h).status_code == 400


def test_unverified_user_can_publish(client):
    # La vérification e-mail est facultative : elle ne bloque pas la publication
    token = register(client, "nv@test.com", verified=False)
    r = client.post("/api/trips", headers=auth_headers(token), json={
        "name": "A", "from_city": "Paris", "to_city": "Alger", "date": "2030-01-01", "capacity": "2", "wa": "+33612345678",
    })
    assert r.status_code == 201


def test_update_me(client):
    h = auth_headers(register(client))
    r = client.patch("/api/auth/me", headers=h, json={"name": "Sam", "birth_date": "1990-05-01"})
    assert r.status_code == 200
    assert r.json()["name"] == "Sam" and r.json()["birth_date"] == "1990-05-01"
    assert r.json()["phone"] == "+33612345678"   # non envoyé = inchangé
    r = client.patch("/api/auth/me", headers=h, json={"birth_date": None})
    assert r.json()["birth_date"] is None
    assert client.patch("/api/auth/me", headers=h, json={"phone": None}).status_code == 422


def test_change_email_needs_password_and_reverification(client):
    h = auth_headers(register(client, "old@test.com", "secret123"))
    bad = client.post("/api/auth/change-email", headers=h, json={"new_email": "n@test.com", "password": "nope"})
    assert bad.status_code == 400
    r = client.post("/api/auth/change-email", headers=h, json={"new_email": "n@test.com", "password": "secret123"})
    assert r.status_code == 200
    assert r.json()["email"] == "n@test.com" and r.json()["email_verified"] is False


def test_old_google_account_gets_verified_on_login(client):
    """Compte Google créé avant la vérification e-mail : vérifié à la connexion, sans code."""
    from godata.models import User
    User.create(email="g@gmail.com", password_hash="", google_id="gid-1", email_verified=False)
    claims = {"uid": "gid-1", "email": "g@gmail.com", "name": "G"}
    with patch("api.routes.auth.verify_google_token", return_value=claims):
        r = client.post("/api/auth/google", json={"id_token": "x"})
    assert r.status_code == 200
    me = client.get("/api/auth/me", headers=auth_headers(r.json()["access_token"])).json()
    assert me["email_verified"] is True
