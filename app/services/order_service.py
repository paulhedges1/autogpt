from sqlalchemy.orm import Session

from app.models.order import Order, OrderStatus, PaymentProvider
from app.services.contact_service import upsert_contact_from_stripe


def create_order_from_stripe(db: Session, payment_intent: dict) -> Order:
    provider_ref = payment_intent["id"]

    existing = db.query(Order).filter_by(provider_ref=provider_ref).first()
    if existing:
        return existing

    contact_id: int | None = None
    stripe_customer = payment_intent.get("customer")
    if isinstance(stripe_customer, dict):
        contact = upsert_contact_from_stripe(db, stripe_customer)
        contact_id = contact.id
    elif isinstance(stripe_customer, str) and stripe_customer:
        from app.models.contact import Contact
        contact = db.query(Contact).filter_by(stripe_customer_id=stripe_customer).first()
        if contact:
            contact_id = contact.id

    if contact_id is None:
        from app.models.contact import Contact
        placeholder = Contact(
            email=f"unknown+{provider_ref}@stripe.noemail",
            stage="lead",
        )
        db.add(placeholder)
        db.flush()
        contact_id = placeholder.id

    amount = payment_intent.get("amount", 0) / 100
    currency = (payment_intent.get("currency") or "usd").upper()
    description = payment_intent.get("description")

    order = Order(
        contact_id=contact_id,
        provider=PaymentProvider.stripe,
        provider_ref=provider_ref,
        amount=amount,
        currency=currency,
        status=OrderStatus.completed,
        description=description,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def create_order_from_paypal(db: Session, resource: dict, contact_id: int) -> Order:
    provider_ref = resource.get("id", "")

    existing = db.query(Order).filter_by(provider_ref=provider_ref).first()
    if existing:
        return existing

    amount_obj = resource.get("amount", {})
    try:
        amount = float(amount_obj.get("total", 0))
    except (TypeError, ValueError):
        amount = 0.0
    currency = (amount_obj.get("currency") or "USD").upper()

    order = Order(
        contact_id=contact_id,
        provider=PaymentProvider.paypal,
        provider_ref=provider_ref,
        amount=amount,
        currency=currency,
        status=OrderStatus.completed,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order
