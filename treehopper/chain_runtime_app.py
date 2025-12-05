# treehopper/chain_runtime_app.py

# ======================================================================
# 1. Standard Library Imports
# ======================================================================
import os
import sys
import json
import asyncio
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

# ======================================================================
# 2. Third-Party Imports
# ======================================================================
from fastapi import FastAPI, Body, HTTPException, Request, APIRouter
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html

# ======================================================================
# 3. Local/Project Imports
# ======================================================================
from treehopper.th_config import VERSION
import treehopper.th_config as _cfg
from treehopper.agent_runtime import run_agent_path
from treehopper.utils import run_registry as run_registry_mod
from treehopper.runtime_context import set_run_id, reset_run_id
from treehopper.middleware.cancellation_guard import cancellation_guard
from treehopper.treehopper_cancellation import (
    is_run_cancelled,
    update_cancel_marker_with_runtime,
    create_cancel_marker,
    run_with_cancellation,
)

# ======================================================================
# EXECUTION AND CONFIGURATION START
# All imports are now complete.
# ======================================================================

# Setting environment variables
os.environ["TREEHOPPER_RUNTIME_MODE"] = "1"

# ======================================================================
# FORCE LOCAL SOURCE (dev mode)
# ======================================================================
if os.getenv("TREEHOPPER_FORCE_LOCAL", "1") == "1":
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    print(f"[FORCE_LOCAL] Activated. Project root inserted → {PROJECT_ROOT}")
    print(f"[FORCE_LOCAL] sys.path[0] = {sys.path[0]}")

# ======================================================================
# TH_CONFIG OVERRIDES
# ======================================================================
ENV_TH_ROOT = os.getenv("TREEHOPPER_TH_ROOT")
ENV_RUNTIME_DIR = os.getenv("TREEHOPPER_RUNTIME_DIR")
ENV_CANCEL_DIR = os.getenv("TREEHOPPER_CANCEL_DIR")

if ENV_TH_ROOT:
    _cfg.TH_ROOT = Path(ENV_TH_ROOT).resolve()
if ENV_RUNTIME_DIR:
    _cfg.RUNTIME_DIR = Path(ENV_RUNTIME_DIR).resolve()
if ENV_CANCEL_DIR:
    _cfg.CANCEL_DIR = Path(ENV_CANCEL_DIR).resolve()

TH_ROOT = _cfg.TH_ROOT
RUNTIME_DIR = _cfg.RUNTIME_DIR
CANCEL_DIR = _cfg.CANCEL_DIR

print(f"[runtime] CANCEL_DIR = {CANCEL_DIR}")
print(f"[runtime] TH_ROOT = {TH_ROOT}")
print(f"[runtime] RUNTIME_DIR = {RUNTIME_DIR}")

CANCEL_DIR.mkdir(parents=True, exist_ok=True)

# ======================================================================
# DEV PYTHONPATH INJECTION
# ======================================================================
try:
    if os.getenv("TREEHOPPER_DEV_MODE") == "1":
        # Import moved here, but must be relative to the PROJECT_ROOT injected above
        from treehopper.environment import inject_pythonpath

        # FIX: Explicitly convert os.environ to a standard dict using dict()
        inject_pythonpath(dict(os.environ))
        print("[DEV_MODE] chain_runtime_app injected PYTHONPATH")
except Exception:
    pass
# ======================================================================
# ENV: CHAIN INFO
# ======================================================================
CHAIN_NAME = cast(str, os.getenv("CHAIN_NAME"))
CHAIN_ID = os.getenv("CHAIN_ID")
CHAIN_DIR_ENV = os.getenv("CHAIN_DIR")

if not CHAIN_NAME:
    raise RuntimeError("CHAIN_NAME environment variable is required for chain runtime.")

CHAIN_DIR: Optional[Path] = None
CHAIN_CFG: Dict[str, Any] = {}

if CHAIN_DIR_ENV:
    CHAIN_DIR = Path(CHAIN_DIR_ENV)
    cfg_path = CHAIN_DIR / "chain.yaml"
    if not cfg_path.exists():
        raise RuntimeError(f"chain.yaml not found at {cfg_path}")
    CHAIN_CFG = yaml.safe_load(cfg_path.read_text())
else:
    CHAIN_CFG = {"chain_name": CHAIN_NAME, "agents": []}

# ======================================================================
# FASTAPI APP
# ======================================================================
app = FastAPI(title=f"Treehopper v{VERSION} Chain Runtime ({CHAIN_NAME})")

# ======================================================================
# STATIC + DOCS
# ======================================================================
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


# ======================================================================
# HEALTH ENDPOINTS
# ======================================================================
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


# ======================================================================
# NEW: STATUS ENDPOINT (PATCH #3)
# ======================================================================
@app.get(f"/api/v1/{CHAIN_NAME}/status/{{run_id}}")
async def chain_status(run_id: str):
    """
    Dashboard & CLI helper:
      Returns last recorded state for run_id.
    """
    if not CHAIN_DIR:
        raise HTTPException(500, "CHAIN_DIR not configured")

    run_file = CHAIN_DIR / "runs" / f"{run_id}.json"
    if not run_file.exists():
        raise HTTPException(404, f"run_id {run_id} not found")

    try:
        return json.loads(run_file.read_text())
    except Exception as e:
        raise HTTPException(500, f"Failed loading status: {e}")


