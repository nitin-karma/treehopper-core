import os
from datetime import datetime
from typing import Any, Dict, List

from fastapi import FastAPI, Body, HTTPException
from pydantic import BaseModel

from treehopper.treehopper import _run_agent_path, VERSION

CHAIN_NAME = os.getenv("CHAIN_NAME")

if not CHAIN_NAME:
    raise RuntimeError(
        "CHAIN_NAME environment variable is required for chain runtime. "
        "Example: CHAIN_NAME=exec_summ uvicorn treehopper.chain_runtime_app:app ..."
    )


class ChainRunBody(BaseModel):
    agents: List[Dict[str, Any]]
    payload: Dict[str, Any] = {}


app = FastAPI(title=f"Treehopper v{VERSION} Chain Runtime ({CHAIN_NAME})")


@app.get("/")
async def root():
    return {"status": "ok", "runtime": "chain", "chain": CHAIN_NAME}


@app.get(f"/api/v1/{CHAIN_NAME}/health")
async def health():
    # We don't check the actual chain registry here; this micro-app is
    # stateless and relies on the caller to pass the agents spec.
    return {"status": "ok", "chain": CHAIN_NAME}


@app.post(f"/api/v1/{CHAIN_NAME}/run")
async def run_chain(body: ChainRunBody = Body(...)):
    """
    Stateless chain runner.

    Caller must send:
      {
        "agents": [ { "agent_name": ..., "path": "/api/v1/agents/...", "inputs": [...], ... }, ... ],
        "payload": { ... }  # root payload for first agent
      }

    We execute the sequence locally using treehopper._run_agent_path.
    """
    agents_spec = body.agents or []
    payload = body.payload or {}

    if not agents_spec:
        raise HTTPException(
            status_code=400, detail="No agents provided in 'agents' list"
        )

    results: List[Dict[str, Any]] = []
    prev_output: Dict[str, Any] | None = None

    for idx, step in enumerate(agents_spec):
        path = step.get("path")
        inputs = step.get("inputs", [])
        agent_name = step.get("agent_name")

        if not path:
            raise HTTPException(
                status_code=400, detail=f"Missing 'path' for step index {idx}"
            )

        # Build params for this step
        if idx == 0:
            # First step: params from root payload
            if inputs:
                params: Dict[str, Any] = {}
                for inp in inputs:
                    key = inp.get("name")
                    if key and key in payload:
                        params[key] = payload[key]
            else:
                params = dict(payload)
        else:
            params = {}
            if prev_output is not None and isinstance(prev_output, dict):
                if inputs:
                    for inp in inputs:
                        key = inp.get("name")
                        if key and key in prev_output:
                            params[key] = prev_output[key]
                else:
                    params = dict(prev_output)

        try:
            result = await _run_agent_path(path, params)
        except HTTPException as e:
            # structured failure response including partial results
            results.append({"error": e.detail if hasattr(e, "detail") else str(e)})
            return {
                "success": False,
                "failed_step": idx,
                "failed_agent": agent_name,
                "executed_at": datetime.utcnow().isoformat() + "Z",
                "results": results,
            }
        except Exception as e:
            results.append({"error": str(e)})
            return {
                "success": False,
                "failed_step": idx,
                "failed_agent": agent_name,
                "executed_at": datetime.utcnow().isoformat() + "Z",
                "results": results,
            }

        results.append(result)
        prev_output = result if isinstance(result, dict) else {"result": result}

    return {
        "success": True,
        "chain_name": CHAIN_NAME,
        "executed_at": datetime.utcnow().isoformat() + "Z",
        "results": results,
    }
