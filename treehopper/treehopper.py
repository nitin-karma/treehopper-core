# treehopper/treehopper.py
import os

if os.getenv("TREEHOPPER_RUNTIME_MODE") == "1":
    CHROMA_DISABLED = True
else:
    CHROMA_DISABLED = False
from datetime import datetime
import sys
import traceback
from pathlib import Path
import importlib.util
from importlib.abc import Loader
from types import ModuleType
import inspect
import json
import subprocess
from fastapi import FastAPI, Request, APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.security import APIKeyHeader

# REMOVED: from fastapi.openapi.utils import get_openapi
from dotenv import load_dotenv
import chromadb

from typing import Any
import yaml
from pydantic import BaseModel

# local imports
from treehopper.utils.run_registry import (
    record_chain_run,
    list_chain_runs as rr_list_chain_runs,
    # REMOVED: get_chain_run as rr_get_chain_run,
)
from treehopper.utils.config import read_config
from treehopper.th_config import (
    # REMOVED: HOME,
    # REMOVED: TH_ROOT,
    REGISTRY_AGENTS,
    REGISTRY_DIR,
    REGISTRY_AGENTS_INDEX,
    CHAINS_DIR,
    CHAINS_INDEX,
    VERSION,
)
from treehopper.logging import get_logger

logger = get_logger()
logger.info("Inside Main Server")
load_dotenv()

# -------------------------------------------------------
# FASTAPI ROOT
# -------------------------------------------------------
app = FastAPI(
    title="Treehopper Agentic API",
    docs_url=None,
    redoc_url=None,
    version=VERSION,
)


# -------------------------------------------------------
# simple memory / chroma init (unchanged)
# -------------------------------------------------------
if not CHROMA_DISABLED:
    TH_TEST_MODE = os.getenv("TH_TEST_MODE") == "1"

    if TH_TEST_MODE:
        memory = chromadb.EphemeralClient()
    else:
        memory = chromadb.PersistentClient(path=".treehopper_memory")

    collection = memory.get_or_create_collection("treehopper_memory")


# -------------------------------------------------------
# ROUTERS + API key header
# -------------------------------------------------------
api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)

router_agents = APIRouter(
    prefix="/api/v1/agents",
    tags=["Agents"],
    dependencies=[Depends(api_key_header)],
)

router_dev = APIRouter(
    prefix="/api/v1/dev",
    tags=["Devtools"],
    dependencies=[Depends(api_key_header)],
)

router_chains = APIRouter(
    prefix="/api/v1/chains",
    tags=["Chains"],
    dependencies=[Depends(api_key_header)],
)

router_sys = APIRouter(prefix="/api/v1/sys", tags=["System"])

# developer-facing agents list (keeps route + metadata)
agents: dict[str, dict] = {}

# NEW: global mapping used by runtimes to call handlers by path
# AGENT_PATH_MAP[path] = {
#   "handler": async callable that accepts a single dict `params`,
#   "orig": original function,
#   "method": "GET"/"POST",
#   "body_model": pydantic model class or None
# }
AGENT_PATH_MAP: dict[str, dict] = {}


