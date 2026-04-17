import json
from unittest.mock import AsyncMock, patch


def _paypal_post(client, body: dict):
    raw = json.dumps(body).encode()
    with patch(
        "app.routers.webhooks.paypal_handler.verify_and_parse",
        new_callable=AsyncMock,
        return_value=body,
    ):
        return client.post(
            "/webhooks/paypal",
            content=raw,
            headers={"content-type": "application/json"},
        )


def test_sale_completed(client, auth_headers):
    body = {
        "event_type": "PAYMENT.SALE.COMPLETED",
        "resource": {
            "id": "SALE_PP_001",
            "amount": {"total": "79.99", "currency": "USD"},
            "payer_info": {
                "email": "paypal_buyer@example.com",
                "payer_id": "PPID001",
                "first_name": "Pay",
                "last_name": "Pal",
            },
        },
    }
    resp = _paypal_post(client, body)
    assert resp.status_code == 200

    contacts = client.get("/api/contacts/", headers=auth_headers).json()
    assert any(c["paypal_payer_id"] == "PPID001" for c in contacts)

    orders = client.get("/api/orders/", headers=auth_headers).json()
    assert any(o["provider_ref"] == "SALE_PP_001" for o in orders)


def test_dispute_marks_order(client, auth_headers):
    # Create an order to dispute
    cid = client.post("/api/contacts/", json={"email": "dispute@example.com"}, headers=auth_headers).json()["id"]
    client.post(
        "/api/orders/",
        json={"contact_id": cid, "provider": "paypal", "provider_ref": "TXN_DISPUTE_001", "amount": 50.0},
        headers=auth_headers,
    )

    body = {
        "event_type": "CUSTOMER.DISPUTE.CREATED",
        "resource": {
            "disputed_transactions": [{"seller_transaction_id": "TXN_DISPUTE_001"}]
        },
    }
    resp = _paypal_post(client, body)
    assert resp.status_code == 200

    orders = client.get("/api/orders/", headers=auth_headers).json()
    disputed = [o for o in orders if o["provider_ref"] == "TXN_DISPUTE_001"]
    assert disputed[0]["status"] == "disputed"
