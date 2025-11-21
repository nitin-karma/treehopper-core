import os
import sys
from pathlib import Path
import importlib.util
from importlib.abc import Loader
from types import ModuleType
import inspect
import json

from fastapi import FastAPI, Request, APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.security import APIKeyHeader
from fastapi.openapi.utils import get_openapi
from dotenv import load_dotenv
import chromadb
from typing import Any

# from chromadb import Client
# from chromadb.config import Settings

# from chromadb import PersistentClient, EphemeralClient
# from chromadb.utils import embedding_functions
from pydantic import BaseModel
from typing import List, Dict

# if True:  # temporary debug
#     print("\n================= PYTEST ENV DEBUG (IMPORT TIME) =================")
#     for k, v in sorted(os.environ.items()):
#         print(f"{k} = {v}")
#     print("================= END PYTEST ENV DEBUG =================\n")

if os.getenv("TH_DEBUG_INIT") == "1":
    print("\n========== ENV DEBUG START ==========")
    for k, v in sorted(os.environ.items()):
        print(f"{k} = {v}")
    print("=========== ENV DEBUG END ===========\n")


class ChainStep(BaseModel):
    path: str
    params: Dict[str, Any] = {}


class ChainBody(BaseModel):
    chain: List[ChainStep]


load_dotenv()

api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)

HOME = Path.home()
TH_ROOT = HOME / ".treehopper"
REGISTRY_AGENTS = TH_ROOT / "registry" / "agents"
REGISTRY_DIR = TH_ROOT / "registry"
REGISTRY_AGENTS_INDEX = REGISTRY_DIR / "agents.json"
VERSION = "0.1.0"
# -------------------------------------------------------
# FASTAPI ROOT
# -------------------------------------------------------
app = FastAPI(
    title="Treehopper Agentic API",
    docs_url=None,
    redoc_url=None,
    version="0.1.0",
)


# ---------------- Swagger with API-Key -----------------
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title="Treehopper Agentic API",
        version="0.1.0",
        routes=app.routes,
    )

    schema["components"]["securitySchemes"] = {
        "APIKeyHeader": {"type": "apiKey", "in": "header", "name": "x-api-key"}
    }

    for path in schema["paths"].values():
        for method in path.values():
            method.setdefault("security", [{"APIKeyHeader": []}])

    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# -------------------------------------------------------
# MEMORY
# -------------------------------------------------------

TH_TEST_MODE = os.getenv("TH_TEST_MODE") == "1"

if TH_TEST_MODE:
    # In tests: fully in-memory, no files on disk
    memory = chromadb.EphemeralClient()
else:
    # In normal runs: persistent DB on disk
    memory = chromadb.PersistentClient(path=".treehopper_memory")

collection = memory.get_or_create_collection("treehopper_memory")

# -------------------------------------------------------
# ROUTERS
# -------------------------------------------------------
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

router_sys = APIRouter(prefix="/api/v1/sys", tags=["System"])

agents: dict[str, dict] = {}  # internal agent registry


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
        agents[full_path] = {"func": func, "method": method, "goal": goal, "tags": tags}
        route_path = full_path.replace("/api/v1/agents", "") or "/"
        if method.upper() == "GET":
            router_agents.get(route_path, tags=tags)(func)
        else:
            router_agents.post(route_path, tags=tags)(func)
        return func

    return decorator


# -------------------------------------------------------
# FAVICON & DOCS
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


# -------------------------------------------------------
# AUTH MIDDLEWARE
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
# SYSTEM ENDPOINTS
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


# -------------------------------------------------------
# DEVTOOLS
# -------------------------------------------------------
@router_dev.get("/agents")
async def list_agents():
    return [
        {"path": p, "method": a["method"], "goal": a["goal"], "tags": a["tags"]}
        for p, a in agents.items()
    ]


@router_dev.post("/chain")
async def chain(body: ChainBody):
    outputs = []

    for step in body.chain:
        path = step.path

        # 🔥 Normalize path so both formats work:
        # "/api/v1/agents/xyz" or "/xyz"
        if path not in agents:
            short = path.replace("/api/v1/agents", "")
            full = f"/api/v1/agents{short}"
            if full not in agents:
                # 🔥 Correct error — tell FastAPI to send a non-200 response
                raise HTTPException(
                    status_code=404, detail=f"Agent not found: {step.path}"
                )
            path = full

        func = agents[path]["func"]
        sig = inspect.signature(func)

        # accepted = {k: v for k, v in step.params.items() if k in sig.parameters}
        accepted = {}
        body_model_param = None
        for name, param in sig.parameters.items():
            ann = param.annotation

            # Detect Pydantic body parameter
            if hasattr(ann, "__fields__"):
                body_model_param = name
                continue

            # Direct primitive
            if name in step.params:
                accepted[name] = step.params[name]

        print("➡ Running agent:", path, "   accepted args:", accepted)
        # Build Pydantic body if needed
        if body_model_param:
            ann = sig.parameters[body_model_param].annotation
            accepted[body_model_param] = ann(**step.params)

        result = (
            await func(**accepted)
            if inspect.iscoroutinefunction(func)
            else func(**accepted)
        )

        # unwrap JSONResponse → dict
        if hasattr(result, "body"):
            try:
                result = json.loads(result.body.decode())
            except Exception:
                pass

        outputs.append(result)

    return {"results": outputs}


@app.post("/api/v1/dev/store", tags=["Devtools"])
async def store(key: str, content: str):
    collection.add(documents=[content], ids=[key], embeddings=[[0.1] * 384])
    return {"status": "stored"}


@app.get("/api/v1/dev/search", tags=["Devtools"])
async def search(query: str):
    r = collection.query(query_texts=[query], n_results=3)
    return {"results": {"documents": r.get("documents", [[]])[0]}}


# -------------------------------------------------------
# AGENT DISCOVERY
# -------------------------------------------------------
def load_module_from_path(name: str, path: str) -> ModuleType:
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
        pkg.__path__ = [str(path)]  # type: ignore[attr-defined]
    sys.modules[name] = pkg


def get_agent_id(agent_name: str) -> str | None:
    """
    Returns agent_id for a given agent_name (case-insensitive).
    If not found, returns None.
    """
    agent_name = agent_name.lower().strip()

    if not REGISTRY_AGENTS_INDEX.exists():
        return None

    try:
        agents = json.loads(REGISTRY_AGENTS_INDEX.read_text())
    except Exception:
        return None

    for agent in agents:
        if agent.get("agent_name", "").lower() == agent_name:
            return agent.get("agent_id")

    return None


def discover_agents():
    # 🧪 Skip folder agent discovery ONLY for pytest TestClient (in-memory app),
    # but still allow discovery when pytest launches CLI subprocess.
    if os.getenv("PYTEST_CURRENT_TEST"):
        # If run by CLI subprocess (treehopper run / call / build / lint / init),
        # we DO want to discover agents.
        cli_commands = {"run", "call", "build", "lint", "init"}
        if not any(cmd in sys.argv for cmd in cli_commands):
            print("🧪 Pytest in-memory mode: skipping folder agent auto-discovery")
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

# Register routers
app.include_router(router_agents)
app.include_router(router_dev)
app.include_router(router_sys)
