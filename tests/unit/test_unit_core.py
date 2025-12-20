# import os
# import json
import pytest

# import sys
# import shutil
from pathlib import Path
from unittest.mock import patch

# --------------------------------------------------
# CORE IMPORTS
# --------------------------------------------------
from treehopper.treehopper import agent, AGENT_PATH_MAP
from treehopper.treehopper_chains import (
    validate_chain_name,
    derive_chain_port,
)
from treehopper.utils.run_registry import make_run_id, record_chain_run
from treehopper.treehopper_cli import validate_agent_name, push_file
from treehopper.chains_agents_refresh_status import (
    chains_status,
    agents_status,
)
import treehopper.th_config as th_config
from treehopper.websockets.schema_guard import validate_event


# --------------------------------------------------
# FIXTURES
# --------------------------------------------------
@pytest.fixture(autouse=True)
def isolate_fs(tmp_path, monkeypatch):
    """
    Deep-patch ALL modules to ensure no real files are touched.
    """
    tmp_reg = tmp_path / "registry"
    tmp_agents = tmp_reg / "agents"
    tmp_chains = tmp_reg / "chains"
    tmp_runtime = tmp_path / "runtime"
    tmp_cancel = tmp_path / "cancel"

    for d in [tmp_reg, tmp_agents, tmp_chains, tmp_runtime, tmp_cancel]:
        d.mkdir(parents=True, exist_ok=True)

    path_map = {
        "REGISTRY_DIR": tmp_reg,
        "REGISTRY_AGENTS": tmp_agents,
        "REGISTRY_AGENTS_INDEX": tmp_agents / "index.json",
        "CHAINS_DIR": tmp_chains,
        "CHAINS_INDEX": tmp_chains / "index.json",
        "RUNTIME_DIR": tmp_runtime,
        "CANCEL_DIR": tmp_cancel,
    }

    # 1. Patch the source config
    for constant, path in path_map.items():
        monkeypatch.setattr(th_config, constant, path)

    # 2. Patch every module that imports these constants
    target_modules = [
        "treehopper.treehopper_cli",
        "treehopper.utils.run_registry",
        "treehopper.chains_agents_refresh_status",
        "treehopper.th_config",
    ]

    for mod_name in target_modules:
        for constant, path in path_map.items():
            monkeypatch.setattr(f"{mod_name}.{constant}", path, raising=False)

    yield


# --- MOCK DATA ---
AGENT_INDEX_MOCK = [
    {
        "agent_name": "pdf_extractor",
        "agent_id": "pdf_extractor-a1b2c3d4",
        "subscription_id": "sub-123",
    },
    {
        "agent_name": "content_analyzer",
        "agent_id": "content_analyzer-x9y8z7w6",
        "subscription_id": "sub-123",
    },
]


# --------------------------------------------------
# AGENT DECORATOR & REGISTRY
# --------------------------------------------------
def test_agent_decorator_registers_path():
    @agent("hello_test", method="POST", goal="unit test")
    async def hello(payload: dict):
        return {"msg": "ok"}

    path = "/api/v1/agents/hello_test"
    assert path in AGENT_PATH_MAP
    entry = AGENT_PATH_MAP[path]
    assert entry["method"] == "POST"
    assert callable(entry["handler"])
    assert entry["orig"] is hello


def test_validate_agent_name_rules():
    assert validate_agent_name("MyAgent_1") == "myagent_1"
    with pytest.raises(ValueError):
        validate_agent_name("bad name")
    with pytest.raises(ValueError):
        validate_agent_name("12bad")


