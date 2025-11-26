# chain_runtime_app.py
import os

# import json
# from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, cast

from fastapi import FastAPI, Body, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# from pydantic import BaseModel

from treehopper.treehopper import _run_agent_path, VERSION
from treehopper.utils.run_registry import record_chain_run

import yaml
from fastapi.openapi.docs import get_swagger_ui_html

# from treehopper.utils.ui_assets import inject_branding

CHAIN_NAME = cast(str, os.getenv("CHAIN_NAME"))
CHAIN_ID = os.getenv("CHAIN_ID")
CHAIN_DIR_ENV = os.getenv("CHAIN_DIR")

if not CHAIN_NAME:
    raise RuntimeError(
        "CHAIN_NAME environment variable is required for chain runtime. "
        "Example: CHAIN_NAME=exec_summ uvicorn treehopper.chain_runtime_app:app ..."
    )

CHAIN_DIR: Path | None = None
CHAIN_CFG: Dict[str, Any] = {}

if CHAIN_DIR_ENV:
    CHAIN_DIR = Path(CHAIN_DIR_ENV)
    cfg_path = CHAIN_DIR / "chain.yaml"
    if not cfg_path.exists():
        raise RuntimeError(f"chain.yaml not found at {cfg_path}")
    try:
        CHAIN_CFG = yaml.safe_load(cfg_path.read_text())
    except Exception as e:
        raise RuntimeError(f"Failed to read chain.yaml: {e}") from e
else:
    # still allow running for debugging, but without persistence
    CHAIN_CFG = {"chain_name": CHAIN_NAME, "agents": []}


app = FastAPI(title=f"Treehopper v{VERSION} Chain Runtime ({CHAIN_NAME})")

# __file__ is treehopper/chain_runtime_app.py
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
# STATIC_DIR = os.path.abspath(STATIC_DIR)  # normalize to absolute path

if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# inject_branding(app, f"Agent Runtime: {AGENT_NAME}")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(os.path.join(STATIC_DIR, "treehopper_favicon.ico"))


@app.get("/docs", include_in_schema=False)
async def custom_docs():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title,
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
        favicon_url="/static/treehopper_favicon.ico",
    )


@app.get("/")
async def root():
    return {
        "status": "ok",
        "runtime": "chain",
        "chain": CHAIN_NAME,
        "chain_id": CHAIN_ID,
    }


@app.get(f"/api/v1/{CHAIN_NAME}/health")
async def health():
    return {"status": "ok", "chain": CHAIN_NAME, "chain_id": CHAIN_ID}


@app.post(f"/api/v1/{CHAIN_NAME}/run")
async def run_chain(payload: dict = Body(default={})):
    """
    Micro-app chain runner.

    Behaves like main server's /api/v1/chains/{name}:
      - Accepts a JSON payload (e.g. {"file_path": "..."}).
      - Uses chain.yaml's agents list for execution order.
      - Records run via run_registry (detached=True).
    """
    agents_spec: List[Dict[str, Any]] = CHAIN_CFG.get("agents", [])
    if not agents_spec:
        raise HTTPException(status_code=400, detail="Chain has no agents configured")

    root_payload: Dict[str, Any] = payload or {}
    results: List[Any] = []
    prev_output: Dict[str, Any] | None = None

    # First-step validation
    first = agents_spec[0]
    declared = [i.get("name") for i in first.get("inputs", []) if i.get("name")]
    missing = [d for d in declared if d not in root_payload]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Missing required input(s) for first step "
                f"'{first.get('agent_name')}': {missing}"
            ),
        )

    for idx, step in enumerate(agents_spec):
        path = step.get("path")
        inputs = step.get("inputs", [])
        agent_name = step.get("agent_name")

        if not path:
            raise HTTPException(
                status_code=400,
                detail=f"Missing 'path' for step {idx} (agent: {agent_name})",
            )

        # Build params for this step
        if idx == 0:
            params: Dict[str, Any] = dict(root_payload)
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
            # treat as failed run, but still record it
            history = record_chain_run(
                chain_name=CHAIN_NAME,
                chain_id=CHAIN_ID,
                chain_dir=CHAIN_DIR,
                payload=root_payload,
                results=results
                + [{"error": e.detail if hasattr(e, "detail") else str(e)}],
                detached=True,
                success=False,
            )
            return history
        except Exception as e:
            history = record_chain_run(
                chain_name=CHAIN_NAME,
                chain_id=CHAIN_ID,
                chain_dir=CHAIN_DIR,
                payload=root_payload,
                results=results + [{"error": str(e)}],
                detached=True,
                success=False,
            )
            return history

        results.append(result)
        prev_output = result if isinstance(result, dict) else {"result": result}

    history = record_chain_run(
        chain_name=CHAIN_NAME,
        chain_id=CHAIN_ID,
        chain_dir=CHAIN_DIR,
        payload=root_payload,
        results=results,
        detached=True,
        success=True,
    )
    return history