# -------------------------------------------------------
# AGENT DECORATOR (routes go to router_agents)
# -------------------------------------------------------
def agent(
    path: str, method: str = "GET", goal: str = "", tags: list[str] | None = None
):
    if tags is None:
        tags = []

    full_path = (
        path
        if path.startswith("/api/v1/agents/")
        else f"/api/v1/agents/{path.lstrip('/')}"
    )

    def decorator(func):
        # register in agents mapping for dev listing
        agents[full_path] = {"func": func, "method": method, "goal": goal, "tags": tags}

        # inspect signature to detect pydantic body param
        sig = inspect.signature(func)
        body_param_name = None
        body_model = None

        # Expectation (Option-2): handler accepts a single payload param annotated with a Pydantic model
        # Find first param whose annotation has __fields__ (pydantic) or is subclass of BaseModel
        for pname, p in sig.parameters.items():
            ann = p.annotation
            if inspect.isclass(ann) and issubclass(ann, BaseModel):
                body_param_name = pname
                body_model = ann
                break
            # duck-type: pydantic BaseModel also exposes __fields__
            if hasattr(ann, "__fields__"):
                body_param_name = pname
                body_model = ann
                break

        # Build a runtime wrapper that accepts a dict of params and calls the original func
        async def handler_for_runtime(params: dict):
            """
            Called by runtime (run_agent_path). Receives a dict `params`
            built from chain inputs. This function:
              - Instantiates the pydantic model if declared
              - Calls the original handler as orig(payload=model_instance)
            """
            try:
                call_kwargs = {}
                if body_model:
                    try:
                        model_instance = body_model(**params)
                    except Exception as e:
                        # surface model validation errors clearly
                        raise RuntimeError(
                            f"Failed to build payload model {body_model}: {e}"
                        )
                    call_kwargs[body_param_name] = model_instance
                else:
                    # fallback: pass entire params as `payload` if the handler expects a single arg named 'payload'
                    # or if no pydantic model is annotated, call with payload=params
                    # find a sensible single-arg name
                    if len(sig.parameters) == 1:
                        pname = next(iter(sig.parameters.keys()))
                        call_kwargs[pname] = params
                    else:
                        # For multiple primitive params, try to map by name
                        for pname in sig.parameters.keys():
                            if pname in params:
                                call_kwargs[pname] = params[pname]

                if inspect.iscoroutinefunction(func):
                    return await func(**call_kwargs)
                else:
                    return func(**call_kwargs)
            except Exception:
                # Keep traceback for debugging (runtime logs)
                traceback.print_exc()
                raise

        # register wrapper into AGENT_PATH_MAP (runtime call path)
        AGENT_PATH_MAP[full_path] = {
            "handler": handler_for_runtime,
            "orig": func,
            "method": method.upper(),
            "body_model": body_model,
            "body_param_name": body_param_name,
        }

        # Register into FastAPI router as before (route handlers will still be the original function)
        route_path = full_path.replace("/api/v1/agents", "") or "/"
        if method.upper() == "GET":
            router_agents.get(route_path, tags=tags)(func)
        else:
            router_agents.post(route_path, tags=tags)(func)

        return func

    return decorator


# -------------------------------------------------------
# Auto-resume on server startup (unchanged)
# -------------------------------------------------------
@app.on_event("startup")
async def maybe_auto_resume():
    cfg = read_config()
    if not cfg.get("auto_resume"):
        return
    for folder in CHAINS_DIR.iterdir():
        last = folder / "last_run.json"
        if not last.exists():
            continue
        try:
            data = json.loads(last.read_text())
        except Exception:
            continue
        if data.get("status") in ("running", "failed", "pending") and not data.get(
            "cancelled"
        ):
            run_id = data["run_id"]
            subprocess.Popen(["treehopper", "chain", "resume", run_id])


# -------------------------------------------------------
# FAVICON & DOCS (unchanged)
# -------------------------------------------------------
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(os.path.join(STATIC_DIR, "treehopper_favicon.png"))


@app.get("/docs", include_in_schema=False)
async def custom_docs():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="Treehopper Agentic API",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
        swagger_favicon_url="/static/treehopper_favicon.png",
    )


# -------------------------------------------------------
# AUTH MIDDLEWARE (unchanged)
# -------------------------------------------------------
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    public_exact = {
        "/",
        "/favicon",
        "/favicon.ico",
        "/docs",
        "/openapi.json",
        "/health",
        "/version",
        "/api/v1/sys/health",
        "/api/v1/sys/version",
    }
    public_prefix = ("/static",)

    if request.url.path in public_exact or request.url.path.startswith(public_prefix):
        return await call_next(request)

    key = request.headers.get("x-api-key") or request.headers.get("X-API-Key")
    if key != "demo-key-123":
        return JSONResponse(status_code=403, content={"error": "Invalid API key"})

    return await call_next(request)


# -------------------------------------------------------
# SYSTEM & DEV endpoints (slightly adjusted to use AGENT_PATH_MAP)
# -------------------------------------------------------
@app.get("/", include_in_schema=False)
@app.get("/health", include_in_schema=False)
@router_sys.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/version", include_in_schema=False)
@router_sys.get("/version")
async def version():
    return {"treehopper": f"v{VERSION}"}


@router_dev.get("/agents")
async def list_agents():
    # return routes from agents dict (as before)
    return [
        {"path": p, "method": a["method"], "goal": a["goal"], "tags": a["tags"]}
        for p, a in agents.items()
    ]


