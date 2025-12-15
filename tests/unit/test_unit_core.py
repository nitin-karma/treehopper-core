# import os
import json
import pytest

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
from treehopper.treehopper_cli import validate_agent_name
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
    monkeypatch.setattr(
        "treehopper.th_config.REGISTRY_DIR", tmp_path / "registry", raising=False
    )
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
