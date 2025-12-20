# import os
# from pathlib import Path
# from unittest.mock import patch

from treehopper.chains_agents_refresh_status import (
    chains_status,
    agents_status,
)


def test_chains_status_empty(tmp_path, monkeypatch):
    monkeypatch.setattr("treehopper.chains_agents_refresh_status.RUNTIME_DIR", tmp_path)

    result = chains_status()
    assert result == {}


def test_agents_status_empty(tmp_path, monkeypatch):
    monkeypatch.setattr("treehopper.chains_agents_refresh_status.RUNTIME_DIR", tmp_path)

    result = agents_status()
    assert result == {}


def test_chains_status_with_pid(tmp_path, monkeypatch):
    # 1. Create the dummy file so the glob finds it
    pid_file = tmp_path / "det_chain_demo.pid"
    pid_file.write_text("dummy")

    monkeypatch.setattr("treehopper.chains_agents_refresh_status.RUNTIME_DIR", tmp_path)

    # 2. PATCH THE IMPORTED REFERENCE
    # Instead of patching treehopper.utils.config, patch it where chains_status sees it
    monkeypatch.setattr(
        "treehopper.chains_agents_refresh_status.read_pid_and_port",
        lambda path: (12345, 20316),
    )

    # 3. Patch the liveness check
    monkeypatch.setattr(
        "treehopper.chains_agents_refresh_status._is_pid_alive",
        lambda pid: True,
    )

    status = chains_status()

    # Debug print to see what the function actually returned if it fails again
    print(f"Status returned: {status}")

    assert "demo" in status
    assert status["demo"]["alive"] is True


def test_agents_status_with_pid(tmp_path, monkeypatch):
    pid_file = tmp_path / "det_agent_foo.pid"
    pid_file.write_text("dummy")

    monkeypatch.setattr("treehopper.chains_agents_refresh_status.RUNTIME_DIR", tmp_path)

    # Patch the imported reference here as well
    monkeypatch.setattr(
        "treehopper.chains_agents_refresh_status.read_pid_and_port",
        lambda path: (54321, 21316),
    )

    monkeypatch.setattr(
        "treehopper.chains_agents_refresh_status._is_pid_alive",
        lambda pid: False,
    )

    status = agents_status()
    assert "foo" in status
    assert status["foo"]["alive"] is False
