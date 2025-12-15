import os
import time
import json
import subprocess
import pytest

# from pathlib import Path
import requests

BASE = "http://127.0.0.1:20316"
API_KEY = {"x-api-key": "demo-key-123"}


@pytest.fixture(scope="module")
def server():
    proc = subprocess.Popen(
        ["treehopper", "run", "--bg"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=os.environ.copy(),
    )
    print(proc)

    # wait for health
    for _ in range(30):
        try:
            r = requests.get(f"{BASE}/api/v1/sys/health", timeout=0.5)
            if r.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(0.3)

    yield
    subprocess.run(["treehopper", "stop"], stdout=subprocess.DEVNULL)


def test_detached_chain_cancel_resume(server):
    payload = {"file_path": "shared/demo/files/test.pdf"}

    r = subprocess.check_output(
        [
            "treehopper",
            "chain",
            "run",
            "dynamic_doc_intel",
            "--detached",
            "--bg",
            "--payload",
            json.dumps(payload),
        ],
        text=True,
    )

    run_id = [line.split()[-1] for line in r.splitlines() if line.startswith("RUN_ID")][
        0
    ]
    assert run_id

    # cancel
    subprocess.run(["treehopper", "chain", "cancel", "--run", run_id])
    time.sleep(1)

    # resume
    subprocess.run(["treehopper", "chain", "resume", run_id])
    time.sleep(2)

    status = requests.get(
        f"{BASE}/api/v1/chains/status/{run_id}",
        headers=API_KEY,
    ).json()

    assert status["ok"] is True
    assert status["status"] in ("completed", "running")
