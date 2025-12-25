# tests/unit/test_ws_replay.py
import pytest
from pathlib import Path

from treehopper.websockets.ws_manager import WSManager


class DummyWebSocket:
    def __init__(self):
        self.sent = []

    async def send_json(self, data):
        self.sent.append(data)


# =====================================================================
# FILESYSTEM ISOLATION FIXTURE
# =====================================================================
@pytest.fixture(autouse=True)
def isolate_ws_paths(tmp_path, monkeypatch):
    """
    Ensure WSManager and any websocket code doesn't create
    directories in real ~/.treehopper during tests.

    This patches all th_config paths to use tmp_path instead.
    """
    import treehopper.th_config as th_config

    # Create temporary directory structure
    tmp_reg = tmp_path / "registry"
    tmp_chains = tmp_reg / "chains"
    tmp_agents = tmp_reg / "agents"
    tmp_runtime = tmp_path / "runtime"
    tmp_cancel = tmp_runtime / "cancels"

    for d in [tmp_reg, tmp_chains, tmp_agents, tmp_runtime, tmp_cancel]:
        d.mkdir(parents=True, exist_ok=True)

    # Define all paths to patch
    path_map = {
        "TH_ROOT": tmp_path,
        "REGISTRY_DIR": tmp_reg,
        "REGISTRY_AGENTS": tmp_agents,
        "CHAINS_DIR": tmp_chains,
        "CHAINS_INDEX": tmp_chains / "index.json",
        "RUNTIME_DIR": tmp_runtime,
        "CANCEL_DIR": tmp_cancel,
    }

    # Patch th_config module
    for constant, path_value in path_map.items():
        monkeypatch.setattr(th_config, constant, path_value)

    # Patch any modules that might import these constants
    modules_to_patch = [
        "treehopper.websockets.ws_manager",
        "treehopper.utils.commons",
    ]

    for mod_name in modules_to_patch:
        for constant, path_value in path_map.items():
            monkeypatch.setattr(f"{mod_name}.{constant}", path_value, raising=False)

    yield tmp_path


# =====================================================================
# WEBSOCKET REPLAY BUFFER TESTS
# =====================================================================


@pytest.mark.asyncio
async def test_run_replay_buffer():
    """
    Test that events broadcasted BEFORE a websocket connects
    are replayed to late joiners via the run-specific buffer.
    """
    ws_mgr = WSManager()
    run_id = "run-123"

    # Simulate events BEFORE connection
    await ws_mgr.broadcast(
        run_id=run_id,
        chain_name="demo_chain",
        event={"type": "step_start", "step_id": "extract"},
    )
    await ws_mgr.broadcast(
        run_id=run_id,
        chain_name="demo_chain",
        event={"type": "agent_start", "step_id": "extract", "agent": "pdf_extractor"},
    )

    # Late joiner connects
    ws = DummyWebSocket()
    await ws_mgr.connect_run(run_id, ws)

    # Verify replay happened
    assert len(ws.sent) == 2
    assert ws.sent[0]["type"] == "step_start"
    assert ws.sent[1]["type"] == "agent_start"


@pytest.mark.asyncio
async def test_chain_replay_buffer():
    """
    Test that events broadcasted to a chain are replayed
    to websockets connecting to that chain's feed.
    """
    ws_mgr = WSManager()
    chain = "demo_chain"
    run_id = "run-abc"

    # Broadcast completion event
    await ws_mgr.broadcast(
        run_id=run_id,
        chain_name=chain,
        event={"type": "run_completed", "status": "success"},
    )

    # Connect to chain feed
    ws = DummyWebSocket()
    await ws_mgr.connect_chain(chain, ws)

    # Verify replay
    assert len(ws.sent) == 1
    assert ws.sent[0]["type"] == "run_completed"
    assert ws.sent[0]["run_id"] == run_id


# =====================================================================
# FILESYSTEM ISOLATION VERIFICATION
# =====================================================================


def test_ws_manager_uses_temp_paths(tmp_path, isolate_ws_paths):
    """
    Verify that WSManager doesn't touch the real ~/.treehopper directory.
    This ensures test isolation and prevents pollution of user's home directory.
    """
    import treehopper.th_config as th_config

    # Verify we're using temp paths, not home
    assert str(tmp_path) in str(th_config.TH_ROOT)
    assert str(Path.home()) not in str(th_config.TH_ROOT)

    # Create WSManager - should only use temp paths
    # Note: We don't need to assign to variable since we're just testing initialization
    WSManager()

    # Double-check: if real ~/.treehopper exists, it shouldn't have test artifacts
    real_treehopper = Path.home() / ".treehopper"
    if real_treehopper.exists():
        # Test-specific paths should NOT exist in real home
        test_artifacts = [
            real_treehopper / "registry" / "chains" / "events",
            real_treehopper / "runtime" / "test-markers",
        ]
        for artifact in test_artifacts:
            assert (
                not artifact.exists()
            ), f"Test artifact found in real ~/.treehopper: {artifact}"
