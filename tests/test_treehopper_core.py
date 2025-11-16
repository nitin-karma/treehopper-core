from fastapi.testclient import TestClient
from treehopper.treehopper import app

client = TestClient(app)
HEADERS = {"x-api-key": "demo-key-123"}


def test_auth_failure():
    response = client.get("/api/v1/dev/agents")  # no API key
    assert response.status_code == 403


def test_greet_endpoint():
    response = client.post(
        "/api/v1/agents/greet", json={"name": "Nitin"}, headers=HEADERS
    )
    assert response.status_code == 200
    assert "Nitin" in response.json()["message"]


def test_list_agents():
    response = client.get("/api/v1/dev/agents", headers=HEADERS)
    assert response.status_code == 200
    paths = [a["path"] for a in response.json()]
    assert "/api/v1/agents/greet" in paths


def test_store_and_search():
    client.post(
        "/api/v1/dev/store",
        params={"key": "k1", "content": "Hello world"},
        headers=HEADERS,
    )
    resp = client.get("/api/v1/dev/search", params={"query": "Hello"}, headers=HEADERS)
    docs = resp.json()["results"]["documents"]
    assert any("Hello" in doc for doc in docs)
