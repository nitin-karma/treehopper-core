import os
import importlib.util
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from chromadb import Client
from chromadb.config import Settings
from chromadb.utils import embedding_functions

load_dotenv()

app = FastAPI()
agents = {}

# memory = Client(
#     Settings(
#         persist_directory=".treehopper_memory",
#         is_persistent=True
#     )
# )
# collection = memory.get_or_create_collection("treehopper")

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
            app.get(path)(func)
        else:
            app.post(path)(func)
        return func

    return decorator


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if request.url.path.startswith("/favicon"):
        return await call_next(request)
    if request.headers.get("x-api-key") != "demo-key-123":
        return JSONResponse(status_code=403, content={"error": "Invalid API key"})
    return await call_next(request)


@app.get("/agents")
async def list_agents():
    return [
        {"path": p, "method": a["method"], "goal": a["goal"], "tags": a["tags"]}
        for p, a in agents.items()
    ]


@app.post("/chain")
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


@app.post("/store")
async def store(key: str, content: str):
    """Store knowledge into vector memory."""
    collection.add(documents=[content], ids=[key])
    return {"status": "stored"}


@app.get("/search")
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
