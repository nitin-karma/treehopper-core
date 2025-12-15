import os

# import json
import pytest
from fastapi.testclient import TestClient
from treehopper.treehopper import app

os.environ["TH_TEST_MODE"] = "1"
os.environ["TREEHOPPER_RUNTIME_MODE"] = "1"


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    r = client.get("/api/v1/sys/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_auth_rejected(client):
    r = client.get("/api/v1/dev/agents")
    assert r.status_code == 403


def test_list_agents_with_key(client):
    r = client.get(
        "/api/v1/dev/agents",
        headers={"x-api-key": "demo-key-123"},
    )
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_chain_list_empty(client):
    r = client.get(
        "/api/v1/dev/chains",
        headers={"x-api-key": "demo-key-123"},
    )
    assert r.status_code == 200
