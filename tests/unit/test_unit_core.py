# import os
import json
import pytest
from unittest.mock import patch

# import shutil

# from pathlib import Path

# --------------------------------------------------
# CORE IMPORTS
# --------------------------------------------------
from treehopper.treehopper import agent, AGENT_PATH_MAP
from treehopper.treehopper_chains import (
    validate_chain_name,
    derive_chain_port,
)
from treehopper.utils.run_registry import make_run_id
from treehopper.treehopper_cli import validate_agent_name, push_file
from treehopper.th_config import (
    REGISTRY_DIR,
    REGISTRY_AGENTS,
    REGISTRY_AGENTS_INDEX,
    CHAINS_DIR,
    CHAINS_INDEX,
    RUNTIME_DIR,
    CANCEL_DIR,
)
from treehopper.utils.run_registry import record_chain_run
from treehopper.websockets.schema_guard import validate_event


# --------------------------------------------------
# FIXTURES
# --------------------------------------------------
@pytest.fixture(autouse=True)
def isolate_fs(tmp_path, monkeypatch):
    """
    Force ALL filesystem paths into a temp directory.
    This guarantees:
    - no ~/.treehopper writes
    - hermetic tests
    """
    # --- CORE FIX: Patch REGISTRY_DIR in BOTH modules ---

    # 1. Patch in th_config (for other modules/globals)
    monkeypatch.setattr(
        "treehopper.th_config.REGISTRY_DIR", tmp_path / "registry", raising=False
    )
    # 2. Patch in treehopper_cli (where push_file resides and uses the import)
    monkeypatch.setattr(
        "treehopper.treehopper_cli.REGISTRY_DIR", tmp_path / "registry", raising=False
    )

    # Patch all other necessary paths in th_config (and treehopper_cli if they are
    # also statically imported, but focusing on REGISTRY_DIR is usually enough)
    monkeypatch.setattr(
        "treehopper.th_config.REGISTRY_AGENTS",
        tmp_path / "registry/agents",
        raising=False,
    )
    monkeypatch.setattr(
        "treehopper.th_config.REGISTRY_AGENTS_INDEX",
        tmp_path / "registry/agents/index.json",
        raising=False,
    )
    monkeypatch.setattr(
        "treehopper.th_config.CHAINS_DIR", tmp_path / "registry/chains", raising=False
    )
    monkeypatch.setattr(
        "treehopper.th_config.CHAINS_INDEX",
        tmp_path / "registry/chains/index.json",
        raising=False,
    )
    monkeypatch.setattr(
        "treehopper.th_config.RUNTIME_DIR", tmp_path / "runtime", raising=False
    )
    monkeypatch.setattr(
        "treehopper.th_config.CANCEL_DIR", tmp_path / "cancel", raising=False
    )

    yield


# --- MOCK DATA FOR push_file TESTS ---

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


# Patch the external dependencies that push_file relies on.
# We assume load_agents_index and ensure_registry_dirs are defined elsewhere,
# but we patch them in the scope of treehopper.treehopper_cli (where push_file is imported).

# --------------------------------------------------
# AGENT FILE OPERATIONS (push_file)
# --------------------------------------------------


@patch("treehopper.treehopper_cli.ensure_registry_dirs")
@patch("treehopper.treehopper_cli.load_agents_index", return_value=AGENT_INDEX_MOCK)
@patch("shutil.copy2")  # <-- NEW PATCH: Mock the file copy operation
def test_push_file_creates_shared_dir(
    mock_copy, mock_load_index, mock_ensure_dirs, tmp_path
):
    """
    Tests the success path: push_file should correctly construct and create
    the shared storage directory for a valid agent_id AND validate the source file.
    """
    agent_name = "pdf_extractor"
    expected_agent_id = "pdf_extractor-a1b2c3d4"

    # 1. Create a mock source file in the temporary environment (REQUIRED for src.exists())
    mock_src_file = tmp_path / "test_file_to_push.pdf"
    mock_src_file.write_text("file content")
    src_path = str(mock_src_file)

    # Expected final path relies on isolate_fs mocking REGISTRY_DIR to tmp_path / "registry"
    expected_dest_dir = tmp_path / "registry" / "shared" / expected_agent_id / "files"

    # Ensure the parent registry path exists as per isolate_fs
    (tmp_path / "registry").mkdir(exist_ok=True)

    # Call the function
    push_file(agent_name, src_path)

    # Assertion 1: Check if the full expected directory path was created (This should now PASS)
    assert expected_dest_dir.exists()
    assert expected_dest_dir.is_dir()

    # Assertion 2: Check that the copy operation was attempted (Verifying the end of the function logic)
    # The destination should be the file inside the newly created directory
    expected_copy_dest = expected_dest_dir / mock_src_file.name
    mock_copy.assert_called_once_with(mock_src_file, expected_copy_dest)


