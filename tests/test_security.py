"""Non-régression des corrections de sécurité (audit du 1er novembre 2026)."""
import hashlib
import hmac
import json
import time
from unittest.mock import MagicMock, patch

from godata.repos import UserRepo
from .conftest import register, auth_headers, TRIP_PAYLOAD

SECRET = "whsec_test"


def _signed(payload: dict) -> tuple[bytes, dict]:
    body = json.dumps(payload).encode()
    ts = str(int(time.time()))
    sig = hmac.new(SECRET.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return body, {"stripe-signature": f"t={ts},v1={sig}", "content-type": "application/json"}


def _paid_session(user_id: int, data: dict) -> dict:
    data_json = json.dumps(data)
    chunks = {f"data{i}": data_json[i * 500:(i + 1) * 500] for i in range((len(data_json) + 499) // 500)}
    return {"type": "checkout.session.completed",
            "data": {"object": {"metadata": {"type": "trip", "user_id": str(user_id), **chunks}}}}


def test_webhook_refused_without_secret(client):
    register(client, "u@test.com")
    uid = UserRepo.get_by_email("u@test.com").id
    with patch("api.stripe_webhook.STRIPE_WEBHOOK_SECRET", ""):
        r = client.post("/api/payments/webhook", json=_paid_session(uid, TRIP_PAYLOAD))
    assert r.status_code == 400
    assert client.get("/api/trips").json() == []


def test_webhook_refused_with_bad_signature(client):
    register(client, "u@test.com")
    uid = UserRepo.get_by_email("u@test.com").id
    body, headers = _signed(_paid_session(uid, TRIP_PAYLOAD))
    headers["stripe-signature"] = headers["stripe-signature"][:-4] + "beef"
    with patch("api.stripe_webhook.STRIPE_WEBHOOK_SECRET", SECRET):
        r = client.post("/api/payments/webhook", content=body, headers=headers)
    assert r.status_code == 400


def test_signed_webhook_publishes_long_listing(client):
    """Signature valide → annonce créée, même avec une description > 500 caractères."""
    register(client, "u@test.com")
    uid = UserRepo.get_by_email("u@test.com").id
    data = {**TRIP_PAYLOAD, "cap_desc": "x" * 900}
    body, headers = _signed(_paid_session(uid, data))
    with patch("api.stripe_webhook.STRIPE_WEBHOOK_SECRET", SECRET):
        r = client.post("/api/payments/webhook", content=body, headers=headers)
    assert r.status_code == 200
    trips = client.get("/api/trips").json()
    assert len(trips) == 1 and trips[0]["cap_desc"] == "x" * 900 and trips[0]["owner_id"] == uid


def test_checkout_splits_metadata(client):
    h = auth_headers(register(client, "u@test.com", role="user"))
    fake = MagicMock(id="cs", url="https://checkout.stripe.test")
    data = {**TRIP_PAYLOAD, "cap_desc": "é" * 900}
    with patch("api.routes.payments.stripe.checkout.Session.create", return_value=fake) as create:
        assert client.post("/api/payments/create-checkout", json={"type": "trip", "data": data}, headers=h).status_code == 200
    meta = create.call_args.kwargs["metadata"]
    assert all(len(v) <= 500 for v in meta.values())
    assert json.loads("".join(meta[f"data{i}"] for i in range(10) if f"data{i}" in meta)) == data


def test_field_too_long_rejected_cleanly(client):
    h = auth_headers(register(client, "u@test.com"))
    r = client.post("/api/payments/create-checkout", json={"type": "trip", "data": {**TRIP_PAYLOAD, "from_city": "A" * 5000}}, headers=h)
    assert r.status_code == 422
    assert "psycopg" not in r.text and "Traceback" not in r.text


def test_password_min_8(client):
    body = {"email": "w@test.com", "phone": "+33612345678", "password": "1234567", "confirm_password": "1234567"}
    assert client.post("/api/auth/register", json=body).status_code == 422


def test_email_html_is_escaped():
    from api.routes import shipments
    s = MagicMock(from_city="<b>Paris</b>", to_city="<script>x</script>", status="accepted")
    with patch.object(shipments.UserRepo, "get_by_id", return_value=MagicMock(email="a@b.c")), \
         patch.object(shipments, "_send") as send:
        shipments._notify(s, 1)
    html = send.call_args.args[2]
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_subject_has_no_newlines():
    from api import scheduler
    with patch.dict("os.environ", {"SMTP_HOST": "h", "SMTP_USER": "u"}), \
         patch("api.scheduler.smtplib.SMTP_SSL") as smtp:
        scheduler._send("a@b.c", "Bonjour\r\nBcc: victime@x.fr", "<p>x</p>")
    sent = smtp.return_value.__enter__.return_value.sendmail.call_args.args[2]
    assert "\nBcc: victime" not in sent
