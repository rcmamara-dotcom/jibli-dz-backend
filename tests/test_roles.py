"""Système de droits : rôles, publication gratuite, gestion des rôles, création d'admin."""
from unittest.mock import patch, MagicMock
from godata.models import User
from godata.repos import UserRepo
from .conftest import register, auth_headers, TRIP_PAYLOAD


def _set_role(email: str, role: str):
    UserRepo.set_role(UserRepo.get_by_email(email).id, role)


def _checkout(client, headers):
    fake = MagicMock(id="cs_test", url="https://checkout.stripe.test/x")
    with patch("api.routes.payments.stripe.checkout.Session.create", return_value=fake) as create:
        r = client.post("/api/payments/create-checkout", json={"type": "trip", "data": TRIP_PAYLOAD}, headers=headers)
    return r, create


def test_normal_user_must_pay(client):
    r, create = _checkout(client, auth_headers(register(client, "u@test.com")))
    assert r.status_code == 200
    assert r.json()["checkout_url"] and not r.json().get("published")
    create.assert_called_once()


def test_vip_and_admin_publish_free(client):
    for i, role in enumerate(["vip", "moderator", "admin"]):
        email = f"{role}@test.com"
        h = auth_headers(register(client, email))
        _set_role(email, role)
        r, create = _checkout(client, h)
        assert r.json() == {"published": True, "checkout_url": None}, role
        create.assert_not_called()
    assert len(client.get("/api/trips").json()) == 3


def test_role_in_me_and_token(client):
    h = auth_headers(register(client, "a@test.com"))
    _set_role("a@test.com", "admin")
    me = client.get("/api/auth/me", headers=h).json()
    assert me["role"] == "admin" and me["is_admin"] is True


def test_admin_changes_roles(client):
    admin = auth_headers(register(client, "admin@test.com"))
    _set_role("admin@test.com", "admin")
    register(client, "u@test.com")
    uid = UserRepo.get_by_email("u@test.com").id
    r = client.patch(f"/api/admin/users/{uid}/role", json={"role": "vip"}, headers=admin)
    assert r.status_code == 200 and r.json()["role"] == "vip"
    assert client.patch(f"/api/admin/users/{uid}/role", json={"role": "dieu"}, headers=admin).status_code == 422
    me_id = UserRepo.get_by_email("admin@test.com").id
    assert client.patch(f"/api/admin/users/{me_id}/role", json={"role": "user"}, headers=admin).status_code == 400


def test_moderator_moderates_but_cannot_manage_users(client):
    mod = auth_headers(register(client, "mod@test.com"))
    _set_role("mod@test.com", "moderator")
    owner = auth_headers(register(client, "owner@test.com"))
    trip_id = client.post("/api/trips", json=TRIP_PAYLOAD, headers=owner).json()["id"]
    assert client.get("/api/admin/stats", headers=mod).status_code == 200
    assert client.delete(f"/api/admin/trips/{trip_id}", headers=mod).status_code == 204
    assert client.get("/api/admin/users", headers=mod).status_code == 403
    uid = UserRepo.get_by_email("owner@test.com").id
    assert client.patch(f"/api/admin/users/{uid}/role", json={"role": "admin"}, headers=mod).status_code == 403


def test_vip_has_no_admin_access(client):
    vip = auth_headers(register(client, "vip@test.com"))
    _set_role("vip@test.com", "vip")
    assert client.get("/api/admin/stats", headers=vip).status_code == 403


def test_create_admin_script_new_and_existing(fresh_db):
    from api import create_admin
    with patch("api.create_admin.init_db"), patch("api.create_admin.getpass.getpass", side_effect=["motdepasse1", "motdepasse1"]):
        assert create_admin.main(["x", "boss@test.com"]) == 0
    boss = UserRepo.get_by_email("boss@test.com")
    assert boss.role == "admin" and boss.is_admin and boss.email_verified
    # compte existant : promu sans redemander de mot de passe
    User.create(email="old@test.com", password_hash="h")
    with patch("api.create_admin.init_db"), patch("api.create_admin.getpass.getpass") as gp:
        assert create_admin.main(["x", "old@test.com"]) == 0
        gp.assert_not_called()
    assert UserRepo.get_by_email("old@test.com").role == "admin"


def test_create_admin_rejects_short_password(fresh_db):
    from api import create_admin
    with patch("api.create_admin.init_db"), patch("api.create_admin.getpass.getpass", return_value="court"):
        assert create_admin.main(["x", "boss@test.com"]) == 1
    assert UserRepo.get_by_email("boss@test.com") is None
