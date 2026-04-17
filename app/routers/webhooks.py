from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.dependencies import get_db
from app.services import stripe_handler, paypal_handler

router = APIRouter()


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(..., alias="stripe-signature"),
    db: Session = Depends(get_db),
):
    payload = await request.body()
    settings = get_settings()

    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Stripe webhook secret not configured")

    event = stripe_handler.verify_and_parse(payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET)
    stripe_handler.dispatch(event, db)
    return {"status": "ok"}


@router.post("/paypal")
async def paypal_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    payload = await request.body()
    headers = dict(request.headers)
    settings = get_settings()

    event = await paypal_handler.verify_and_parse(payload, headers, settings)
    await paypal_handler.dispatch(event, db)
    return {"status": "ok"}
