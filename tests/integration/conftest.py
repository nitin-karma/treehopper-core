import os
import pytest
from fastapi.testclient import TestClient
from treehopper.treehopper import app

os.environ["TH_TEST_MODE"] = "1"
os.environ["TREEHOPPER_RUNTIME_MODE"] = "1"
os.environ["TREEHOPPER_API_KEY"] = "demo-key-123"


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers():
    return {"x-api-key": "demo-key-123"}
