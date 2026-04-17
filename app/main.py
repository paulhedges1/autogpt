from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import SessionLocal
from app.routers import auth, contacts, deals, notes, orders, webhooks, admin
from app.services.auth_service import seed_admin

app = FastAPI(title="CRM System", version="1.0.0")

app.mount("/static", StaticFiles(directory="static"), name="static")

# API routes (JWT-protected)
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(contacts.router, prefix="/api/contacts", tags=["Contacts"])
app.include_router(orders.router, prefix="/api/orders", tags=["Orders"])
app.include_router(notes.router, prefix="/api/notes", tags=["Notes"])
app.include_router(deals.router, prefix="/api/deals", tags=["Deals"])

# Webhook routes (signature-verified, no JWT)
app.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])

# Admin UI (cookie-session-protected)
app.include_router(auth.router, prefix="", tags=["Admin Auth"])
app.include_router(admin.router, prefix="/admin", tags=["Admin UI"])


@app.on_event("startup")
def on_startup():
    db = SessionLocal()
    try:
        seed_admin(db)
    finally:
        db.close()
