import os
from typing import Any, Dict

from fastapi import FastAPI, Body, HTTPException
from fastapi import Security
from fastapi.security import APIKeyHeader
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from treehopper.agent_runtime import run_agent_path
from treehopper.th_config import VERSION, DEFAULT_API_KEY

# from treehopper.utils.ui_assets import inject_branding
from fastapi.openapi.docs import get_swagger_ui_html

API_KEY = os.getenv("TREEHOPPER_API_KEY", DEFAULT_API_KEY)
API_KEY_HEADER = APIKeyHeader(name="x-api-key", auto_error=False)


async def verify_api_key(key: str = Security(API_KEY_HEADER)):
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return key


AGENT_NAME = os.getenv("AGENT_NAME")

if not AGENT_NAME:
    raise RuntimeError(
        "AGENT_NAME environment variable is required for agent runtime. "
        "Example: AGENT_NAME=formatter uvicorn treehopper.agent_runtime_app:app ..."
    )

app = FastAPI(title=f"Treehopper v{VERSION} Agent Runtime ({AGENT_NAME})")


# __file__ is treehopper/agent_runtime_app.py
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
STATIC_DIR = os.path.abspath(STATIC_DIR)

if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# inject_branding(app, f"Agent Runtime: {AGENT_NAME}")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(os.path.join(STATIC_DIR, "treehopper_favicon.png"))


@app.get("/docs", include_in_schema=False)
async def custom_docs():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title,
        swagger_favicon_url="/static/treehopper_favicon.png",
    )


@app.get("/")
async def root():
    return {"status": "ok", "runtime": "agent", "agent": AGENT_NAME}


@app.get(f"/api/v1/{AGENT_NAME}/health")
async def health():
    # Optional: check that the underlying agent is registered
    # We just trust discover_agents() in treehopper.treehopper for now.
    return {"status": "ok", "agent": AGENT_NAME}


@app.post(f"/api/v1/{AGENT_NAME}/run")
async def run_agent(
    payload: Dict[str, Any] = Body(...), api_key: str = Security(verify_api_key)
):
    """
    Run the underlying Treehopper agent function directly
    using the shared in-process registry in treehopper.treehopper.

    This always uses POST with a JSON body.
    """
    agent_path = f"/api/v1/agents/{AGENT_NAME}"

    try:
        result = await run_agent_path(agent_path, payload or {})
    except HTTPException as e:
        # propagate FastAPI HTTP errors as-is
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # run_agent_path already normalizes to a dict
    if isinstance(result, dict):
        return JSONResponse(result)
    return JSONResponse({"value": result})
