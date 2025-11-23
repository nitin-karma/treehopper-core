from fastapi import FastAPI
from fastapi.responses import JSONResponse
from treehopper.treehopper import VERSION, _execute_agent_step


def create_agent_app(agent_name: str, agent_path: str):
    app = FastAPI(title=f"Treehopper v{VERSION} Agent Runtime — {agent_name}")

    @app.get("/")
    async def root():
        return {"agent": agent_name, "status": "running"}

    @app.get(f"/api/v1/{agent_name}/health")
    async def health():
        return {"status": "ok", "agent": agent_name}

    @app.post(f"/api/v1/{agent_name}/run")
    async def run(payload: dict):
        out = await _execute_agent_step(agent_path, payload)
        return JSONResponse({"agent": agent_name, "result": out})

    return app
