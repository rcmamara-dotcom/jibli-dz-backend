import json
import logging
import os

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from godata.models import User
from godata.repos import TripRepo, ParcelRepo

from ..auth import require_user
from ..permissions import can
from ..stripe_webhook import verify_stripe_event
from ..schemas import TripIn, ParcelIn
from ..limiter import limiter
from pydantic import ValidationError
from .subscriptions import get_user_subscription_info

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/payments", tags=["payments"])

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
PUBLIC_URL = os.environ.get("PUBLIC_URL", "https://jiblidz.com")
PRICE_CENTS = 300  # 3€


@router.post("/create-checkout")
@limiter.limit("20/hour")
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
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors()[0]["msg"])

    # Publication directe : rôle avec publication gratuite, ou abonnement avec quota restant
    sub_info = get_user_subscription_info(user.id)
    free = can(user, "publish_free")
    if free or (sub_info["plan"] and sub_info["status"] in ("active", "trialing")):
        remaining = None if free else sub_info.get("remaining")
        if remaining is None or remaining > 0:
            data = body.get("data", {})
            try:
                if listing_type == "trip":
                    trip_data = TripIn(**data)
                    TripRepo.create(owner_id=user.id, **trip_data.model_dump())
                else:
                    parcel_data = ParcelIn(**data)
                    ParcelRepo.create(owner_id=user.id, **parcel_data.model_dump())
            except Exception:
                log.exception("Publication directe impossible: user=%s", user.id)
                raise HTTPException(status_code=500, detail="Publication impossible, réessaie plus tard")
            log.info("Publication directe: user=%s role=%s plan=%s type=%s", user.id, user.role, sub_info["plan"], listing_type)
            return {"published": True, "checkout_url": None}

    # Stripe limite chaque valeur de métadonnée à 500 caractères : on découpe le JSON
    data_json = json.dumps(body.get("data", {}), ensure_ascii=False)
    chunks = {f"data{i}": data_json[i * 500:(i + 1) * 500] for i in range((len(data_json) + 499) // 500)}

    try:
        session = stripe.checkout.Session.create(
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
                **chunks,
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
    event = verify_stripe_event(await request.body(), request.headers.get("stripe-signature", ""))

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        _handle_payment_success(session)

    return {"status": "ok"}


def _handle_payment_success(session: dict) -> None:
    meta = session.get("metadata", {})
    listing_type = meta.get("type")
    user_id = int(meta.get("user_id", 0))
    # "data" seul : sessions créées avant le découpage
    data_json = meta.get("data") or "".join(meta.get(f"data{i}", "") for i in range(50)) or "{}"

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