@router_dev.get("/chains")
async def list_chains():
    logger.info("[MAIN RUN TIME] to list the chain")
    results: list[dict] = []
    if CHAINS_DIR.is_dir():
        for folder in CHAINS_DIR.iterdir():
            cfg_path = folder / "chain.yaml"
            if not cfg_path.exists():
                continue
            try:
                cfg = yaml.safe_load(cfg_path.read_text())
            except Exception:
                continue
            results.append(
                {
                    "chain_name": cfg.get("chain_name"),
                    "chain_id": cfg.get("chain_id"),
                    "endpoint": cfg.get("endpoint"),
                    "agents": [a.get("agent_name") for a in cfg.get("agents", [])],
                    "created_at": cfg.get("created_at"),
                }
            )
    return results


# ===============================================================
# GLOBAL RUN STATUS ENDPOINT  (MAIN SERVER)
# ===============================================================


@router_chains.get("/status/{run_id}")
async def global_run_status(run_id: str):
    """
    Global lookup: Searches all chain run folders in ~/.treehopper/registry/chains/*
    and returns unified structured status info.
    """
    registry_chains = Path(REGISTRY_DIR) / "chains"

    if not registry_chains.exists():
        return {"ok": False, "error": "registry_missing", "run_id": run_id}

    # search all chains
    for chain_folder in registry_chains.glob("*"):
        run_file = chain_folder / "runs" / f"{run_id}.json"
        if run_file.exists():
            try:
                data = json.loads(run_file.read_text())
                stat = run_file.stat()
                return {
                    "ok": True,
                    "run_id": run_id,
                    "chain_name": data.get("chain_name"),
                    "chain_id": data.get("chain_id"),
                    "status": data.get("status"),
                    "current_step_index": data.get("current_step_index"),
                    "cancelled": data.get("cancelled", False),
                    "success": data.get("success", False),
                    "last_updated": datetime.utcfromtimestamp(stat.st_mtime).isoformat()
                    + "Z",
                    "raw": data,
                }
            except Exception as e:
                return {"ok": False, "error": f"parse_failure: {e}", "run_id": run_id}

    return {"ok": False, "error": "run_not_found", "run_id": run_id}


# -------------------------------------------------------
# CORE: _run_agent_path (used by chain runtime)
# -------------------------------------------------------
# async def _run_agent_path(path: str, params: dict):
#     print("[MAIN RUN TIME] Agent execution from main server")
#     """
#     Called by chain runtime app. Uses AGENT_PATH_MAP to find the runtime wrapper.
#     Ensures cancellation BEFORE and AFTER calling the handler.
#     """
#     import asyncio
#     from treehopper.runtime_context import get_run_id
#     from treehopper.treehopper_cancellation import is_run_cancelled

#     # Normalize path forms to full_path
#     if not path.startswith("/api/v1/agents/"):
#         path = f"/api/v1/agents{path if path.startswith('/') else '/' + path}"

#     if path not in AGENT_PATH_MAP:
#         raise RuntimeError(f"Agent path not found: {path}")

#     wrapper = AGENT_PATH_MAP[path]["handler"]

#     # 1) cancellation check BEFORE call
#     run_id = get_run_id()
#     if run_id:
#         cancelled = await is_run_cancelled(run_id)
#         if cancelled:
#             print(f"[treehopper:_run_agent_path] CANCEL detected BEFORE calling {path}")
#             raise asyncio.CancelledError()

#     # 2) execute wrapper (which will instantiate Pydantic model and call original handler)
#     try:
#         result = await wrapper(params)
#     except asyncio.CancelledError:
#         print(f"[treehopper:_run_agent_path] CANCELLED WHILE executing {path}")
#         raise
#     except Exception as e:
#         print(f"[treehopper:_run_agent_path] ERROR executing {path}: {e}")
#         traceback.print_exc()
#         raise

#     # 3) cancellation check AFTER call (some handlers might take long to return)
#     if run_id:
#         cancelled = await is_run_cancelled(run_id)
#         if cancelled:
#             print(
#                 f"[treehopper:_run_agent_path] CANCEL detected AFTER executing {path}"
#             )
#             raise asyncio.CancelledError()

#     return result


