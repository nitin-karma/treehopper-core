import os
import json
from datetime import datetime
from typing import Any, Dict, List

from fastapi import FastAPI, Body, HTTPException
from treehopper.treehopper import _run_agent_path, VERSION
from treehopper.treehopper_chains import load_chain_cfg, resolve_chain

CHAIN_NAME = os.getenv("CHAIN_NAME")
if not CHAIN_NAME:
    raise RuntimeError("CHAIN_NAME environment variable required")

app = FastAPI(title=f"Treehopper v{VERSION} Chain Runtime ({CHAIN_NAME})")


def _load_cfg():
    chain_ref = resolve_chain(CHAIN_NAME)
    cfg = load_chain_cfg(chain_ref)
    agents = cfg.get("agents", [])
    return chain_ref, cfg, agents


@app.get("/")
async def root():
    return {"status": "ok", "runtime": "chain", "chain": CHAIN_NAME}


@app.get(f"/api/v1/{CHAIN_NAME}/health")
async def health():
    return {"status": "ok", "chain": CHAIN_NAME}


@app.post(f"/api/v1/{CHAIN_NAME}/run")
async def run_chain(payload: dict = Body(...)):
    """
    Body format must match main server:
      { "file_path": "...", ... }
    """
    chain_ref, cfg, agents = _load_cfg()
    if not agents:
        raise HTTPException(status_code=400, detail="No agents in chain")

    results: List[Dict[str, Any]] = []
    prev_output = None

    for idx, step in enumerate(agents):
        path = step["path"]
        inputs = step.get("inputs", [])

        if idx == 0:
            params = {}
            for inp in inputs:
                k = inp.get("name")
                if k not in payload:
                    missing_inputs = [
                        k for k in [i["name"] for i in inputs] if k not in payload
                    ]
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Missing required input(s) for first step '{step['agent_name']}': "
                            f"{missing_inputs}"
                        ),
                    )
                params[k] = payload[k]
        else:
            params = {}
            if isinstance(prev_output, dict):
                for inp in inputs:
                    k = inp.get("name")
                    if k in prev_output:
                        params[k] = prev_output[k]

        try:
            out = await _run_agent_path(path, params)
        except Exception as e:
            results.append({"error": str(e)})
            return {
                "success": False,
                "failed_step": idx,
                "failed_agent": step.get("agent_name"),
                "executed_at": datetime.utcnow().isoformat() + "Z",
                "results": results,
                "detached": True,
            }

        results.append(out)
        prev_output = out

    history = {
        "chain_name": CHAIN_NAME,
        "executed_at": datetime.utcnow().isoformat() + "Z",
        "input": payload,
        "results": results,
        "detached": True,
    }
    (chain_ref.dir_path / "last_run.json").write_text(
        json.dumps(history, indent=2), encoding="utf-8"
    )
    return history
