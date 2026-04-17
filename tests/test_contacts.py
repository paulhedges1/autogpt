def test_create_and_list_contact(client, auth_headers):
    resp = client.post(
        "/api/contacts/",
        json={"email": "alice@example.com", "full_name": "Alice", "stage": "lead"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "alice@example.com"
    assert data["stage"] == "lead"

    resp = client.get("/api/contacts/", headers=auth_headers)
    assert resp.status_code == 200
    assert any(c["email"] == "alice@example.com" for c in resp.json())


def test_duplicate_email_returns_409(client, auth_headers):
    client.post("/api/contacts/", json={"email": "dup@example.com"}, headers=auth_headers)
    resp = client.post("/api/contacts/", json={"email": "dup@example.com"}, headers=auth_headers)
    assert resp.status_code == 409


def test_update_contact(client, auth_headers):
    resp = client.post("/api/contacts/", json={"email": "bob@example.com"}, headers=auth_headers)
    cid = resp.json()["id"]

    resp = client.patch(f"/api/contacts/{cid}", json={"stage": "customer"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["stage"] == "customer"


def test_delete_contact(client, auth_headers):
    resp = client.post("/api/contacts/", json={"email": "del@example.com"}, headers=auth_headers)
    cid = resp.json()["id"]
    resp = client.delete(f"/api/contacts/{cid}", headers=auth_headers)
    assert resp.status_code == 204
    resp = client.get(f"/api/contacts/{cid}", headers=auth_headers)
    assert resp.status_code == 404


def test_requires_auth(client):
    resp = client.get("/api/contacts/")
    assert resp.status_code == 401
