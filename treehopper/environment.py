# treehopper/environment.py
import os
from pathlib import Path


def inject_pythonpath(env: dict):
    """
    Injects the project root into PYTHONPATH **only when running in dev mode**.

    This ensures that chain runtimes (spawned as subprocesses) import
    the local source tree instead of the installed pip version.
    """
    if os.getenv("TREEHOPPER_DEV_MODE") != "1":
        return  # No-op for pip users / production

    project_root = str(Path(__file__).resolve().parent.parent)
    existing = env.get("PYTHONPATH")

    if existing:
        if project_root not in existing:
            env["PYTHONPATH"] = f"{project_root}:{existing}"
    else:
        env["PYTHONPATH"] = project_root

    print(f"[DEV_MODE] PYTHONPATH injected → {env['PYTHONPATH']}")
