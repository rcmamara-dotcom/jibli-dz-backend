"""Tests for /api/auth routes."""
import pytest
from unittest.mock import patch
from .conftest import register, auth_headers


def test_register_success(client):
    r = client.post("/api/auth/register", json={"email": "a@test.com", "password": "password1"})
    assert r.status_code == 201
    assert "access_token" in r.json()


def test_register_duplicate_email(client):
    client.post("/api/auth/register", json={"email": "dup@test.com", "password": "password1"})
    r = client.post("/api/auth/register", json={"email": "dup@test.com", "password": "password1"})
    assert r.status_code == 400
    assert "déjà utilisé" in r.json()["detail"]


def test_login_success(client):
    client.post("/api/auth/register", json={"email": "u@test.com", "password": "mypassword"})
    r = client.post("/api/auth/login", json={"email": "u@test.com", "password": "mypassword"})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_login_wrong_password(client):
    client.post("/api/auth/register", json={"email": "u@test.com", "password": "mypassword"})
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
