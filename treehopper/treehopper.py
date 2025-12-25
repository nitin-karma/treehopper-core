# treehopper/treehopper.py
import os
import sys
import json
import inspect
import traceback
import subprocess
from datetime import datetime
from pathlib import Path
from types import ModuleType
from importlib.abc import Loader
import importlib.util
from typing import Any
from fastapi import FastAPI, Request, APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.security import APIKeyHeader

from dotenv import load_dotenv
import chromadb
import yaml
from pydantic import BaseModel

# -------------------------------------------------------
# LOCAL IMPORTS
# -------------------------------------------------------
from treehopper.utils.run_registry import (
    record_chain_run,
    list_chain_runs as rr_list_chain_runs,
)
from treehopper.utils.config import read_config
from treehopper.th_config import (
    REGISTRY_AGENTS,
    REGISTRY_DIR,
    REGISTRY_AGENTS_INDEX,
    CHAINS_DIR,
    CHAINS_INDEX,
    VERSION,
)
from treehopper.logging import get_logger
from treehopper.utils.commons import load_chains_index

# -------------------------------------------------------
# ENV / FLAGS
# -------------------------------------------------------
load_dotenv()

CHROMA_DISABLED = os.getenv("TREEHOPPER_RUNTIME_MODE") == "1"
TH_TEST_MODE = os.getenv("TH_TEST_MODE") == "1"

logger = get_logger()

# -------------------------------------------------------
# GLOBAL STATE (SAFE)
# -------------------------------------------------------
agents: dict[str, dict] = {}
AGENT_PATH_MAP: dict[str, dict] = {}

# -------------------------------------------------------
# CHROMA MEMORY (unchanged behaviour)
# -------------------------------------------------------
if not CHROMA_DISABLED:
    if TH_TEST_MODE:
        memory = chromadb.EphemeralClient()
    else:
        memory = chromadb.PersistentClient(path=".treehopper_memory")
    collection = memory.get_or_create_collection("treehopper_memory")

# -------------------------------------------------------
# ROUTERS
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


# -------------------------------------------------------
# AGENT DECORATOR (UNCHANGED SEMANTICS)
# -------------------------------------------------------
def agent(
    path: str, method: str = "GET", goal: str = "", tags: list[str] | None = None
):
    tags = tags or []
    full_path = (
        path
        if path.startswith("/api/v1/agents/")
        else f"/api/v1/agents/{path.lstrip('/')}"
    )

    def decorator(func):
        agents[full_path] = {
            "func": func,
            "method": method.upper(),
            "goal": goal,
            "tags": tags,
        }

        sig = inspect.signature(func)
        body_param = None
        body_model = None

        for pname, p in sig.parameters.items():
            ann = p.annotation
            if inspect.isclass(ann) and issubclass(ann, BaseModel):
                body_param = pname
                body_model = ann
                break
            if hasattr(ann, "__fields__"):
                body_param = pname
                body_model = ann
                break

        async def runtime_handler(params: dict):
            try:
                kwargs = {}
                if body_model:
                    kwargs[body_param] = body_model(**params)
                else:
                    if len(sig.parameters) == 1:
                        kwargs[next(iter(sig.parameters))] = params
                    else:
                        for k in sig.parameters:
                            if k in params:
                                kwargs[k] = params[k]

                if inspect.iscoroutinefunction(func):
                    return await func(**kwargs)
                return func(**kwargs)
            except Exception:
                traceback.print_exc()
                raise

        AGENT_PATH_MAP[full_path] = {
            "handler": runtime_handler,
            "orig": func,
            "method": method.upper(),
        }

        route = full_path.replace("/api/v1/agents", "") or "/"
        if method.upper() == "GET":
            router_agents.get(route, tags=tags)(func)
        else:
            router_agents.post(route, tags=tags)(func)

        return func

    return decorator


# -------------------------------------------------------
# AGENT EXECUTION
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


# -------------------------------------------------------
# CHAIN RESOLUTION
# -------------------------------------------------------
def resolve_chain_by_name(chain_name: str) -> tuple[dict, Path]:
    name = chain_name.lower().strip()

    for c in load_chains_index():
        if c.get("chain_name", "").lower() == name:
            chain_dir = CHAINS_DIR / c["chain_id"]
            cfg = yaml.safe_load((chain_dir / "chain.yaml").read_text())
            return cfg, chain_dir

    if CHAINS_DIR.exists():
        for d in CHAINS_DIR.iterdir():
            cfg_file = d / "chain.yaml"
            if not cfg_file.exists():
                continue
            cfg = yaml.safe_load(cfg_file.read_text())
            if cfg.get("chain_name", "").lower() == name:
                return cfg, d

    raise HTTPException(status_code=404, detail=f"Chain not found: {chain_name}")


