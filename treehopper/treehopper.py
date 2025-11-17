import os
import importlib.util
import inspect
from fastapi import FastAPI, Request, APIRouter
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html
from dotenv import load_dotenv
from chromadb import Client
from chromadb.config import Settings
from chromadb.utils import embedding_functions

load_dotenv()

# ----------------------- FASTAPI ROOT ----------------------------------
app = FastAPI(
    title="Treehopper Agentic API",
    docs_url=None,
    redoc_url=None,
    version="0.1.0",
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ----------------------- MEMORY ----------------------------------------
memory = Client(Settings(is_persistent=True, persist_directory=".treehopper_memory"))
collection = memory.get_or_create_collection(
    "treehopper", embedding_function=embedding_functions.DefaultEmbeddingFunction()
)

# ----------------------- ROUTERS ---------------------------------------
router_agents = APIRouter(prefix="/api/v1/agents", tags=["Example Agents"])
router_dev = APIRouter(prefix="/api/v1/dev", tags=["Developer Tools"])
router_sys = APIRouter(prefix="/api/v1/sys", tags=["System"])

agents = {}  # internal registry


# ----------------------- AGENT DECORATOR --------------------------------
def agent(path, method="GET", goal="", tags=None):
    if tags is None:
        tags = []

    # unify paths → agents must be relative only
    if path.startswith("/api/v1/agents/"):
        full_path = path
    else:
        full_path = f"/api/v1/agents/{path.lstrip('/')}"

    def decorator(func):
        agents[full_path] = {"func": func, "method": method, "goal": goal, "tags": tags}
        if method == "GET":
            app.get(full_path, tags=tags)(func)
        else:
            app.post(full_path, tags=tags)(func)
        return func

    return decorator


# ----------------------- FAVICON & DOCS --------------------------------
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


# ----------------------- AUTH MIDDLEWARE --------------------------------
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    public_exact = {"/", "/favicon", "/favicon.ico", "/docs", "/openapi.json"}
    public_prefix = ("/static",)

    if request.url.path in public_exact or request.url.path.startswith(public_prefix):
        return await call_next(request)

    if request.headers.get("x-api-key") != "demo-key-123":
        return JSONResponse(status_code=403, content={"error": "Invalid API key"})

    return await call_next(request)


# ----------------------- SYSTEM ENDPOINTS -------------------------------
@router_sys.get("/health")
async def health():
    return {"status": "ok"}


@router_sys.get("/version")
async def version():
    return {"treehopper": "0.1.0"}


# ----------------------- DEVTOOLS ENDPOINTS -----------------------------
@router_dev.get("/agents")
async def list_agents():
    return [
        {"path": p, "method": a["method"], "goal": a["goal"], "tags": a["tags"]}
        for p, a in agents.items()
    ]


@router_dev.post("/chain")
async def chain(request: Request):
    """Execute multiple agents sequentially. Supports sync and async agents."""
    body = await request.json()
    steps = body.get("chain", [])
    outputs = []
    for step in steps:
        path = step["path"]
        params = step.get("params", {})
        # 🔥 graceful missing-agent validation
        if path not in agents:
            return JSONResponse(
                status_code=400, content={"error": f"Agent not found: {path}"}
            )
        func = agents[path]["func"]
        sig = inspect.signature(func)
        accepted = {k: v for k, v in params.items() if k in sig.parameters}
        # execute async/sync
        if inspect.iscoroutinefunction(func):
            result = await func(**accepted)
        else:
            result = func(**accepted)
        outputs.append(result)
    return {"results": outputs}


@app.post("/api/v1/dev/store", tags=["Devtools"])
async def store(key: str, content: str):
    """Store knowledge into vector memory."""
    collection.add(
        documents=[content],
        ids=[key],
        embeddings=[[0.1] * 384],  # avoids downloading models
    )
    return {"status": "stored"}


@app.get("/api/v1/dev/search", tags=["Devtools"])
async def search(query: str):
    """Search vector memory."""
    q = collection.query(query_texts=[query], n_results=3)
    docs = q.get("documents", [[]])[0]
    return {"results": {"documents": docs}}


# ----------------------- AGENT AUTO-DISCOVERY ---------------------------
def discover_agents():
    AGENTS_DIR = os.path.join(os.path.dirname(__file__), "agents")
    if not os.path.isdir(AGENTS_DIR):
        return
    for filename in os.listdir(AGENTS_DIR):
        if filename.endswith(".py") and not filename.startswith("_"):
            path = os.path.join(AGENTS_DIR, filename)
            spec = importlib.util.spec_from_file_location(filename, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)


discover_agents()

# REGISTER ROUTERS LAST
app.include_router(router_agents)
app.include_router(router_dev)
app.include_router(router_sys)
