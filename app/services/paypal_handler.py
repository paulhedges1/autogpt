import json

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.services.contact_service import upsert_contact_from_paypal
from app.services.order_service import create_order_from_paypal

VERIFY_URL_SANDBOX = "https://api-m.sandbox.paypal.com/v1/notifications/verify-webhook-signature"
VERIFY_URL_LIVE = "https://api-m.paypal.com/v1/notifications/verify-webhook-signature"
TOKEN_URL_SANDBOX = "https://api-m.sandbox.paypal.com/v1/oauth2/token"
TOKEN_URL_LIVE = "https://api-m.paypal.com/v1/oauth2/token"


async def _get_access_token(settings) -> str:
    token_url = TOKEN_URL_SANDBOX if settings.PAYPAL_SANDBOX else TOKEN_URL_LIVE
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            token_url,
            data={"grant_type": "client_credentials"},
            auth=(settings.PAYPAL_CLIENT_ID, settings.PAYPAL_CLIENT_SECRET),
        )
    resp.raise_for_status()
    return resp.json()["access_token"]


async def verify_and_parse(payload: bytes, headers: dict, settings) -> dict:
    body = json.loads(payload)
    verify_url = VERIFY_URL_SANDBOX if settings.PAYPAL_SANDBOX else VERIFY_URL_LIVE

    access_token = await _get_access_token(settings)
    verify_payload = {
        "auth_algo": headers.get("paypal-auth-algo"),
        "cert_url": headers.get("paypal-cert-url"),
        "transmission_id": headers.get("paypal-transmission-id"),
        "transmission_sig": headers.get("paypal-transmission-sig"),
        "transmission_time": headers.get("paypal-transmission-time"),
        "webhook_id": settings.PAYPAL_WEBHOOK_ID,
        "webhook_event": body,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            verify_url,
            json=verify_payload,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if resp.json().get("verification_status") != "SUCCESS":
        raise HTTPException(status_code=400, detail="PayPal webhook verification failed")

    return body


async def dispatch(event: dict, db: Session) -> None:
    etype = event.get("event_type")

    if etype == "PAYMENT.SALE.COMPLETED":
        resource = event["resource"]
        contact = upsert_contact_from_paypal(db, resource)
        create_order_from_paypal(db, resource, contact.id)

    elif etype == "CUSTOMER.DISPUTE.CREATED":
        resource = event["resource"]
        _mark_disputed(db, resource)


def _mark_disputed(db: Session, resource: dict) -> None:
    from app.models.order import Order, OrderStatus

    txn_id = (resource.get("disputed_transactions") or [{}])[0].get(
        "seller_transaction_id"
    )
    if txn_id:
        order = db.query(Order).filter_by(provider_ref=txn_id).first()
        if order:
            order.status = OrderStatus.disputed
            db.commit()