# -------------------------------------------------------
# DEV ENDPOINTS (RESTORED)
# -------------------------------------------------------
@router_dev.get("/agents")
async def list_agents():
    return [
        {"path": p, "method": a["method"], "goal": a["goal"], "tags": a["tags"]}
        for p, a in agents.items()
    ]


@router_dev.get("/chains")
async def list_chains():
    results: list[dict] = []
    default_chain_type = "Single-step, sequential"

    if CHAINS_DIR.is_dir():
        for folder in CHAINS_DIR.iterdir():
            cfg_path = folder / "chain.yaml"
            if not cfg_path.exists():
                continue
            try:
                cfg = yaml.safe_load(cfg_path.read_text())
            except Exception:
                continue

            # Ensure cfg is not None
            if not cfg:
                continue

            if "steps" in cfg:
                steps = cfg.get("steps", [])
                execution_modes = [s.get("execution_mode") for s in steps]

                chain_type = (
                    f"Multi-step, {'-->'.join(execution_modes)}"
                    if len(execution_modes) > 1
                    else f"Multi-step, {execution_modes[0]}"
                )

                agents_list = []
                for s in steps:
                    agents_list.append(
                        {
                            s.get("execution_mode", "SEQUENTIAL").upper(): [
                                a.get("agent_name") for a in s.get("agents", [])
                            ]
                        }
                    )
            else:
                chain_type = default_chain_type
                agents_list = [
                    {"SEQUENTIAL": [a.get("agent_name") for a in cfg.get("agents", [])]}
                ]

            results.append(
                {
                    "chain_name": cfg.get("chain_name"),
                    "chain_id": cfg.get("chain_id"),
                    "chain_type": chain_type,
                    "endpoint": cfg.get("endpoint"),
                    "agents": agents_list,
                    "created_at": cfg.get("created_at"),
                }
            )

    return results


# -------------------------------------------------------
# CHAIN EXECUTION
# -------------------------------------------------------
@router_chains.post("/{chain_name}/run")
async def run_chain_endpoint(chain_name: str, payload: dict | None = None):
    """
    Main-server chain runner (sequential chains only).

    Semantics:
      - First agent gets root payload
      - Only REQUIRED inputs are validated
      - Optional inputs are skipped if missing
      - Subsequent agents receive outputs from previous step
    """
    print("[run_chain_endpoint] starting from main server")

    cfg, chain_dir = resolve_chain_by_name(chain_name)
    print(cfg, chain_dir)

    if "steps" in cfg:
        raise HTTPException(
            status_code=400,
            detail=(
                "This chain uses multi-step execution.\n"
                "Multi-step / parallel / routed chains must be run in detached mode.\n\n"
                "Use:\n"
                f"  th chain run {chain_name} --detached"
            ),
        )

    agents_cfg = cfg.get("agents", [])
    print(agents_cfg)

    if not agents_cfg:
        raise HTTPException(
            status_code=400, detail=f"Chain has no agents: {chain_name}"
        )

    results: list[Any] = []
    prev_output: dict[str, Any] | None = None
    root_payload: dict[str, Any] = payload or {}

    for idx, step in enumerate(agents_cfg):

        inputs = step.get("inputs", [])

        # -------------------------------
        # FIRST STEP VALIDATION (FIXED)
        # -------------------------------
        if idx == 0:
            required_inputs = [
                i["name"] for i in inputs if i.get("name") and i.get("required", True)
            ]

            missing = [k for k in required_inputs if k not in root_payload]
            if missing:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Missing required input(s) for first step "
                        f"'{step.get('agent_name')}': {missing}"
                    ),
                )

        # -------------------------------
        # PARAM BUILDING
        # -------------------------------
        if idx == 0:
            params: dict[str, Any] = dict(root_payload)
        else:
            params = {}
            if isinstance(prev_output, dict):
                for inp in inputs:
                    name = inp.get("name")
                    if not name:
                        continue
                    if name in prev_output:
                        params[name] = prev_output[name]
                    # optional inputs are silently skipped

        result = await _execute_agent_step(step["path"], params)
        print(result)
        results.append(result)
        prev_output = result if isinstance(result, dict) else {"result": result}

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


