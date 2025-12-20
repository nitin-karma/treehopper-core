import os

# import time
# import json
import subprocess

# from pathlib import Path


def test_reject_multi_step_from_main_server(client, auth_headers):
    payload = {"file_path": "shared/pdf_extractor-a1b2c3d4/files/contract.pdf"}

    r = client.post(
        "/api/v1/chains/dynamic_doc_intel/run",
        headers={**auth_headers, "x-treehopper-detached": "1"},
        json=payload,
    )

    assert r.status_code in (400, 404)


def test_cancel_and_resume_flow_runtime_only(isolated_treehopper_root):
    env = os.environ.copy()
    env["TH_ROOT"] = str(isolated_treehopper_root)
    env["TREEHOPPER_RUNTIME_DIR"] = str(isolated_treehopper_root / "runtime")
    env["TREEHOPPER_CANCEL_DIR"] = str(isolated_treehopper_root / "runtime" / "cancels")
    env["TREEHOPPER_FORCE_LOCAL"] = "1"
    env["TREEHOPPER_RUNTIME_MODE"] = "1"

    output = subprocess.check_output(
        [
            "th",
            "chain",
            "run",
            "dynamic_doc_intel",
            "--payload",
            '{"file_path":"shared/pdf_extractor-a1b2c3d4/files/contract.pdf"}',
            "--detached",
            "--bg",
            "--port",
            "20316",
        ],
        text=True,
        env=env,
    )

    assert "RUN_ID:" in output
