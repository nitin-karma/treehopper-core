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
from typing import Any, Dict, Optional, cast

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
# ======================================================================
# BUILTIN RUNTIME PRIMITIVES (NOT AGENTS)
# ======================================================================


def builtin_language_detect(text: Optional[str]) -> Dict[str, Any]:
    if not text or not isinstance(text, str):
        return {"language": "unknown", "confidence": 0.0}

    t = text.lower()
    if any(w in t for w in (" the ", " and ", " is ", " of ")):
        return {"language": "en", "confidence": 0.95}

    return {"language": "unknown", "confidence": 0.4}


def builtin_merge_parallel(parallel_results: list) -> Dict[str, Any]:
    """
    Generic fan-in merge.
    Deterministic, last-write-wins.
    """
    merged: Dict[str, Any] = {}

    for item in parallel_results:
        output = item.get("output", {})
        if isinstance(output, dict):
            merged.update(output)

    # Optional enrichment
    text = merged.get("extracted_text") or merged.get("text")
    if text:
        merged["_meta"] = builtin_language_detect(text)

    return merged


BUILTIN_MERGE_RUNTIME = {
    "smart_data_aggregator": builtin_merge_parallel,
    "default": builtin_merge_parallel,
}


def normalize_chain_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Backward compatibility:
    Convert v1 chain format (agents[]) → v2 steps[]
    """
    if "steps" in cfg:
        return cfg

    agents = cfg.get("agents", [])
    if not agents:
        raise RuntimeError("Invalid chain config: no agents or steps defined")

    steps = []
    for idx, agent in enumerate(agents):
        steps.append(
            {
                "step_id": f"step_{idx+1}",
                "execution_mode": "sequential",
                "agents": [agent],
            }
        )

    cfg["steps"] = steps
    return cfg


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
# ✅ ADD THIS LINE
CHAIN_CFG = normalize_chain_cfg(CHAIN_CFG)

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
# Helper Functions
# ======================================================================


def resolve_input(
    source: Optional[str],
    state: Dict[str, Dict[str, Any]],
    root_payload: Dict[str, Any],
    fallback_key: Optional[str] = None,
):
    """
    Resolution order:
    1. Explicit source: step.agent.field
    2. Implicit: previous step's agent output by key
    3. Request payload fallback
    """
    print(
        f"[resolve_input] source={source}, key={fallback_key}, "
        f"state_keys={list(state.keys())}, "
    )
    # 1️⃣ Explicit mapping
    if source:
        if source == "request":
            # request means entire request payload OR direct key
            if fallback_key and fallback_key in root_payload:
                return root_payload[fallback_key]
            return root_payload
        try:
            step, agent, field = source.split(".", 2)
            return state.get(step, {}).get(agent, {}).get(field)
        except Exception:
            return None

    # 2️⃣ IMPLICIT SEQUENTIAL MAPPING
    if state and fallback_key:
        step_ids = list(state.keys())
        if len(step_ids) >= 2:
            prev_step_id = step_ids[-2]
            for agent_output in state.get(prev_step_id, {}).values():
                if isinstance(agent_output, dict) and fallback_key in agent_output:
                    return agent_output[fallback_key]

    # 3️⃣ Request payload fallback
    if fallback_key:
        return root_payload.get(fallback_key)
    return None


def flatten_namespaced(step_id: str, agent: str, output: Dict[str, Any]):
    flat = {}
    for k, v in output.items():
        flat[f"{step_id}.{agent}.{k}"] = v
    return flat


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
    steps = CHAIN_CFG.get("steps", [])
    if not steps:
        raise HTTPException(status_code=400, detail="Chain has no steps configured")

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

        steps = CHAIN_CFG.get("steps", [])
        runtime_state: Dict[str, Dict[str, Any]] = {}
        namespaced: Dict[str, Any] = {}

        run_registry_mod.record_chain_run(
            chain_name=CHAIN_NAME,
            chain_id=CHAIN_ID,
            chain_dir=CHAIN_DIR,
            payload=root_payload,
            results=[],
            detached=True,
            success=False,
            run_id=run_id,
            status="starting",
            current_step_index=-1,
        )

        step_index = 0

        while step_index < len(steps):
            step = steps[step_index]
            step_id = step["step_id"]
            mode = step.get("execution_mode", "sequential")
            agents = step.get("agents", [])
            merge_agent = step.get("merge_agent")
            routes = step.get("route_on", [])

            runtime_state[step_id] = {}

            run_registry_mod.record_chain_run(
                chain_name=CHAIN_NAME,
                chain_id=CHAIN_ID,
                chain_dir=CHAIN_DIR,
                payload=root_payload,
                results=[],
                detached=True,
                success=False,
                run_id=run_id,
                status="running",
                current_step_index=step_index,
            )

            # -------------------------
            # SEQUENTIAL STEP
            # -------------------------

            if mode == "sequential":
                ag = agents[0]
                params = {}
                for inp in ag.get("inputs", []):
                    val = resolve_input(
                        inp.get("source"),
                        runtime_state,
                        root_payload,
                        fallback_key=inp["name"],
                    )
                    params[inp["name"]] = val
                print(
                    f"[runtime] Step={step_id}, Agent={ag['agent_name']}, Params={params}"
                )
                result = await cancellation_guard(
                    run_agent_path(ag["path"], params),
                    run_id,
                    step_index,
                )

                runtime_state[step_id][ag["agent_name"]] = result
                namespaced.update(flatten_namespaced(step_id, ag["agent_name"], result))

                step_output = result

            # -------------------------
            # PARALLEL STEP
            # -------------------------
            else:

                async def run_one(agent):
                    params = {}
                    for inp in agent.get("inputs", []):
                        params[inp["name"]] = resolve_input(
                            inp.get("source"),
                            runtime_state,
                            root_payload,
                            fallback_key=inp["name"],
                        )
                    out = await cancellation_guard(
                        run_agent_path(agent["path"], params),
                        run_id,
                        step_index,
                    )
                    return {"agent": agent["agent_name"], "output": out}

                parallel_results = await asyncio.gather(*[run_one(a) for a in agents])

                for item in parallel_results:
                    runtime_state[step_id][item["agent"]] = item["output"]
                    namespaced.update(
                        flatten_namespaced(step_id, item["agent"], item["output"])
                    )

                # ---- MERGE ----
                # ---- MERGE (BUILTIN, LOCKED) ----
                merge_key = merge_agent or "default"

                merge_fn = BUILTIN_MERGE_RUNTIME.get(merge_key)
                if not merge_fn:
                    raise RuntimeError(
                        f"Unknown merge-agent '{merge_key}'. "
                        f"Available: {list(BUILTIN_MERGE_RUNTIME.keys())}"
                    )

                step_output = merge_fn(parallel_results)

            # -------------------------
            # CONDITIONAL ROUTING
            # -------------------------
            jumped = False
            for rule in routes:
                expr = rule["if"].replace("output.", "")
                try:
                    if eval(expr, {}, step_output):
                        target = rule["goto"]
                        step_index = next(
                            i for i, s in enumerate(steps) if s["step_id"] == target
                        )
                        jumped = True
                        break
                except Exception:
                    pass

            if not jumped:
                step_index += 1

        return run_registry_mod.record_chain_run(
            chain_name=CHAIN_NAME,
            chain_id=CHAIN_ID,
            chain_dir=CHAIN_DIR,
            payload=root_payload,
            results=runtime_state,
            detached=True,
            success=True,
            run_id=run_id,
            status="completed",
            current_step_index=len(steps) - 1,
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
