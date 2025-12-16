import time

# import os
import json
import subprocess
from pathlib import Path


def test_reject_multi_step_from_main_server(client, auth_headers):
    payload = {"file_path": "shared/pdf_extractor-a1b2c3d4/files/contract.pdf"}

    # Start detached run
    r = client.post(
        "/api/v1/chains/dynamic_doc_intel/run",
        headers={**auth_headers, "x-treehopper-detached": "1"},
        json=payload,
    )

    assert r.status_code == 400
    assert "This chain uses multi-step execution." in r.json()["detail"]


def test_cancel_and_resume_flow_runtime_only():
    """
    Multi-step chains must be tested ONLY via detached runtime.
    Main server cannot cancel/resume by design.
    """

    cmd = [
        "th",
        "chain",
        "run",
        "dynamic_doc_intel",
        "--payload",
        '{"file_path":"shared/pdf_extractor-a1b2c3d4/files/contract.pdf"}',
        "--detached",
        "--bg",
    ]

    result = subprocess.check_output(cmd, text=True)

    # Extract run_id
    run_id = None
    for line in result.splitlines():
        if line.startswith("RUN_ID:"):
            run_id = line.split("RUN_ID:")[1].strip()

    assert run_id, "run_id not found"

    # Cancel
    subprocess.check_call(["th", "chain", "cancel", "--run", run_id])
    time.sleep(1)

    # Resume
    subprocess.check_call(["th", "chain", "resume", run_id])

    run_file = Path.home() / ".treehopper/registry/chains"
    matches = list(run_file.glob(f"*/runs/{run_id}.json"))
    assert matches

    data = json.loads(matches[0].read_text())
    assert data["success"] is True
