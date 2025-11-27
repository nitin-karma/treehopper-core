import os
import subprocess
import time
import requests


def test_cli_run_agent():
    # start server
    proc = subprocess.Popen(
        ["treehopper", "run"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "TH_TEST_MODE": "1"},
    )

    # wait until server is live
    for _ in range(40):
        try:
            if (
                requests.get("http://localhost:1567/api/v1/sys/health").status_code
                == 200
            ):
                break
        except Exception:
            time.sleep(0.2)

    # call the agent
    result = subprocess.run(
        ["treehopper", "call", "/api/v1/agents/greet", '{"name": "Test"}'],
        capture_output=True,
        text=True,
    )

    # cleanup
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

    assert "Test" in result.stdout
