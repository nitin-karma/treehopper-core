# tests/integration/conftest.py
import os
import pytest
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def isolated_treehopper_root():
    with tempfile.TemporaryDirectory(prefix="treehopper-test-") as d:
        root = Path(d)

        os.environ["TH_ROOT"] = str(root)
        os.environ["TREEHOPPER_RUNTIME_DIR"] = str(root / "runtime")
        os.environ["TREEHOPPER_CANCEL_DIR"] = str(root / "runtime" / "cancels")
        os.environ["TH_TEST_MODE"] = "1"
        os.environ["TH_LLM_PROVIDER"] = "mock"
        os.environ["TREEHOPPER_API_KEY"] = "demo-key-123"
        os.environ["TREEHOPPER_FORCE_LOCAL"] = "1"

        # 🔥 bootstrap BEFORE app import
        from bootstrap import bootstrap_treehopper

        bootstrap_treehopper(root)
        os.environ.pop("PYTEST_CURRENT_TEST", None)
        from treehopper.treehopper import discover_agents

        discover_agents()

        yield root


@pytest.fixture(scope="session")
def client(isolated_treehopper_root):
    # 🔥 import AFTER bootstrap
    from treehopper.treehopper import app

    return TestClient(app)


@pytest.fixture
def auth_headers():
    return {"x-api-key": "demo-key-123"}
