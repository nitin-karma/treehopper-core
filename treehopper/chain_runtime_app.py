from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pathlib import Path
import yaml
from treehopper.treehopper import VERSION, _execute_agent_step


def create_chain_app(chain_name: str, chain_dir: Path):
    cfg = yaml.safe_load((chain_dir / "chain.yaml").read_text())
    agents = cfg["agents"]
    app = FastAPI(title=f"Treehopper v{VERSION} Chain Runtime — {chain_name}")

    @app.get("/")
    async def root():
        return {"chain": chain_name, "status": "running"}

    @app.get(f"/api/v1/{chain_name}/health")
    async def health():
        return {"status": "ok", "chain": chain_name}

    @app.post(f"/api/v1/{chain_name}/run")
    async def run(payload: dict):
        results = []
        prev = None
        for step in agents:
            params = payload if prev is None else prev
            out = await _execute_agent_step(step["path"], params)
            prev = out
            results.append(out)

        history = {"chain": chain_name, "results": results}
        (chain_dir / "last_run.json").write_text(
            yaml.safe_dump(history, sort_keys=False)
        )
        return JSONResponse(history)

    return app
