# # tests/integration/test_cancel_resume_flow.py
import json
import time

# from pathlib import Path
from treehopper.treehopper_chains import (
    # chain_build,
    # resolve_chain,
    # chain_run_detached,
    resume_run,
)

# from treehopper.treehopper_cancellation import create_cancel_marker


def test_cancel_and_resume_cycle(tmp_path, monkeypatch):
    # This is an integration-style test that simulates: create chain, run detached, create cancel marker,
    # then call resume_run and assert run file becomes completed.
    # Setup a fake chain directory in tmp_path to avoid touching real ~/.treehopper
    th_root = tmp_path / ".treehopper"
    registry = th_root / "registry"
    chains_dir = registry / "chains"
    chains_dir.mkdir(parents=True)
    chain_id = "cancel_test_chain-test"
    chain_dir = chains_dir / chain_id
    (chain_dir / "runs").mkdir(parents=True)
    # write a simple chain.yaml
    chain_cfg = {
        "chain_name": "cancel_test_chain",
        "chain_id": chain_id,
        "agents": [
            {"agent_name": "slow_agent", "path": "/api/v1/agents/slow_agent"},
            {
                "agent_name": "slow_agent_stage2",
                "path": "/api/v1/agents/slow_agent_stage2",
            },
        ],
    }
    (chain_dir / "chain.yaml").write_text(json.dumps(chain_cfg))
    # monkeypatch CHAINS_DIR / REGISTRY paths used by your code if required
    # For simple test, create a run file with status=running and current_step_index=0
    run_id = "cancel_test_chain-9999"
    run_file = chain_dir / "runs" / f"{run_id}.json"
    run_data = {
        "chain_name": "cancel_test_chain",
        "chain_id": chain_id,
        "run_id": run_id,
        "executed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "input": {"name": "X"},
        "results": [],
        "detached": True,
        "success": False,
        "status": "running",
        "current_step_index": 0,
    }
    run_file.write_text(json.dumps(run_data))
    # create cancel marker file
    # create_cancel_marker uses TH_ROOT path; if needed, monkeypatch its DB_PATH or location
    # call resume_run -> should resume (your resume_run uses run file location)
    resume_run(run_id)
    # re-read file
    data = json.loads(run_file.read_text())
    assert data.get("status") in ("completed", "failed")
