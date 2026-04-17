from sqlalchemy.orm import Session

from app.models.contact import Contact, PipelineStage


def upsert_contact_from_stripe(db: Session, stripe_customer: dict) -> Contact:
    stripe_id = stripe_customer["id"]
    email = stripe_customer.get("email") or ""

    contact = db.query(Contact).filter_by(stripe_customer_id=stripe_id).first()
    if not contact and email:
        contact = db.query(Contact).filter_by(email=email).first()

    if contact:
        contact.stripe_customer_id = stripe_id
        if stripe_customer.get("name"):
            contact.full_name = stripe_customer["name"]
    else:
        contact = Contact(
            email=email or f"unknown+{stripe_id}@stripe.noemail",
            full_name=stripe_customer.get("name"),
            stripe_customer_id=stripe_id,
            stage=PipelineStage.lead,
        )
        db.add(contact)

    db.commit()
    db.refresh(contact)
    return contact


def upsert_contact_from_paypal(db: Session, resource: dict) -> Contact:
    payer_info = resource.get("payer_info") or resource.get("payer", {}).get("payer_info", {})
    payer_id = payer_info.get("payer_id", "")
    email = payer_info.get("email") or payer_info.get("email_address") or ""
    name = (
        payer_info.get("first_name", "") + " " + payer_info.get("last_name", "")
    ).strip() or None

    contact = None
    if payer_id:
        contact = db.query(Contact).filter_by(paypal_payer_id=payer_id).first()
    if not contact and email:
        contact = db.query(Contact).filter_by(email=email).first()

    if contact:
        if payer_id:
            contact.paypal_payer_id = payer_id
        if name:
            contact.full_name = contact.full_name or name
    else:
        contact = Contact(
            email=email or f"unknown+{payer_id}@paypal.noemail",
            full_name=name,
            paypal_payer_id=payer_id or None,
            stage=PipelineStage.lead,
        )
        db.add(contact)

    db.commit()
    db.refresh(contact)
    return contact
