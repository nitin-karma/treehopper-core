import os
import importlib.util
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from chromadb import Client
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

load_dotenv()

app = FastAPI(
    title="Treehopper Agentic API",
    docs_url=None,
    redoc_url=None,
    description="Run modular AI agents, chaining, and memory with a unified agent framework.\n\n"
    "🚀 **Key Features**\n"
    "- Auto-discovered agents\n"
    "- Chaining multiple agent calls\n"
    "- Vector memory storage and search\n"
    "- Multi-provider LLM backend integration",
    version="0.1.0",
    contact={
        "name": "Treehopper",
        "url": "https://github.com/nitin-karma/treehopper-core",
    },
)
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

agents = {}
# 🔥 Disable real embedding model — use dummy vectors instead
memory = Client(Settings(is_persistent=True, persist_directory=".treehopper_memory"))
collection = memory.get_or_create_collection(
    "treehopper", embedding_function=embedding_functions.DefaultEmbeddingFunction()
)


def agent(path, method="GET", goal="", tags=None):
    if tags is None:
        tags = []

    def decorator(func):
        agents[path] = {"func": func, "method": method, "goal": goal, "tags": tags}
        if method == "GET":
            app.get(path, tags=tags)(func)  # FIXED
        else:
            app.post(path, tags=tags)(func)  # FIXED
        return func

    return decorator


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(os.path.join(STATIC_DIR, "treehopper_favicon.png"))


@app.get("/docs", include_in_schema=False)
async def custom_docs():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="Treehopper API — Swagger UI",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
        swagger_favicon_url="/static/treehopper_favicon.png",  # 👈 not filesystem path
    )


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    public_paths = public_paths = [
        "/",
        "/favicon",
        "/favicon.ico",
        "/docs",
        "/openapi.json",
        "/static",
    ]
    if any(request.url.path.startswith(p) for p in public_paths):
        return await call_next(request)
    if request.headers.get("x-api-key") != "demo-key-123":
        return JSONResponse(status_code=403, content={"error": "Invalid API key"})
    return await call_next(request)


@app.get("/", tags=["Health"])
async def health():
    return {"status": "ok"}


@app.get("/agents", tags=["Devtools"])
async def list_agents():
    return [
        {"path": p, "method": a["method"], "goal": a["goal"], "tags": a["tags"]}
        for p, a in agents.items()
    ]


@app.post("/chain", tags=["Devtools"])
async def chain(request: Request):
    """Execute multiple agents sequentially."""
    body = await request.json()
    results = []
    for step in body.get("chain", []):
        path = step["path"]
        params = step.get("params", {})
        func = agents[path]["func"]
        # Call sync or async functions safely
        result = (
            func(**params) if not hasattr(func, "__await__") else await func(**params)
        )
        results.append(result)
    return {"results": results}


@app.post("/store", tags=["Devtools"])
async def store(key: str, content: str):
    """Store knowledge into vector memory."""
    collection.add(documents=[content], ids=[key])
    return {"status": "stored"}


@app.get("/search", tags=["Devtools"])
async def search(query: str):
    results = collection.query(query_texts=[query], n_results=3)
    return {"results": {"documents": results["documents"][0]}}


def discover_agents():
    """Auto-load agents from treehopper/agents directory."""
    AGENTS_DIR = os.path.join(os.path.dirname(__file__), "agents")
    if not os.path.isdir(AGENTS_DIR):
        return
    for filename in os.listdir(AGENTS_DIR):
        if filename.endswith(".py") and not filename.startswith("_"):
            path = os.path.join(AGENTS_DIR, filename)
            spec = importlib.util.spec_from_file_location(filename, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)


# Always auto-discover agents after package installation
discover_agents()
