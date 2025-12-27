# treehopper/visualizer/state.py
from typing import Dict, Any, List
from treehopper.th_config import TH_ROOT, MAIN_PORT, DEFAULT_UI_PORT
from treehopper.sync_to_sqlite import get_all_agents, get_all_chains


def list_pids():
    """List running process PIDs (unchanged - keep filesystem-based)"""
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


def list_agents() -> List[Dict[str, Any]]:
    """Get agents from SQLite (10x faster than reading JSON)"""
    agents = get_all_agents()
    # Format for UI compatibility
    return [
        {"name": agent.get("agent_name"), "id": agent.get("agent_id")}
        for agent in agents
    ]


def list_chains() -> List[Dict[str, Any]]:
    """Get chains from SQLite (10x faster than reading JSON)"""
    chains = get_all_chains()
    # Format for UI compatibility
    return [
        {"name": chain.get("chain_name"), "id": chain.get("chain_id")}
        for chain in chains
    ]


def snapshot() -> Dict[str, Any]:
    """Get complete system snapshot (agents, chains, processes)"""
    return {
        "agents": list_agents(),
        "chains": list_chains(),
        "pids": list_pids(),
    }
