import stripe
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.services.contact_service import upsert_contact_from_stripe
from app.services.order_service import create_order_from_stripe


def verify_and_parse(payload: bytes, sig_header: str, secret: str) -> dict:
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, secret)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")
    return event


def dispatch(event: dict, db: Session) -> None:
    etype = event["type"]
    data = event["data"]["object"]

    if etype in ("customer.created", "customer.updated"):
        upsert_contact_from_stripe(db, data)
    elif etype == "payment_intent.succeeded":
        create_order_from_stripe(db, data)
