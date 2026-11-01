import json
import logging
import os

import stripe
from fastapi import HTTPException

log = logging.getLogger(__name__)
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")


def verify_stripe_event(payload: bytes, sig_header: str) -> dict:
    """Vérifie la signature Stripe et renvoie l'événement en dict.

    Sans secret configuré on refuse tout : sinon n'importe qui pourrait
    simuler un paiement. Le dict (et non le StripeObject) car les versions
    récentes de stripe-python n'ont plus .get().
    """
    if not STRIPE_WEBHOOK_SECRET:
        log.error("STRIPE_WEBHOOK_SECRET manquant : webhook refusé")
        raise HTTPException(status_code=400, detail="Webhook non configuré")
    try:
        stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.SignatureVerificationError) as e:
        log.warning("Webhook signature invalid: %s", e)
        raise HTTPException(status_code=400, detail="Invalid signature")
    return json.loads(payload)
