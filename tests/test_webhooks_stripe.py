import hashlib
import hmac
import json
import time
from unittest.mock import MagicMock, patch

SECRET = "whsec_test_secret_key_for_testing"


def _make_sig(payload: bytes) -> str:
    timestamp = int(time.time())
    signed_payload = f"{timestamp}.".encode() + payload
    sig = hmac.new(SECRET.encode(), signed_payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={sig}"


def _post(client, payload: dict):
    body = json.dumps(payload).encode()
    sig = _make_sig(body)
    mock_settings = MagicMock()
    mock_settings.STRIPE_WEBHOOK_SECRET = SECRET
    with patch("app.routers.webhooks.get_settings", return_value=mock_settings):
        return client.post(
            "/webhooks/stripe",
            content=body,
            headers={"stripe-signature": sig, "content-type": "application/json"},
        )


def test_customer_created(client, auth_headers):
    payload = {
        "id": "evt_001",
        "type": "customer.created",
        "data": {
            "object": {
                "id": "cus_test_002",
                "email": "stripe_webhook_test@example.com",
                "name": "Stripe Webhook User",
            }
        },
    }
    resp = _post(client, payload)
    assert resp.status_code == 200

    contacts = client.get("/api/contacts/", headers=auth_headers).json()
    assert any(c["stripe_customer_id"] == "cus_test_002" for c in contacts)


def test_payment_intent_succeeded(client, auth_headers):
    payload = {
        "id": "evt_002",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": "pi_test_webhook_001",
                "amount": 4999,
                "currency": "usd",
                "customer": None,
                "description": "Test payment",
            }
        },
    }
    resp = _post(client, payload)
    assert resp.status_code == 200

    orders = client.get("/api/orders/", headers=auth_headers).json()
    assert any(o["provider_ref"] == "pi_test_webhook_001" for o in orders)


def test_invalid_signature(client):
    body = json.dumps({"id": "evt_bad", "type": "customer.created", "data": {"object": {}}}).encode()
    mock_settings = MagicMock()
    mock_settings.STRIPE_WEBHOOK_SECRET = SECRET
    with patch("app.routers.webhooks.get_settings", return_value=mock_settings):
        resp = client.post(
            "/webhooks/stripe",
            content=body,
            headers={"stripe-signature": "t=bad,v1=bad", "content-type": "application/json"},
        )
    assert resp.status_code == 400
