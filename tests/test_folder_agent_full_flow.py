# import json
import os
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

import requests

API_KEY = {"x-api-key": "demo-key-123"}
BASE = "http://localhost:1560"


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def test_folder_agent_full_flow():
    agent_name = f"alpha_{uuid.uuid4().hex[:6]}"

    with tempfile.TemporaryDirectory() as tmp:
        cwd = Path(tmp)
        os.chdir(cwd)

        # ---- 1) init
        r = run_cmd(["treehopper", "init", agent_name])
        assert r.returncode == 0
        assert (cwd / agent_name).exists()

        # ---- 2) lint
        r = run_cmd(["treehopper", "lint", agent_name])
        assert r.returncode == 0

        # ---- 3) build (copy to ~/.treehopper)
        r = run_cmd(["treehopper", "build", agent_name])
        assert r.returncode == 0

        # # ---- 4) restart existing 1560 uvicorn so new agent is discovered
        env = os.environ.copy()
        # env["PROD"] = "1"                 # disable reload
        # subprocess.run(["pkill", "-f", "uvicorn.*1560"], stderr=subprocess.DEVNULL)
        proc = subprocess.Popen(["treehopper", "run"], env=env)
        # ---- 4) restart server to discover new agent
        # r = run_cmd(["treehopper", "restart"])
        # assert r.returncode == 0

        # wait until server is up
        for _ in range(40):
            try:
                if (
                    requests.get(f"{BASE}/api/v1/sys/health", timeout=0.2).status_code
                    == 200
                ):
                    break
            except Exception:
                time.sleep(0.15)

        # ---- 5) call agent
        payload = {"name": "Folder"}
        r = requests.post(
            f"{BASE}/api/v1/agents/{agent_name}",
            json=payload,
            headers=API_KEY,
        )
        assert r.status_code == 200, r.text
        assert "Folder" in r.text

        # ---- 6) chain call
        chain_payload = {
            "chain": [
                {"path": f"/api/v1/agents/{agent_name}", "params": {"name": "Step1"}},
                {"path": f"/api/v1/agents/{agent_name}", "params": {"name": "Step2"}},
            ]
        }
        r = requests.post(
            f"{BASE}/api/v1/dev/chain", json=chain_payload, headers=API_KEY
        )
        assert r.status_code == 200
        data = r.json()
        assert "Step1" in data["results"][0]["message"]
        assert "Step2" in data["results"][1]["message"]
        assert data["results"][0]["message"].endswith("agent!")
        assert data["results"][1]["message"].endswith("agent!")

        # ---- 7) CLI info
        r = run_cmd(["treehopper", "agent", "info", agent_name])
        assert r.returncode == 0
        assert f"agent_name: {agent_name}" in r.stdout

        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
