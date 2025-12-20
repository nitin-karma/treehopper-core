import os
import subprocess
import pytest
from subprocess import CalledProcessError, STDOUT


def test_detached_chain_run(isolated_treehopper_root, auth_headers):
    env = os.environ.copy()
    env["TH_ROOT"] = str(isolated_treehopper_root)
    env["TREEHOPPER_RUNTIME_DIR"] = str(isolated_treehopper_root / "runtime")
    env["TREEHOPPER_CANCEL_DIR"] = str(isolated_treehopper_root / "runtime" / "cancels")
    env["TREEHOPPER_FORCE_LOCAL"] = "1"
    env["TREEHOPPER_RUNTIME_MODE"] = "1"
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

    try:
        # Use stderr=STDOUT to capture all output (stdout + stderr) in the result variable
        result = subprocess.check_output(cmd, text=True, stderr=STDOUT, env=env)

        # --- PRIMARY SUCCESS CHECK ---
        run_id = None
        detached = 0

        for line in result.splitlines():
            if line.startswith("RUN_ID:"):
                run_id = line.split("RUN_ID:")[1].strip()
            if "Detached chain triggered" in line:
                detached = 1

        # If the expected success indicators are present, the test passes normally.
        assert run_id is not None, "Failed to extract RUN_ID from successful execution."
        assert detached == 1, "Expected 'Detached chain triggered' message."

    except CalledProcessError as e:
        full_output = e.output

        # --- 429 FAILURE CHECK (User's requested pass condition) ---
        rate_limit_indicators = [
            "429 Too Many Requests",
            "Rate Limit Exceeded",
            "rate limit",
            # We look for the 429 code reported in the error output
            "429",
        ]

        is_rate_limited = any(
            indicator in full_output for indicator in rate_limit_indicators
        )

        if is_rate_limited:
            # If rate-limited, the test is considered passed as per the user's request
            # to prevent CI failure due to external service constraints.
            print(
                f"\n[Test Passed] Detected expected 429 Rate Limit error:\n{full_output}"
            )
            # Explicitly assert True to pass the test block
            assert True
        else:
            # If the failure is due to an unexpected reason, the test fails.
            pytest.fail(
                f"Subprocess failed with unexpected error (not 429):\n{full_output}"
            )
