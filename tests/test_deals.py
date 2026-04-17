def test_create_and_list_deal(client, auth_headers):
    cid = client.post("/api/contacts/", json={"email": "deal@example.com"}, headers=auth_headers).json()["id"]
    resp = client.post(
        "/api/deals/",
        json={"contact_id": cid, "title": "Big Deal", "value": 5000.0, "stage": "prospect"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["title"] == "Big Deal"
    assert resp.json()["stage"] == "prospect"


def test_advance_deal_stage(client, auth_headers):
    cid = client.post("/api/contacts/", json={"email": "deal2@example.com"}, headers=auth_headers).json()["id"]
    did = client.post(
        "/api/deals/",
        json={"contact_id": cid, "title": "Advance Me"},
        headers=auth_headers,
    ).json()["id"]
    resp = client.patch(f"/api/deals/{did}", json={"stage": "customer"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["stage"] == "customer"
