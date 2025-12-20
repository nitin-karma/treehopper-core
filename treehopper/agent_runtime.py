# import os
from treehopper.treehopper import AGENT_PATH_MAP
from treehopper.runtime_context import get_run_id
from treehopper.treehopper_cancellation import is_run_cancelled
import asyncio
import traceback

# ======================================================================
# 🔥 CRITICAL: DISCOVER AGENTS IN RUNTIME PROCESS
# ======================================================================
# from treehopper.treehopper import discover_agents

# print("[runtime] Discovering agents...")
# discover_agents()
# print("[runtime] Agent discovery complete")


async def run_agent_path(path: str, params: dict):
    print(f"checking path {path}")
    """
    Lightweight clone of _run_agent_path — without importing chromadb,
    agents, memory, main server components or anything heavy.
    """

    # Normalize path
    if not path.startswith("/api/v1/agents/"):
        path = f"/api/v1/agents{path if path.startswith('/') else '/' + path}"

    if path not in AGENT_PATH_MAP:
        # from dotenv import load_dotenv
        # load_dotenv()
        # print(f"[agent_runtime] {os.environ}")
        raise RuntimeError(f"Agent path not found: {path}")

    wrapper = AGENT_PATH_MAP[path]["handler"]

    run_id = get_run_id()
    if run_id and await is_run_cancelled(run_id):
        raise asyncio.CancelledError()

    try:
        result = await wrapper(params)
    except asyncio.CancelledError:
        raise
    except Exception as e:
        print(f"[agent runtime] - {str(e)}")
        traceback.print_exc()
        raise

    if run_id and await is_run_cancelled(run_id):
        raise asyncio.CancelledError()

    return result