# -------------------------------------------------------
# helper used by the /api/v1/dev/chain route — maps params -> call
# -------------------------------------------------------
async def _execute_agent_step(path: str, params: dict) -> dict:
    """
    For dev synchronous chain runner: adapt to AGENT_PATH_MAP if available,
    otherwise fall back to old `agents` mapping.
    Returns a dict result (ensures JSON-serializable)
    """
    # normalize full path
    if not path.startswith("/api/v1/agents/"):
        path = f"/api/v1/agents{path if path.startswith('/') else '/' + path}"

    # Prefer AGENT_PATH_MAP runtime wrapper
    if path in AGENT_PATH_MAP:
        wrapper = AGENT_PATH_MAP[path]["handler"]
        res = await wrapper(params)
    else:
        # older fallback: find de-registered function in agents dict
        if path not in agents:
            raise HTTPException(status_code=404, detail=f"Agent not found: {path}")
        func = agents[path]["func"]
        sig = inspect.signature(func)

        # Build call kwargs (primitive mapping or dict payload)
        call_kwargs = {}
        if len(sig.parameters) == 1:
            pname = next(iter(sig.parameters.keys()))
            ann = sig.parameters[pname].annotation
            if (
                inspect.isclass(ann)
                and issubclass(ann, BaseModel)
                or hasattr(ann, "__fields__")
            ):
                # instantiate Pydantic model if annotated
                try:
                    call_kwargs[pname] = ann(**params)
                except Exception as e:
                    raise HTTPException(status_code=400, detail=str(e))
            else:
                # pass params as dict
                call_kwargs[pname] = params
        else:
            # multiple params mapping
            for pname in sig.parameters.keys():
                if pname in params:
                    call_kwargs[pname] = params[pname]

        res = (
            await func(**call_kwargs)
            if inspect.iscoroutinefunction(func)
            else func(**call_kwargs)
        )

    # unwrap JSONResponse like before
    if hasattr(res, "body"):
        try:
            res = json.loads(res.body.decode())
        except Exception:
            pass

    if not isinstance(res, dict):
        return {"value": res}
    return res


@router_chains.post("/{chain_name}/run")
async def run_chain_endpoint(chain_name: str, payload: dict | None = None):
    """
    Main-server chain runner.

    Semantics:
      - First agent gets the root payload (validated against its declared inputs).
      - Subsequent agents get params mapped from previous step's output.
      - Full run is recorded via run_registry (last_run + runs/<run_id>.json).
    """
    print("[run_chain_endpoint] starting")
    cfg, chain_dir = resolve_chain_by_name(chain_name)
    agents_cfg = cfg.get("agents", [])

    if not agents_cfg:
        raise HTTPException(
            status_code=400, detail=f"Chain has no agents: {chain_name}"
        )

    results: list[Any] = []
    prev_output: dict[str, Any] | None = None
    root_payload: dict[str, Any] = payload or {}

    for idx, step in enumerate(agents_cfg):
        # Validate FIRST STEP required inputs exist
        if idx == 0:
            declared = [i.get("name") for i in step.get("inputs", []) if i.get("name")]
            missing = [d for d in declared if d not in root_payload]
            if missing:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Missing required input(s) for first step "
                        f"'{step.get('agent_name')}': {missing}"
                    ),
                )

        # Build params for execution
        if idx == 0:
            params: dict[str, Any] = dict(root_payload)
        else:
            params = {}
            for inp in step.get("inputs", []):
                k = inp.get("name")
                if k and isinstance(prev_output, dict) and k in prev_output:
                    params[k] = prev_output[k]

        result = await _execute_agent_step(step["path"], params)
        results.append(result)
        prev_output = result if isinstance(result, dict) else {"result": result}

    # delegate persistence to run_registry (also writes last_run.json)
    history = record_chain_run(
        chain_name=cfg.get("chain_name", chain_name),
        chain_id=cfg.get("chain_id"),
        chain_dir=chain_dir,
        payload=root_payload,
        results=results,
        detached=False,
        success=True,
    )
    return history


@router_chains.get("/{chain_name}/runs")
async def list_chain_runs(chain_name: str, limit: int = 50):
    """
    List recent runs for a chain (summary).
    """
    cfg, chain_dir = resolve_chain_by_name(chain_name)
    runs = rr_list_chain_runs(chain_dir, limit=limit)
    return {
        "chain_name": cfg.get("chain_name", chain_name),
        "chain_id": cfg.get("chain_id"),
        "runs": runs,
    }


@router_dev.post("/chain", include_in_schema=False)
async def chain(body: dict):
    outputs: list[dict] = []
    for step in body.get("chain", []):
        result = await _execute_agent_step(step["path"], step.get("params", {}))
        outputs.append(result)
    return {"results": outputs}


# -------------------------------------------------------
# DEVSTORE / SEARCH (unchanged)
# -------------------------------------------------------
@app.post("/api/v1/dev/store", tags=["Devtools"])
async def store(key: str, content: str):
    collection.add(documents=[content], ids=[key], embeddings=[[0.1] * 384])
    return {"status": "stored"}


