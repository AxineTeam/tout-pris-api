def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_stufflist(client):
    response = client.post("/stufflists", json={"name": "courses"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "courses"
    assert body["id"] == 1


def test_list_stufflists(client):
    client.post("/stufflists", json={"name": "courses"})
    client.post("/stufflists", json={"name": "voyage"})
    response = client.get("/stufflists")
    assert response.status_code == 200
    names = [item["name"] for item in response.json()]
    assert names == ["courses", "voyage"]


def test_get_stufflist(client):
    created = client.post("/stufflists", json={"name": "courses"}).json()
    response = client.get(f"/stufflists/{created['id']}")
    assert response.status_code == 200
    assert response.json() == created


def test_get_stufflist_not_found(client):
    response = client.get("/stufflists/999")
    assert response.status_code == 404


def test_delete_stufflist(client):
    created = client.post("/stufflists", json={"name": "courses"}).json()
    response = client.delete(f"/stufflists/{created['id']}")
    assert response.status_code == 204
    assert client.get(f"/stufflists/{created['id']}").status_code == 404


def test_create_stufflist_requires_name(client):
    response = client.post("/stufflists", json={})
    assert response.status_code == 422