# --------------------------------------------------
# AGENT FILE OPERATIONS (push_file)
# --------------------------------------------------
@patch("treehopper.treehopper_cli.ensure_registry_dirs")
@patch("treehopper.treehopper_cli.load_agents_index", return_value=AGENT_INDEX_MOCK)
@patch("shutil.copy2")
def test_push_file_creates_shared_dir(
    mock_copy, mock_load_index, mock_ensure_dirs, tmp_path
):
    agent_name = "pdf_extractor"
    expected_agent_id = "pdf_extractor-a1b2c3d4"

    mock_src_file = tmp_path / "test_file_to_push.pdf"
    mock_src_file.write_text("file content")

    # Use patched REGISTRY_DIR
    expected_dest_dir = th_config.REGISTRY_DIR / "shared" / expected_agent_id / "files"

    push_file(agent_name, str(mock_src_file))

    assert expected_dest_dir.exists()
    mock_copy.assert_called_once()


@patch("treehopper.treehopper_cli.ensure_registry_dirs")
@patch("treehopper.treehopper_cli.load_agents_index", return_value=AGENT_INDEX_MOCK)
def test_push_file_source_file_not_found_raises_system_exit(
    mock_load_index, mock_ensure_dirs, capsys
):
    with pytest.raises(SystemExit) as excinfo:
        push_file("pdf_extractor", "/nonexistent/path.pdf")
    assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert "❌ File not found" in captured.out


# --------------------------------------------------
# STATUS REFRESH TESTS
# --------------------------------------------------
def test_chains_status_with_pid(tmp_path, monkeypatch):
    pid_file = th_config.RUNTIME_DIR / "det_chain_demo.pid"
    pid_file.write_text("stub")

    monkeypatch.setattr(
        "treehopper.chains_agents_refresh_status.read_pid_and_port",
        lambda p: (12345, 20316),
    )
    monkeypatch.setattr(
        "treehopper.chains_agents_refresh_status._is_pid_alive", lambda pid: True
    )

    status = chains_status()
    assert "demo" in status
    assert status["demo"]["alive"] is True


def test_agents_status_with_pid(tmp_path, monkeypatch):
    pid_file = th_config.RUNTIME_DIR / "det_agent_foo.pid"
    pid_file.write_text("stub")

    monkeypatch.setattr(
        "treehopper.chains_agents_refresh_status.read_pid_and_port",
        lambda p: (54321, 21316),
    )
    monkeypatch.setattr(
        "treehopper.chains_agents_refresh_status._is_pid_alive", lambda pid: False
    )

    status = agents_status()
    assert "foo" in status
    assert status["foo"]["alive"] is False


# --------------------------------------------------
# CHAIN VALIDATION
# --------------------------------------------------
def test_validate_chain_name():
    assert validate_chain_name("DocFlow_1") == "docflow_1"
    with pytest.raises(ValueError):
        validate_chain_name("bad name")


def test_derive_chain_port_stable_and_range():
    p1 = derive_chain_port("abc-123")
    p2 = derive_chain_port("abc-123")
    assert p1 == p2
    assert 20000 <= p1 <= 24999


# --------------------------------------------------
# RUN REGISTRY
# --------------------------------------------------
def test_make_run_id_unique_and_prefixed():
    r1 = make_run_id("demo")
    r2 = make_run_id("demo")
    assert r1 != r2
    assert r1.startswith("demo-")


def test_record_chain_run_writes_files(tmp_path):
    chain_dir = th_config.CHAINS_DIR / "demo-123"
    chain_dir.mkdir(parents=True)

    record_chain_run(
        chain_name="demo",
        chain_id="demo-123",
        chain_dir=chain_dir,
        payload={"x": 1},
        results=[{"ok": True}],
        detached=False,
        success=True,
        run_id="demo-001",
    )
    assert (chain_dir / "runs/demo-001.json").exists()
    assert (chain_dir / "last_run.json").exists()


# --------------------------------------------------
# FILESYSTEM PATH GUARANTEES
# --------------------------------------------------
def test_registry_paths_created(tmp_path):
    th_config.REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    th_config.REGISTRY_AGENTS.mkdir(parents=True, exist_ok=True)
    th_config.CHAINS_DIR.mkdir(parents=True, exist_ok=True)
    th_config.RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    th_config.CANCEL_DIR.mkdir(parents=True, exist_ok=True)

    assert str(tmp_path) in str(th_config.REGISTRY_DIR)
    assert th_config.REGISTRY_AGENTS.exists()


