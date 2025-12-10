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

# from datetime import datetime

# ======================================================================
# 2. Third-Party Imports
# ======================================================================
from fastapi import FastAPI, Body, HTTPException, Request, APIRouter
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi import Security
from fastapi.security import APIKeyHeader
from fastapi.openapi.utils import get_openapi

# ======================================================================
# 3. Local/Project Imports
# ======================================================================
from treehopper.th_config import VERSION, DEFAULT_API_KEY
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
API_KEY = os.getenv("TREEHOPPER_API_KEY", DEFAULT_API_KEY)
API_KEY_HEADER = APIKeyHeader(name="x-api-key", auto_error=False)
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


app.openapi_schema = None


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version="1.0",
        routes=app.routes,
    )

    # Define API key security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "APIKeyHeader": {"type": "apiKey", "in": "header", "name": "x-api-key"}
    }

    # Apply to all endpoints
    for path in openapi_schema["paths"]:
        for method in openapi_schema["paths"][path]:
            openapi_schema["paths"][path][method]["security"] = [{"APIKeyHeader": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


# ======================================================================
# STATIC + DOCS
# ======================================================================
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


async def verify_api_key(key: str = Security(API_KEY_HEADER)):
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return key


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


def _load_run_json(run_file: Path) -> Optional[Dict[str, Any]]:
    try:
        txt = run_file.read_text()
        return json.loads(txt)
    except Exception:
        return None


@app.get(f"/api/v1/{CHAIN_NAME}/status/{{run_id}}")
async def chain_status(run_id: str, api_key: str = Security(verify_api_key)):
    if not CHAIN_DIR:
        raise HTTPException(500, "CHAIN_DIR not configured")

    run_file = CHAIN_DIR / "runs" / f"{run_id}.json"
    if not run_file.exists():
        raise HTTPException(404, f"run_id {run_id} not found")

    try:
        data = json.loads(run_file.read_text())

        # IMPORTANT: flatten "status" to top-level to match test script
        return {
            "ok": True,
            "status": data.get("status"),
            "current_step_index": data.get("current_step_index"),
            "cancelled": data.get("cancelled"),
            "success": data.get("success"),
            "raw": data,
        }
    except Exception as e:
        raise HTTPException(500, f"Failed loading status: {e}")


# ======================================================================
# CANCEL ROUTER
# ======================================================================
runtime_cancel = APIRouter(prefix="/api/v1/cancel")


@runtime_cancel.post("/run/{run_id}")
async def runtime_local_cancel(run_id: str, api_key: str = Security(verify_api_key)):
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
async def run_chain(
    request: Request,
    payload: dict = Body(default={}),
    api_key: str = Security(verify_api_key),
):
    print("[CHAIN RUN TIME] to run the chain")
    agents_spec: List[Dict[str, Any]] = CHAIN_CFG.get("agents", [])
    if not agents_spec:
        raise HTTPException(status_code=400, detail="Chain has no agents configured")

    root_payload = payload or {}
    run_id = request.headers.get("X-Treehopper-Run-Id") or request.headers.get(
        "x-treehopper-run-id"
    )
    batch_id = request.headers.get("X-Treehopper-Batch-Id") or request.headers.get(
        "x-treehopper-batch-id"
    )

    # 🟢 If Swagger or curl didn't send run_id → auto-generate one
    if not run_id:
        run_id = run_registry_mod.make_run_id(CHAIN_NAME)
        print(f"[runtime] Auto-generated run_id={run_id} (Swagger/manual call)")

    print(f"[runtime] Using CHAIN_DIR = {CHAIN_DIR}")
    print(f"[runtime] CANCEL_DIR = {CANCEL_DIR}")

    # -------------------------------
    # PENDING (written only once)
    # -------------------------------
    run_registry_mod.record_chain_run(
        chain_name=CHAIN_NAME,
        chain_id=CHAIN_ID,
        chain_dir=CHAIN_DIR,
        payload=root_payload,
        results=[],
        detached=True,
        success=False,
        run_id=run_id,
        cancelled=False,
        status="pending",
        current_step_index=-1,
    )

    token = set_run_id(run_id)

    async def _execute_chain():
        nonlocal root_payload
        results: List[Any] = []
        prev_output: Dict[str, Any] | None = None

        # -------------------------------
        # STARTING
        # -------------------------------
        run_registry_mod.record_chain_run(
            chain_name=CHAIN_NAME,
            chain_id=CHAIN_ID,
            chain_dir=CHAIN_DIR,
            payload=root_payload,
            results=results,
            detached=True,
            success=False,
            run_id=run_id,
            cancelled=False,
            status="starting",
            current_step_index=-1,
        )

        for idx, step in enumerate(agents_spec):
            path = step.get("path")
            inputs = step.get("inputs", [])

            # -------------------------------
            # PRE-CANCEL CHECK
            # -------------------------------
            print(f"[RUNTIME] Pre-step cancel check for step {idx}, run_id={run_id}")
            if await is_run_cancelled(run_id):
                print(f"[RUNTIME] CANCELLED before starting step {idx}")
                return run_registry_mod.record_chain_run(
                    chain_name=CHAIN_NAME,
                    chain_id=CHAIN_ID,
                    chain_dir=CHAIN_DIR,
                    payload=root_payload,
                    results=results,
                    detached=True,
                    success=False,
                    run_id=run_id,
                    cancelled=True,
                    status="cancelled",
                    current_step_index=idx,
                )

            # -------------------------------
            # PREP INPUTS
            # -------------------------------
            if idx == 0:
                params = dict(root_payload)
            else:
                params = {}
                if prev_output:
                    if inputs:
                        for inp in inputs:
                            nm = inp.get("name")
                            if nm in prev_output:
                                params[nm] = prev_output[nm]
                    else:
                        params = dict(prev_output)

            # ======================================================
            # ⭐ CRITICAL FIX ⭐ — deterministic "running" state write
            # ======================================================
            run_registry_mod.record_chain_run(
                chain_name=CHAIN_NAME,
                chain_id=CHAIN_ID,
                chain_dir=CHAIN_DIR,
                payload=root_payload,
                results=results,
                detached=True,
                success=False,
                run_id=run_id,
                cancelled=False,
                status="running",
                current_step_index=idx,
            )
            # ======================================================

            # -------------------------------
            # FINAL CANCEL CHECK BEFORE EXEC
            # -------------------------------
            if await is_run_cancelled(run_id):
                print(f"[RUNTIME] CANCELLED just before executing step {idx}")
                return run_registry_mod.record_chain_run(
                    chain_name=CHAIN_NAME,
                    chain_id=CHAIN_ID,
                    chain_dir=CHAIN_DIR,
                    payload=root_payload,
                    results=results,
                    detached=True,
                    success=False,
                    run_id=run_id,
                    cancelled=True,
                    status="cancelled",
                    current_step_index=idx,
                )

            # -------------------------------
            # EXECUTE AGENT
            # -------------------------------
            try:
                print(f"[RUNTIME] Executing step {idx} via {path} (run_id={run_id})")
                step_result = await cancellation_guard(
                    run_agent_path(path, params), run_id, idx
                )
            except asyncio.CancelledError:
                print(f"[cancellation_guard] CANCELLED at step={idx}, run_id={run_id}")
                return run_registry_mod.record_chain_run(
                    chain_name=CHAIN_NAME,
                    chain_id=CHAIN_ID,
                    chain_dir=CHAIN_DIR,
                    payload=root_payload,
                    results=results,
                    detached=True,
                    success=False,
                    run_id=run_id,
                    cancelled=True,
                    status="cancelled",
                    current_step_index=idx,
                )
            except Exception as e:
                print(f"[RUNTIME] Step {idx} failed: {e}")
                return run_registry_mod.record_chain_run(
                    chain_name=CHAIN_NAME,
                    chain_id=CHAIN_ID,
                    chain_dir=CHAIN_DIR,
                    payload=root_payload,
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

        # -------------------------------
        # COMPLETED SUCCESSFULLY
        # -------------------------------
        return run_registry_mod.record_chain_run(
            chain_name=CHAIN_NAME,
            chain_id=CHAIN_ID,
            chain_dir=CHAIN_DIR,
            payload=root_payload,
            results=results,
            detached=True,
            success=True,
            run_id=run_id,
            cancelled=False,
            status="completed",
            current_step_index=len(results) - 1,
        )

    # ---------------------------------------------------
    # WRAP WITH CANCELLATION REGISTRATION
    # ---------------------------------------------------
    try:
        wrapped = await run_with_cancellation(
            run_id=run_id,
            chain_id=CHAIN_ID or CHAIN_NAME,
            batch_id=batch_id,
            coro=_execute_chain(),
        )
    finally:
        reset_run_id(token)

    # ---------------------------------------------------
    # GLOBAL CANCEL RETURN
    # ---------------------------------------------------
    if isinstance(wrapped, dict) and wrapped.get("cancelled"):
        run_registry_mod.record_chain_run(
            chain_name=CHAIN_NAME,
            chain_id=CHAIN_ID,
            chain_dir=CHAIN_DIR,
            payload=root_payload,
            results=wrapped.get("results", []),
            detached=True,
            success=False,
            run_id=run_id,
            cancelled=True,
            status="cancelled",
        )

    return wrapped