# ======================================================================
# CANCEL ROUTER
# ======================================================================
runtime_cancel = APIRouter(prefix="/api/v1/cancel")


@runtime_cancel.post("/run/{run_id}")
async def runtime_local_cancel(run_id: str):
    """
    RUNTIME LOCAL CANCEL ENDPOINT.
    Only updates FS marker — does not call central cancel routine.
    """
    print(f"[runtime cancel] Received cancel for run_id={run_id}")
    try:
        tag = f"runtime:{os.getpid()}"
        # NOTE: update_cancel_marker_with_runtime and create_cancel_marker
        # should exist in treehopper/treehopper_cancellation.py
        updated = update_cancel_marker_with_runtime(run_id, runtime_tag=tag)

        if updated:
            print(f"[runtime cancel] Updated cancel marker → {updated}")
        else:
            p = create_cancel_marker(run_id, source="runtime", modifier=tag)
            print(f"[runtime cancel] Created cancel marker → {p}")

    except Exception as e:
        print(f"[runtime cancel] ERROR updating marker: {e}")

    return {"ok": True}


app.include_router(runtime_cancel)


# ======================================================================
# DETACHED CHAIN EXECUTION ENDPOINT
# ======================================================================
@app.post(f"/api/v1/{CHAIN_NAME}/run")
async def run_chain(request: Request, payload: dict = Body(default={})):
    agents_spec: List[Dict[str, Any]] = CHAIN_CFG.get("agents", [])

    if not agents_spec:
        raise HTTPException(400, "Chain has no agents configured")

    run_id = request.headers.get("X-Treehopper-Run-Id")
    batch_id = request.headers.get("X-Treehopper-Batch-Id")

    if not run_id:
        raise HTTPException(400, "Detached runtime ERROR: missing run_id")

    # Mark run as starting
    run_registry_mod.record_chain_run(
        chain_name=CHAIN_NAME,
        chain_id=CHAIN_ID,
        chain_dir=CHAIN_DIR,
        payload=payload,
        results=[],
        detached=True,
        success=False,
        run_id=run_id,
        cancelled=False,
        status="starting",
        current_step_index=-1,
    )

    token = set_run_id(run_id)

    async def _execute_chain():
        results: List[Any] = []
        prev_output = None

        for idx, step in enumerate(agents_spec):
            # MARK RUNNING
            run_registry_mod.record_chain_run(
                chain_name=CHAIN_NAME,
                chain_id=CHAIN_ID,
                chain_dir=CHAIN_DIR,
                payload=payload,
                results=results,
                detached=True,
                success=False,
                run_id=run_id,
                cancelled=False,
                status="running",
                current_step_index=idx,
            )

            # PRE-CANCEL
            if await is_run_cancelled(run_id):
                return run_registry_mod.record_chain_run(
                    chain_name=CHAIN_NAME,
                    chain_id=CHAIN_ID,
                    chain_dir=CHAIN_DIR,
                    payload=payload,
                    results=results,
                    detached=True,
                    success=False,
                    run_id=run_id,
                    cancelled=True,
                    status="cancelled",
                    current_step_index=idx,
                )

            # PARAMS
            if idx == 0:
                params = dict(payload)
            else:
                params = {}
                if prev_output:
                    inputs = step.get("inputs", [])
                    if inputs:
                        for inp in inputs:
                            name = inp["name"]
                            if name in prev_output:
                                params[name] = prev_output[name]
                    else:
                        params = dict(prev_output)

            # EXECUTE AGENT
            try:
                step_result = await cancellation_guard(
                    run_agent_path(step["path"], params),
                    run_id,
                    idx,
                )
            except asyncio.CancelledError:
                return run_registry_mod.record_chain_run(
                    chain_name=CHAIN_NAME,
                    chain_id=CHAIN_ID,
                    chain_dir=CHAIN_DIR,
                    payload=payload,
                    results=results,
                    detached=True,
                    success=False,
                    run_id=run_id,
                    cancelled=True,
                    status="cancelled",
                    current_step_index=idx,
                )
            except Exception as e:
                return run_registry_mod.record_chain_run(
                    chain_name=CHAIN_NAME,
                    chain_id=CHAIN_ID,
                    chain_dir=CHAIN_DIR,
                    payload=payload,
                    results=results + [{"error": str(e)}],
                    detached=True,
                    success=False,
                    run_id=run_id,
                    cancelled=False,
                    status="failed",
                    current_step_index=idx,
                )

            results.append(step_result)
            prev_output = (
                step_result
                if isinstance(step_result, dict)
                else {"result": step_result}
            )

        # FINAL SUCCESS
        return run_registry_mod.record_chain_run(
            chain_name=CHAIN_NAME,
            chain_id=CHAIN_ID,
            chain_dir=CHAIN_DIR,
            payload=payload,
            results=results,
            detached=True,
            success=True,
            run_id=run_id,
            cancelled=False,
            status="completed",
            current_step_index=len(results) - 1,
        )

    # WRAP IN CANCELLATION CONTROLLER
    try:
        wrapped = await run_with_cancellation(
            run_id=run_id,
            chain_id=CHAIN_ID or CHAIN_NAME,
            batch_id=batch_id,
            coro=_execute_chain(),
        )
    finally:
        reset_run_id(token)

    return wrapped
