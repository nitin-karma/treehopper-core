# mypy: ignore-errors
# tests/integration/conftest.py

import os
import sys
import pytest
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient

# ------------------------------------------------------------------
# 🔒 SET ENV BEFORE ANY TREEHOPPER IMPORTS
# ------------------------------------------------------------------

if "TH_ROOT" not in os.environ:
    os.environ["TH_ROOT"] = "/tmp/treehopper-pytest-guard"

os.environ["TREEHOPPER_RUNTIME_DIR"] = os.path.join(os.environ["TH_ROOT"], "runtime")
os.environ["TREEHOPPER_CANCEL_DIR"] = os.path.join(
    os.environ["TH_ROOT"], "runtime", "cancels"
)
os.environ["TH_TEST_MODE"] = "1"
os.environ["TH_LLM_PROVIDER"] = "mock"
os.environ["TREEHOPPER_API_KEY"] = "demo-key-123"
os.environ["TREEHOPPER_FORCE_LOCAL"] = "1"


@pytest.fixture(scope="session", autouse=True)
def isolated_treehopper_root():
    """Creates temp TH_ROOT and bootstraps via CLI"""
    with tempfile.TemporaryDirectory(prefix="treehopper-test-") as d:
        root = Path(d)

        # Update environment
        os.environ["TH_ROOT"] = str(root)
        os.environ["TREEHOPPER_RUNTIME_DIR"] = str(root / "runtime")
        os.environ["TREEHOPPER_CANCEL_DIR"] = str(root / "runtime" / "cancels")

        # Bootstrap using CLI
        from bootstrap import bootstrap_treehopper

        bootstrap_treehopper(root)

        # Verify structure
        registry_dir = root / "registry"
        agents_dir = registry_dir / "agents"
        chains_dir = registry_dir / "chains"

        agents = list(agents_dir.glob("*"))
        chains = list(chains_dir.glob("*"))

        print("\n✅ Bootstrap verification:")
        print(f"   TH_ROOT: {root}")
        print(f"   Agents: {len(agents)} - {[a.name for a in agents]}")
        print(f"   Chains: {len(chains)} - {[c.name for c in chains]}")

        assert len(agents) == 5, f"Expected 5 agents, got {len(agents)}"
        assert len(chains) == 2, f"Expected 2 chains, got {len(chains)}"

        yield root


@pytest.fixture(scope="session")
def client(isolated_treehopper_root):
    """Creates FastAPI TestClient with correct TH_ROOT"""

    # Clear module cache
    modules_to_clear = [
        "treehopper.th_config",
        "treehopper.treehopper",
        "treehopper.registry",
        "treehopper.utils.commons",
    ]

    for mod in modules_to_clear:
        if mod in sys.modules:
            del sys.modules[mod]
            print(f"🔄 Cleared module cache: {mod}")

    current_root = os.environ["TH_ROOT"]
    print(f"\n🚀 Creating FastAPI app with TH_ROOT: {current_root}")

    # 🔥 CRITICAL: Temporarily modify sys.argv to enable agent discovery
    original_argv = sys.argv.copy()
    sys.argv = ["pytest", "run"]  # Trick discover_agents() into running

    try:
        from treehopper.treehopper import get_app, AGENT_PATH_MAP, agents

        app = get_app()
    finally:
        sys.argv = original_argv

    # Verify everything loaded correctly
    from treehopper.th_config import CHAINS_DIR, REGISTRY_AGENTS

    print(f"✅ App CHAINS_DIR: {CHAINS_DIR}")
    print(f"✅ App REGISTRY_AGENTS: {REGISTRY_AGENTS}")
    print(f"✅ Discovered {len(AGENT_PATH_MAP)} agent paths")
    print(f"✅ Registered {len(agents)} agent definitions")

    if AGENT_PATH_MAP:
        sample_paths = list(AGENT_PATH_MAP.keys())[:3]
        print(f"   Sample paths: {sample_paths}")
    else:
        print("   ⚠️ WARNING: No agents discovered in AGENT_PATH_MAP!")
        # Debug
        print(f"   Checking {REGISTRY_AGENTS}:")
        if REGISTRY_AGENTS.exists():
            for agent_dir in REGISTRY_AGENTS.glob("*"):
                print(f"      - {agent_dir.name}: {list(agent_dir.glob('*.py'))}")

    if CHAINS_DIR.exists():
        chains = list(CHAINS_DIR.glob("*"))
        print(f"✅ App found {len(chains)} chains")

    return TestClient(app)


@pytest.fixture
def auth_headers():
    return {"x-api-key": "demo-key-123"}