@app.get("/api/v1/dev/search", tags=["Devtools"])
async def search(query: str):
    r = collection.query(query_texts=[query], n_results=3)
    return {"results": {"documents": r.get("documents", [[]])[0]}}


# -------------------------------------------------------
# AGENT DISCOVERY (unchanged behavior; decorator fills AGENT_PATH_MAP)
# -------------------------------------------------------
def load_module_from_path(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or not isinstance(spec.loader, Loader):
        raise ImportError(f"Invalid spec for: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def ensure_pkg(name: str, path: Path | None = None):
    if name in sys.modules:
        return
    pkg = ModuleType(name)
    if path:
        pkg.__path__ = [str(path)]
    sys.modules[name] = pkg


def get_agent_id(agent_name: str) -> str | None:
    agent_name = agent_name.lower().strip()
    if not REGISTRY_AGENTS_INDEX.exists():
        return None
    try:
        agents_list = json.loads(REGISTRY_AGENTS_INDEX.read_text())
    except Exception:
        return None
    for a in agents_list:
        if a.get("agent_name", "").lower() == agent_name:
            return a.get("agent_id")
    return None


def get_chain_id(chain_name: str) -> str | None:
    chain_name = chain_name.lower().strip()
    if not CHAINS_INDEX.exists():
        return None
    try:
        chains_list = json.loads(CHAINS_INDEX.read_text())
    except Exception:
        return None
    for chain in chains_list:
        if chain.get("chain_name", "").lower() == chain_name:
            return chain.get("chain_id")
    return None


def load_chains_index() -> list[dict]:
    if not CHAINS_INDEX.exists():
        return []
    try:
        return json.loads(CHAINS_INDEX.read_text())
    except Exception:
        return []


def resolve_chain_by_name(chain_name: str) -> tuple[dict, Path]:
    chain_name = chain_name.strip().lower()
    index = load_chains_index()
    chain_id = None
    for c in index:
        if c.get("chain_name", "").lower() == chain_name:
            chain_id = c.get("chain_id")
            break
    if not chain_id:
        if CHAINS_DIR.is_dir():
            for folder in CHAINS_DIR.iterdir():
                cfg_path = folder / "chain.yaml"
                if not cfg_path.exists():
                    continue
                try:
                    cfg = yaml.safe_load(cfg_path.read_text())
                except Exception:
                    continue
                if cfg.get("chain_name", "").lower() == chain_name:
                    return cfg, folder
        raise HTTPException(status_code=404, detail=f"Chain not found: {chain_name}")
    chain_dir = CHAINS_DIR / chain_id
    cfg_path = chain_dir / "chain.yaml"
    if not cfg_path.exists():
        raise HTTPException(status_code=404, detail=f"Chain config missing: {chain_id}")
    try:
        cfg = yaml.safe_load(cfg_path.read_text())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Invalid chain.yaml: {e}")
    return cfg, chain_dir


# -------------------------------------------------------
# Discovery: load builtin + registry agents (calls decorator, which populates AGENT_PATH_MAP)
# -------------------------------------------------------
def discover_agents():
    # Skip discovery in pytest in-memory mode except when CLI needs it
    if os.getenv("PYTEST_CURRENT_TEST"):
        cli_commands = {"run", "call", "build", "lint", "init"}
        if not any(cmd in sys.argv for cmd in cli_commands):
            logger.info(
                "🧪 Pytest in-memory mode: skipping folder agent auto-discovery"
            )
            return

    core_dir = os.path.join(os.path.dirname(__file__), "agents")
    if os.path.isdir(core_dir):
        for f in os.listdir(core_dir):
            if f.endswith(".py") and not f.startswith("_"):
                load_module_from_path(
                    f"treehopper_builtin_{f}", os.path.join(core_dir, f)
                )

    if REGISTRY_AGENTS.is_dir():
        ensure_pkg("treehopper_user", REGISTRY_AGENTS)
        for agent_dir in REGISTRY_AGENTS.iterdir():
            if not agent_dir.is_dir():
                continue
            pkg = f"treehopper_user.{agent_dir.name}"
            ensure_pkg(pkg, agent_dir)
            schema = agent_dir / "schema.py"
            handler = agent_dir / "handler.py"
            if schema.exists():
                load_module_from_path(f"{pkg}.schema", str(schema))
            if handler.exists():
                load_module_from_path(f"{pkg}.handler", str(handler))


discover_agents()

# Register routers (unchanged)
app.include_router(router_agents)
app.include_router(router_dev)
app.include_router(router_sys)
app.include_router(router_chains)
