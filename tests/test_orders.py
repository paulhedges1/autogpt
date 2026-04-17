def _make_contact(client, headers, email="order_test@example.com"):
    resp = client.post("/api/contacts/", json={"email": email}, headers=headers)
    return resp.json()["id"]


def test_create_and_list_order(client, auth_headers):
    cid = _make_contact(client, auth_headers)
    resp = client.post(
        "/api/orders/",
        json={"contact_id": cid, "provider": "manual", "amount": 99.99, "currency": "GBP"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["amount"] == 99.99
    assert data["currency"] == "GBP"


def test_update_order_status(client, auth_headers):
    cid = _make_contact(client, auth_headers, "order_upd@example.com")
    oid = client.post(
        "/api/orders/",
        json={"contact_id": cid, "provider": "stripe", "amount": 50.0},
        headers=auth_headers,
    ).json()["id"]
    resp = client.patch(f"/api/orders/{oid}", json={"status": "refunded"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "refunded"
