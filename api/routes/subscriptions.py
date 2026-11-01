import logging
import os
from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from godata.models import User
from godata.repos import SubscriptionRepo, TripRepo, ParcelRepo

from ..auth import require_user
from ..stripe_webhook import verify_stripe_event

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
PUBLIC_URL = os.environ.get("PUBLIC_URL", "https://jiblidz.com")

# Stripe Price IDs — set in environment
PRICE_IDS = {
    "starter": os.environ.get("STRIPE_PRICE_STARTER", ""),
    "voyageur": os.environ.get("STRIPE_PRICE_VOYAGEUR", ""),
    "pro": os.environ.get("STRIPE_PRICE_PRO", ""),
}

PLAN_QUOTAS = {
    "starter": 5,
    "voyageur": 20,
    "pro": None,  # unlimited
}


def get_user_subscription_info(user_id: int) -> dict:
    """Returns subscription status and remaining quota for a user."""
    sub = SubscriptionRepo.get_by_user(user_id)
    if not sub or sub.status not in ("active", "trialing"):
        return {"plan": None, "status": None, "quota": None, "used": None, "remaining": None}

    quota = PLAN_QUOTAS.get(sub.plan)
    if quota is None:
        return {"plan": sub.plan, "status": sub.status, "quota": None, "used": None, "remaining": None}

    # Count publications in current billing period
    period_start = sub.current_period_start
    trips_count = TripRepo.count_by_user_since(user_id, period_start)
    parcels_count = ParcelRepo.count_by_user_since(user_id, period_start)
    used = trips_count + parcels_count
    remaining = max(0, quota - used)

    return {
        "plan": sub.plan,
        "status": sub.status,
        "quota": quota,
        "used": used,
        "remaining": remaining,
        "period_end": sub.current_period_end.isoformat(),
    }


@router.get("/me")
def get_my_subscription(user: User = Depends(require_user)) -> dict:
    return get_user_subscription_info(user.id)


@router.post("/create-checkout")
def create_subscription_checkout(body: dict, user: User = Depends(require_user)) -> dict:
    plan = body.get("plan")
    if plan not in PRICE_IDS:
        raise HTTPException(status_code=400, detail="Plan invalide")

    price_id = PRICE_IDS[plan]
    if not price_id:
        raise HTTPException(status_code=500, detail="Plan non configuré")

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{PUBLIC_URL}/?subscription=success&plan={plan}",
            cancel_url=f"{PUBLIC_URL}/?subscription=cancelled",
            customer_email=user.email,
            metadata={"user_id": str(user.id), "plan": plan},
            # les métadonnées de la session ne passent pas à l'abonnement : le webhook en a besoin
            subscription_data={"metadata": {"user_id": str(user.id), "plan": plan}},
        )
        return {"checkout_url": session.url}
    except stripe.StripeError as e:
        log.error("Stripe subscription error: %s", e)
        raise HTTPException(status_code=502, detail="Erreur de paiement, réessayez.")


@router.post("/portal")
def customer_portal(user: User = Depends(require_user)) -> dict:
    sub = SubscriptionRepo.get_by_user(user.id)
    if not sub:
        raise HTTPException(status_code=404, detail="Aucun abonnement actif")
    try:
        session = stripe.billing_portal.Session.create(
            customer=sub.stripe_customer_id,
            return_url=f"{PUBLIC_URL}/",
        )
        return {"portal_url": session.url}
    except stripe.StripeError as e:
        log.error("Stripe portal error: %s", e)
        raise HTTPException(status_code=502, detail="Erreur portail Stripe")


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def subscription_webhook(request: Request) -> dict:
    event = verify_stripe_event(await request.body(), request.headers.get("stripe-signature", ""))

    event_type = event["type"]
    log.info("Subscription webhook event: %s", event_type)

    if event_type in ("customer.subscription.created", "customer.subscription.updated"):
        _handle_subscription_upsert(event["data"]["object"])
    elif event_type == "customer.subscription.deleted":
        sub = event["data"]["object"]
        SubscriptionRepo.delete_by_stripe_id(sub["id"])
        log.info("Subscription deleted: %s", sub["id"])

    return {"status": "ok"}


def _handle_subscription_upsert(sub: dict) -> None:
    user_id_str = sub.get("metadata", {}).get("user_id")
    if not user_id_str:
        # Try to find user by customer email
        log.warning("No user_id in subscription metadata: %s", sub["id"])
        return

    user_id = int(user_id_str)
    plan = sub.get("metadata", {}).get("plan", "starter")

    # Depuis l'API Stripe 2025-03 la période est sur l'item, plus sur l'abonnement
    item = (sub.get("items", {}).get("data") or [{}])[0]
    period_start = datetime.fromtimestamp(sub.get("current_period_start") or item["current_period_start"], tz=timezone.utc)
    period_end = datetime.fromtimestamp(sub.get("current_period_end") or item["current_period_end"], tz=timezone.utc)

    SubscriptionRepo.upsert(
        user_id=user_id,
        plan=plan,
        status=sub["status"],
        stripe_subscription_id=sub["id"],
        stripe_customer_id=sub["customer"],
        current_period_start=period_start,
        current_period_end=period_end,
    )
    log.info("Subscription upserted: user=%s plan=%s status=%s", user_id, plan, sub["status"])
