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


def test_sequential_chaining():
    payload = {
        "chain": [
            {"path": "/api/v1/agents/greet", "params": {"name": "Step1"}},
            {"path": "/api/v1/agents/greet", "params": {"name": "Step2"}},
        ]
    }

    resp = client.post("/api/v1/dev/chain", json=payload, headers=HEADERS)

    assert resp.status_code == 200
    results = resp.json()["results"]

    assert isinstance(results, list)
    assert "Step1" in str(results[0])
    assert "Step2" in str(results[1])


def test_sequential_chaining_multiple_agents():
    payload = {
        "chain": [
            {"path": "/api/v1/agents/greet", "params": {"name": "Alpha"}},
            {"path": "/api/v1/agents/math", "params": {"a": 2, "b": 3}},
            {"path": "/api/v1/agents/llm_compare", "params": {"prompt": "Test"}},
        ]
    }

    resp = client.post("/api/v1/dev/chain", json=payload, headers=HEADERS)
    assert resp.status_code == 200

    results = resp.json()["results"]
    assert len(results) == 3

    # 1️⃣ greet agent output should contain name
    assert "Alpha" in str(results[0])

    # 2️⃣ math agent output should contain addition result
    assert any(str(x) in str(results[1]) for x in ["5", "2 + 3"])

    # 3️⃣ llm_compare agent output should contain prompt
    assert "Test" in str(results[2])


def test_chaining_fails_if_agent_missing():
    payload = {"chain": [{"path": "/api/v1/agents/DOES_NOT_EXIST", "params": {}}]}

    resp = client.post("/api/v1/dev/chain", json=payload, headers=HEADERS)
    assert resp.status_code in (400, 404, 500)