@router_chains.get("/{chain_name}/runs")
async def list_chain_runs(chain_name: str, limit: int = 50):
    cfg, chain_dir = resolve_chain_by_name(chain_name)
    return {
        "chain_name": cfg["chain_name"],
        "chain_id": cfg["chain_id"],
        "runs": rr_list_chain_runs(chain_dir, limit=limit),
    }


@router_dev.post("/chain", include_in_schema=False)
async def chain(body: dict):
    outputs: list[dict] = []
    for step in body.get("chain", []):
        result = await _execute_agent_step(step["path"], step.get("params", {}))
        outputs.append(result)
    return {"results": outputs}


# -------------------------------------------------------
# DEVSTORE / SEARCH (FIXED – router based)
# -------------------------------------------------------
@router_dev.post("/store", tags=["Devtools"])
async def store(key: str, content: str):
    collection.add(
        documents=[content],
        ids=[key],
        embeddings=[[0.1] * 384],
    )
    return {"status": "stored"}


@router_dev.get("/search", tags=["Devtools"])
async def search(query: str):
    r = collection.query(query_texts=[query], n_results=3)
    return {"results": {"documents": r.get("documents", [[]])[0]}}


# -------------------------------------------------------
# SYSTEM
# -------------------------------------------------------
@router_sys.get("/health")
async def health():
    return {"status": "ok"}


@router_sys.get("/version")
async def version():
    return {"treehopper": f"v{VERSION}"}


# -------------------------------------------------------
# DISCOVERY
# -------------------------------------------------------
def load_module_from_path(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not isinstance(spec.loader, Loader):
        raise ImportError(path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


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


def discover_agents():
    if os.getenv("PYTEST_CURRENT_TEST"):
        if not any(cmd in sys.argv for cmd in {"run", "call", "build"}):
            return

    builtin = Path(__file__).parent / "agents"
    if builtin.exists():
        for f in builtin.glob("*.py"):
            if not f.name.startswith("_"):
                load_module_from_path(f"treehopper_builtin_{f.stem}", str(f))

    if REGISTRY_AGENTS.exists():
        ensure_pkg("treehopper_user", REGISTRY_AGENTS)
        for d in REGISTRY_AGENTS.iterdir():
            ensure_pkg(f"treehopper_user.{d.name}", d)
            for f in ("schema.py", "handler.py"):
                p = d / f
                if p.exists():
                    load_module_from_path(f"treehopper_user.{d.name}.{p.stem}", str(p))


# -------------------------------------------------------
# APP FACTORY (🔥 FIXES CI + TEST ISSUES)
# -------------------------------------------------------
def get_app() -> FastAPI:
    from treehopper.th_config import ensure_dirs

    ensure_dirs()  # 🔥 forces paths to reflect current TH_ROOT

    from treehopper.registry import reload_registry

    reload_registry()

    app = FastAPI(
        title="Treehopper Agentic API",
        docs_url=None,
        redoc_url=None,
        version=VERSION,
    )

    discover_agents()

    app.include_router(router_agents)
    app.include_router(router_dev)
    app.include_router(router_sys)
    app.include_router(router_chains)

    STATIC_DIR = Path(__file__).parent / "static"
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    # -------------------------------------------------------
    # CUSTOM DOCS & FAVICON
    # -------------------------------------------------------
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

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        # Whitelist public endpoints
        public_paths = {
            "/",
            "/health",
            "/version",
            "/docs",
            "/favicon.ico",  # ✅ Add favicon to whitelist
            "/openapi.json",
            "/api/v1/sys/health",
            "/api/v1/sys/version",
        }

        if request.url.path.startswith("/static") or request.url.path in public_paths:
            return await call_next(request)

        if request.headers.get("x-api-key") != "demo-key-123":
            return JSONResponse(status_code=403, content={"error": "Invalid API key"})

        return await call_next(request)

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
                subprocess.Popen(["treehopper", "chain", "resume", data["run_id"]])

    return app


# -------------------------------------------------------
# ASGI ENTRYPOINT
# -------------------------------------------------------
app = get_app()