@patch("treehopper.treehopper_cli.ensure_registry_dirs")
@patch("treehopper.treehopper_cli.load_agents_index", return_value=AGENT_INDEX_MOCK)
def test_push_file_source_file_not_found_raises_system_exit(
    mock_load_index, mock_ensure_dirs, capsys
):
    """
    Tests the failure path when the source file does not exist.
    """
    agent_name = "pdf_extractor"
    non_existent_src_path = "/nonexistent/path/to/file.pdf"

    # Assert that sys.exit(1) is called
    with pytest.raises(SystemExit) as excinfo:
        push_file(agent_name, non_existent_src_path)

    # Check the exit code
    assert excinfo.value.code == 1

    # Check the printed output for the user-facing message
    captured = capsys.readouterr()
    expected_message = f"❌ File not found: {non_existent_src_path}\n"
    assert captured.out == expected_message


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
    chain_dir = tmp_path / "registry/chains/demo-123"
    chain_dir.mkdir(parents=True)

    history = record_chain_run(
        chain_name="demo",
        chain_id="demo-123",
        chain_dir=chain_dir,
        payload={"x": 1},
        results=[{"ok": True}],
        detached=False,
        success=True,
        run_id="demo-001",
    )
    print(history)
    run_file = chain_dir / "runs/demo-001.json"
    last_run = chain_dir / "last_run.json"

    assert run_file.exists()
    assert last_run.exists()

    data = json.loads(run_file.read_text())
    assert data["run_id"] == "demo-001"
    assert data["success"] is True


# --------------------------------------------------
# FILESYSTEM PATH GUARANTEES
# --------------------------------------------------
def test_registry_paths_created(tmp_path):
    # force creation
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    REGISTRY_AGENTS.mkdir(parents=True, exist_ok=True)
    CHAINS_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    CANCEL_DIR.mkdir(parents=True, exist_ok=True)

    assert REGISTRY_DIR.exists()
    assert REGISTRY_AGENTS.exists()
    assert CHAINS_DIR.exists()
    assert RUNTIME_DIR.exists()
    assert CANCEL_DIR.exists()


def test_registry_index_paths(tmp_path):
    REGISTRY_AGENTS.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_AGENTS_INDEX.write_text("[]")

    CHAINS_DIR.mkdir(parents=True, exist_ok=True)
    CHAINS_INDEX.write_text("[]")

    assert REGISTRY_AGENTS_INDEX.exists()
    assert CHAINS_INDEX.exists()


# --------------------------------------------------
# WEBSOCKET EVENT SCHEMA (FROZEN CONTRACT)
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
            "merge_agent": "smart_data_aggregator",
            "merged_keys": ["x", "y"],
        },
        {"type": "run_completed", "status": "success"},
        {"type": "run_cancelled"},
    ],
)
def test_ws_event_schema_valid(event):
    # should NOT raise
    validate_event(event)


def test_ws_event_schema_invalid():
    with pytest.raises(ValueError):
        validate_event({"type": "step_start"})  # missing required fields


# --------------------------------------------------
# CANCEL DIRECTORY SEMANTICS
# --------------------------------------------------
def test_cancel_dir_is_writable(tmp_path):
    CANCEL_DIR.mkdir(parents=True, exist_ok=True)

    marker = CANCEL_DIR / "demo-001.cancel"
    marker.write_text("cancelled")

    assert marker.exists()
    assert marker.read_text() == "cancelled"
