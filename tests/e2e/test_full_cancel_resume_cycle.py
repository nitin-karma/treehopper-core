# tests/e2e/test_full_cancel_resume_cycle.py
# import time
# import json
# from pathlib import Path
from treehopper.treehopper_chains import resolve_chain, chain_run_detached

# import os


def test_full_cancel_resume(tmp_path):
    # This is a high-level E2E that expects chain files already installed in registry.
    # In CI, you will run the suite in an environment prepared by integration tests.
    # For now, mark it xfail in default runs or guard with environment variable.
    import os

    if os.getenv("RUN_E2E") != "1":
        import pytest

        pytest.skip("Skip e2e unless RUN_E2E=1")

    # find chain id
    chain_ref = resolve_chain("cancel_test_chain")  # requires chain present
    run_id = chain_run_detached(chain_ref, {"name": "E2E"}, run_once=True)
    # cancel and resume would be exercised by other tests; this is just a stub
    assert run_id is not None
