# tests/integration/bootstrap.py
import os
import subprocess
from pathlib import Path


def th(cmd: list[str], env: dict):
    subprocess.check_call(["th"] + cmd, env=env)


def bootstrap_treehopper(root: Path):
    env = os.environ.copy()

    env["TH_ROOT"] = str(root)
    env["TREEHOPPER_RUNTIME_DIR"] = str(root / "runtime")
    env["TREEHOPPER_CANCEL_DIR"] = str(root / "runtime" / "cancels")
    env["TREEHOPPER_FORCE_LOCAL"] = "1"
    env["TH_TEST_MODE"] = "1"
    env["TH_LLM_PROVIDER"] = "mock"

    # -------------------
    # Build agents
    # -------------------
    th(["build", "examples/pdf_extractor"], env)
    th(["build", "examples/content_analyzer"], env)
    th(["build", "examples/report_generator"], env)
    th(["build", "examples/keyword_extractor"], env)
    th(["build", "examples/teams_notifier"], env)

    # -------------------
    # Build chains
    # -------------------
    th(
        [
            "chain",
            "build",
            "doc_flow",
            "pdf_extractor",
            "content_analyzer",
            "report_generator",
        ],
        env,
    )

    th(
        [
            "chain",
            "build-steps",
            "dynamic_doc_intel",
            "--step",
            "extract",
            "sequential",
            "pdf_extractor",
            "--step",
            "analyze",
            "parallel",
            "content_analyzer",
            "keyword_extractor",
            "--merge-agent",
            "smart_data_aggregator",
            "--step",
            "alert_team",
            "sequential",
            "teams_notifier",
        ],
        env,
    )

    # -------------------
    # Push test file
    # -------------------
    th(
        ["push-file", "pdf_extractor", "examples/files/contract.pdf"],
        env,
    )
