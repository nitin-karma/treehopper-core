import os
from typing import Any, Dict

from fastapi import FastAPI, Body, HTTPException
from fastapi.responses import JSONResponse

from treehopper.treehopper import _run_agent_path, VERSION

AGENT_NAME = os.getenv("AGENT_NAME")

if not AGENT_NAME:
    raise RuntimeError(
        "AGENT_NAME environment variable is required for agent runtime. "
        "Example: AGENT_NAME=formatter uvicorn treehopper.agent_runtime_app:app ..."
    )

app = FastAPI(title=f"Treehopper v{VERSION} Agent Runtime ({AGENT_NAME})")


@app.get("/")
async def root():
    return {"status": "ok", "runtime": "agent", "agent": AGENT_NAME}


@app.get(f"/api/v1/{AGENT_NAME}/health")
async def health():
    # Optional: check that the underlying agent is registered
    # We just trust discover_agents() in treehopper.treehopper for now.
    return {"status": "ok", "agent": AGENT_NAME}


@app.post(f"/api/v1/{AGENT_NAME}/run")
async def run_agent(payload: Dict[str, Any] = Body(...)):
    """
    Run the underlying Treehopper agent function directly
    using the shared in-process registry in treehopper.treehopper.

    This always uses POST with a JSON body.
    """
    agent_path = f"/api/v1/agents/{AGENT_NAME}"

    try:
        result = await _run_agent_path(agent_path, payload or {})
    except HTTPException as e:
        # propagate FastAPI HTTP errors as-is
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # _run_agent_path already normalizes to a dict
    if isinstance(result, dict):
        return JSONResponse(result)
    return JSONResponse({"value": result})
