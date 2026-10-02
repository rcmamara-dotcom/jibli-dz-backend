import json
import logging
import os

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from godata.models import User
from godata.repos import TripRepo, ParcelRepo

from ..auth import require_user
from ..schemas import TripIn, ParcelIn

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/payments", tags=["payments"])

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
PUBLIC_URL = os.environ.get("PUBLIC_URL", "https://jiblidz.com")
PRICE_CENTS = 500  # 5€


@router.post("/create-checkout")
def create_checkout(request: Request, body: dict, user: User = Depends(require_user)) -> dict:
    listing_type = body.get("type")  # "trip" or "parcel"
    if listing_type not in ("trip", "parcel"):
        raise HTTPException(status_code=400, detail="Type invalide")

    # Validate form data before creating session
    try:
        if listing_type == "trip":
            TripIn(**body.get("data", {}))
        else:
            ParcelIn(**body.get("data", {}))
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Stripe metadata is limited to 500 chars per value
    data_json = json.dumps(body.get("data", {}), ensure_ascii=False)

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "eur",
                    "unit_amount": PRICE_CENTS,
                    "product_data": {
                        "name": f"Publication annonce {'Trajet' if listing_type == 'trip' else 'Colis'} - Jibli DZ",
                        "description": "Votre annonce sera publiee immediatement apres le paiement.",
                    },
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=f"{PUBLIC_URL}/?payment=success&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{PUBLIC_URL}/?payment=cancelled",
            metadata={
                "type": listing_type,
                "user_id": str(user.id),
                "data": data_json[:500],  # Stripe metadata value limit
            },
            customer_email=user.email,
        )
        log.info("Stripe session created: %s user_id=%s type=%s", session.id, user.id, listing_type)
        return {"checkout_url": session.url, "session_id": session.id}
    except stripe.StripeError as e:
        log.error("Stripe error: %s", e)
        raise HTTPException(status_code=502, detail="Erreur de paiement, réessayez.")


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook(request: Request) -> dict:
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        if STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
        else:
            event = stripe.Event.construct_from(json.loads(payload), stripe.api_key)
    except (ValueError, stripe.SignatureVerificationError) as e:
        log.warning("Webhook signature invalid: %s", e)
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        _handle_payment_success(session)

    return {"status": "ok"}


def _handle_payment_success(session: dict) -> None:
    meta = session.get("metadata", {})
    listing_type = meta.get("type")
    user_id = int(meta.get("user_id", 0))
    data_json = meta.get("data", "{}")

    try:
        data = json.loads(data_json)
    except json.JSONDecodeError:
        log.error("Invalid JSON in session metadata: %s", data_json)
        return

    try:
        if listing_type == "trip":
            trip = TripRepo.create(owner_id=user_id, **TripIn(**data).model_dump())
            log.info("Trip created via payment: id=%s user_id=%s", trip.id, user_id)
        elif listing_type == "parcel":
            parcel = ParcelRepo.create(owner_id=user_id, **ParcelIn(**data).model_dump())
            log.info("Parcel created via payment: id=%s user_id=%s", parcel.id, user_id)
        else:
            log.warning("Unknown listing type in webhook: %s", listing_type)
    except Exception as e:
        log.exception("Error creating listing from webhook: %s", e)