def test_registry_index_paths(tmp_path):
    th_config.REGISTRY_AGENTS_INDEX.parent.mkdir(parents=True, exist_ok=True)
    th_config.REGISTRY_AGENTS_INDEX.write_text("[]")
    th_config.CHAINS_INDEX.parent.mkdir(parents=True, exist_ok=True)
    th_config.CHAINS_INDEX.write_text("[]")

    assert th_config.REGISTRY_AGENTS_INDEX.exists()
    assert th_config.CHAINS_INDEX.exists()


# --------------------------------------------------
# WEBSOCKET EVENT SCHEMA (7 Parameterized Cases)
# --------------------------------------------------
@pytest.mark.parametrize(
    "event",
    [
        {
            "type": "step_start",
            "step_id": "extract",
            "step_index": 0,
            "mode": "sequential",
        },
        {"type": "agent_start", "step_id": "extract", "agent": "pdf_extractor"},
        {"type": "agent_complete", "step_id": "extract", "agent": "pdf_extractor"},
        {"type": "parallel_complete", "step_id": "analyze", "agents": ["a", "b"]},
        {
            "type": "merge_complete",
            "step_id": "analyze",
            "merge_agent": "aggregator",
            "merged_keys": ["x"],
        },
        {"type": "run_completed", "status": "success"},
        {"type": "run_cancelled"},
    ],
)
def test_ws_event_schema_valid(event):
    validate_event(event)


def test_ws_event_schema_invalid():
    with pytest.raises(ValueError):
        validate_event({"type": "step_start"})  # Missing required fields


# --------------------------------------------------
# CANCEL DIRECTORY SEMANTICS
# --------------------------------------------------
def test_cancel_dir_is_writable(tmp_path):
    th_config.CANCEL_DIR.mkdir(parents=True, exist_ok=True)
    marker = th_config.CANCEL_DIR / "demo-001.cancel"
    marker.write_text("cancelled")
    assert marker.exists()
    assert marker.read_text() == "cancelled"


def test_real_registry_untouched_verification(tmp_path):
    """
    Explicitly verifies that the real ~/.treehopper/registry files
    were not emptied or modified during the test execution.
    """
    import treehopper.th_config as th_config

    # 1. Define the REAL paths (ignoring the monkeypatch)
    real_home = Path.home() / ".treehopper"
    real_agents_json = real_home / "registry" / "agents" / "index.json"
    real_chains_json = real_home / "registry" / "chains" / "index.json"

    # 2. Capture current state if they exist
    initial_content_agents = (
        real_agents_json.read_text() if real_agents_json.exists() else None
    )
    initial_content_chains = (
        real_chains_json.read_text() if real_chains_json.exists() else None
    )

    # 3. Trigger the logic that was previously causing the "leak"
    # We call these to ensure the patched versions are what's being used
    th_config.REGISTRY_AGENTS_INDEX.parent.mkdir(parents=True, exist_ok=True)
    th_config.REGISTRY_AGENTS_INDEX.write_text("['test-data']")

    # 4. ASSERTIONS
    # Verify the temporary test file HAS the test data
    assert th_config.REGISTRY_AGENTS_INDEX.read_text() == "['test-data']"

    # Verify the REAL home file REMAINS unchanged
    if initial_content_agents is not None:
        assert real_agents_json.read_text() == initial_content_agents
        assert (
            real_agents_json.read_text() != "[]"
        )  # Double check it didn't get emptied

    if initial_content_chains is not None:
        assert real_chains_json.read_text() == initial_content_chains

    # 5. Final Path Sanity Check
    assert str(tmp_path) in str(th_config.REGISTRY_AGENTS_INDEX)
    assert str(Path.home()) not in str(th_config.REGISTRY_AGENTS_INDEX)
