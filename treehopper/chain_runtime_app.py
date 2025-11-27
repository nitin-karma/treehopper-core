# chain_runtime_app.py
import os
from pathlib import Path
from typing import Any, Dict, List, cast

from fastapi import FastAPI, Body, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.openapi.docs import get_swagger_ui_html
import yaml

from treehopper.treehopper import _run_agent_path, VERSION
from treehopper.utils import run_registry as run_registry_mod
from treehopper.treehopper_cancellation import (
    run_with_cancellation,
    is_run_cancelled,  # <-- REQUIRED FOR PATCH C
)

CHAIN_NAME = cast(str, os.getenv("CHAIN_NAME"))
CHAIN_ID = os.getenv("CHAIN_ID")
CHAIN_DIR_ENV = os.getenv("CHAIN_DIR")

if not CHAIN_NAME:
    raise RuntimeError("CHAIN_NAME environment variable is required for chain runtime.")

CHAIN_DIR: Path | None = None
CHAIN_CFG: Dict[str, Any] = {}

if CHAIN_DIR_ENV:
    CHAIN_DIR = Path(CHAIN_DIR_ENV)
    cfg_path = CHAIN_DIR / "chain.yaml"
    if not cfg_path.exists():
        raise RuntimeError(f"chain.yaml not found at {cfg_path}")
    CHAIN_CFG = yaml.safe_load(cfg_path.read_text())
else:
    CHAIN_CFG = {"chain_name": CHAIN_NAME, "agents": []}

app = FastAPI(title=f"Treehopper v{VERSION} Chain Runtime ({CHAIN_NAME})")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


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


# ------------------------------------------------------------------------------
# PATCH C + PATCH E APPLIED BELOW
# ------------------------------------------------------------------------------


@app.post(f"/api/v1/{CHAIN_NAME}/run")
async def run_chain(request: Request, payload: dict = Body(default={})):
    """
    Chain micro-app execution:
      • Reads run_id/batch_id from headers
      • Executes agents sequentially
      • Checks cancellation BEFORE every agent step   (Patch C)
      • Writes cancellation to history correctly     (Patch E)
    """

    agents_spec: List[Dict[str, Any]] = CHAIN_CFG.get("agents", [])
    if not agents_spec:
        raise HTTPException(status_code=400, detail="Chain has no agents configured")

    root_payload: Dict[str, Any] = payload or {}
    results: List[Any] = []
    prev_output: Dict[str, Any] | None = None

    # Extract run_id + batch_id from headers (PATCH D)
    run_id = request.headers.get("X-Treehopper-Run-Id") or run_registry_mod.make_run_id(
        CHAIN_NAME
    )
    batch_id = request.headers.get("X-Treehopper-Batch-Id")

    async def _execute_chain():
        nonlocal results, prev_output

        for idx, step in enumerate(agents_spec):
            agent_name = step.get("agent_name")
            path = step.get("path")
            inputs = step.get("inputs", [])

            # ------------------------------------------------------------------
            # PATCH C: Check cancellation BEFORE running any step
            # ------------------------------------------------------------------
            if is_run_cancelled(run_id):
                cancelled_result = {
                    "cancelled": True,
                    "run_id": run_id,
                    "results": results,
                    "success": False,
                }
                # persist cancellation (PATCH E)
                run_registry_mod.record_chain_run(
                    chain_name=CHAIN_NAME,
                    chain_id=CHAIN_ID,
                    chain_dir=CHAIN_DIR,
                    payload=root_payload,
                    results=results,
                    detached=True,
                    success=False,
                    run_id=run_id,
                    cancelled=True,
                )
                return cancelled_result

            if not path:
                error_res = results + [
                    {"error": f"Missing path for step {idx} - {agent_name}"}
                ]
                return run_registry_mod.record_chain_run(
                    CHAIN_NAME,
                    CHAIN_ID,
                    CHAIN_DIR,
                    root_payload,
                    error_res,
                    detached=True,
                    success=False,
                    run_id=run_id,
                )

            # Build params
            if idx == 0:
                params = dict(root_payload)
            else:
                params = {}
                if prev_output and isinstance(prev_output, dict):
                    if inputs:
                        for inp in inputs:
                            name = inp.get("name")
                            if name in prev_output:
                                params[name] = prev_output[name]
                    else:
                        params = dict(prev_output)

            # Execute agent
            try:
                step_result = await _run_agent_path(path, params)
            except Exception as e:
                return run_registry_mod.record_chain_run(
                    CHAIN_NAME,
                    CHAIN_ID,
                    CHAIN_DIR,
                    root_payload,
                    results + [{"error": str(e)}],
                    detached=True,
                    success=False,
                    run_id=run_id,
                )

            results.append(step_result)
            prev_output = (
                step_result
                if isinstance(step_result, dict)
                else {"result": step_result}
            )

        # Normal success
        return run_registry_mod.record_chain_run(
            CHAIN_NAME,
            CHAIN_ID,
            CHAIN_DIR,
            root_payload,
            results,
            detached=True,
            success=True,
            run_id=run_id,
        )

    # Wrap with cancellation wrapper
    wrapped = await run_with_cancellation(
        run_id=run_id,
        chain_id=CHAIN_ID or CHAIN_NAME,
        batch_id=batch_id,
        coro=_execute_chain(),
    )

    # If the wrapper reports cancellation → persist (Patch E)
    if isinstance(wrapped, dict) and wrapped.get("cancelled"):
        run_registry_mod.record_chain_run(
            chain_name=CHAIN_NAME,
            chain_id=CHAIN_ID,
            chain_dir=CHAIN_DIR,
            payload=root_payload,
            results=results,
            detached=True,
            success=False,
            run_id=run_id,
            cancelled=True,  # now valid (signature modified)
        )
        return wrapped

    return wrapped
