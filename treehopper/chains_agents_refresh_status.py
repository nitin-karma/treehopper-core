# treehopper/chains_agents_refresh_status.py

import os
import time
import subprocess
from pathlib import Path
from typing import Dict, List

from treehopper.utils.config import read_pid_and_port
from treehopper.th_config import RUNTIME_DIR
from treehopper.logging import get_logger

logger = get_logger()


# -------------------------------------------------------
# Helpers
# -------------------------------------------------------


def _runtime_pid_files(prefix: str) -> List[Path]:
    """
    prefix:
      - 'det_chain_' for chains
      - 'det_agent_' for agents
    """
    if not RUNTIME_DIR.exists():
        return []

    return list(RUNTIME_DIR.glob(f"{prefix}*.pid"))


def _is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


# -------------------------------------------------------
# STATUS
# -------------------------------------------------------


def chains_status() -> Dict[str, dict]:
    """
    Show status of all detached chain runtimes.
    """
    status = {}

    for pid_file in _runtime_pid_files("det_chain_"):
        name = pid_file.stem.replace("det_chain_", "")
        pid, port = read_pid_and_port(pid_file)

        alive = pid is not None and _is_pid_alive(pid)

        status[name] = {
            "pid": pid,
            "port": port,
            "alive": alive,
        }

        icon = "🟢" if alive else "🔴"
        print(f"{icon} chain={name} pid={pid} port={port}")

    if not status:
        print("ℹ️ No detached chain runtimes found")

    return status


def agents_status() -> Dict[str, dict]:
    """
    Show status of all detached agent runtimes.
    """
    status = {}

    for pid_file in _runtime_pid_files("det_agent_"):
        name = pid_file.stem.replace("det_agent_", "")
        pid, port = read_pid_and_port(pid_file)

        alive = pid is not None and _is_pid_alive(pid)

        status[name] = {
            "pid": pid,
            "port": port,
            "alive": alive,
        }

        icon = "🟢" if alive else "🔴"
        print(f"{icon} agent={name} pid={pid} port={port}")

    if not status:
        print("ℹ️ No detached agent runtimes found")

    return status


# -------------------------------------------------------
# RESTART
# -------------------------------------------------------


def _restart_runtime(name: str, pid: int, port: int, kind: str):
    """
    Kill and restart a detached runtime.
    kind: 'chain' or 'agent'
    """
    if pid:
        logger.info(f"🔄 Restarting {kind} {name} (pid={pid})")
        try:
            os.kill(pid, 9)
        except ProcessLookupError:
            pass

    time.sleep(0.5)

    cmd = ["treehopper", kind, "start", name, "--bg"]
    subprocess.Popen(cmd)

    print(f"🚀 Restart requested for {kind} {name}")


def chains_restart(name: str | None = None):
    runtimes = chains_status()
    logger.info(runtimes)

    for chain, info in runtimes.items():
        if name and chain.split("-")[0] != name:
            continue
        _restart_runtime(chain, info["pid"], info["port"], "chain")


def agents_restart(name: str | None = None):
    runtimes = agents_status()

    for agent, info in runtimes.items():
        if name and agent.split("-")[0] != name:
            continue
        _restart_runtime(agent, info["pid"], info["port"], "agent")
