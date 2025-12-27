# treehopper/visualizer/state.py
import json

# import os
# from pathlib import Path
from typing import Dict, Any, List
from treehopper.th_config import TH_ROOT, MAIN_PORT, DEFAULT_UI_PORT


def list_pids():
    runtime = TH_ROOT / "runtime"
    pids = {}
    if runtime.exists():
        for f in runtime.glob("*.pid"):
            try:
                _pid = f.read_text().strip()
                if ":" in _pid:
                    pids[f.name] = (
                        f"pid - {int(_pid.split(':')[0])}, port - {int(_pid.split(':')[1])}"
                    )
                elif f.name == "main_server.pid":
                    pids[f.name] = f"pid - {int(_pid)}, port - {int(MAIN_PORT)}"
                elif f.name == "ui.pid":
                    pids[f.name] = f"pid - {int(_pid)}, port - {int(DEFAULT_UI_PORT)}"
            except Exception as e:
                print(f"[list_pids] - {str(e)}")
                pass
    return pids


def list_agents() -> List[Dict[str, Any]]:  # Changed type hint from list[str]
    """Reads the agents.json file and returns a list of agent objects."""
    agents_index = TH_ROOT / "registry" / "agents.json"

    if not agents_index.exists():
        return []

    try:
        with agents_index.open("r", encoding="utf-8") as f:
            data = json.load(f)

        # Extraction logic remains the same, now matches the hint
        return [
            {"name": agent.get("agent_name"), "id": agent.get("agent_id")}
            for agent in data
            if "agent_name" in agent
        ]

    except (json.JSONDecodeError, IOError) as e:
        print(f"❌ Error reading agents index: {e}")
        return []


def list_chains() -> List[Dict[str, Any]]:  # Changed type hint from list[str]
    """Reads the chains.json file and returns a list of chain objects."""
    chains_index = TH_ROOT / "registry" / "chains.json"

    if not chains_index.exists():
        return []

    try:
        with chains_index.open("r", encoding="utf-8") as f:
            data = json.load(f)

        return [
            {"name": chain.get("chain_name"), "id": chain.get("chain_id")}
            for chain in data
            if "chain_name" in chain
        ]

    except (json.JSONDecodeError, IOError) as e:
        print(f"❌ Error reading chains index: {e}")
        return []


def snapshot() -> Dict[str, Any]:
    return {
        "agents": list_agents(),
        "chains": list_chains(),
        "pids": list_pids(),
    }
