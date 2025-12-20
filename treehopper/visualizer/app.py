# treehopper/visualizer/app.py

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import json
import asyncio

from treehopper.visualizer.state import snapshot
from treehopper.visualizer.log_tail import read_logs
from treehopper.logging import metrics
from treehopper.th_config import TH_ROOT
from treehopper.visualizer.ws_proxy import proxy_chain_ws

app = FastAPI(title="TreehopperAI Visualizer")

# -------------------------------------------------------------------
# Paths
# -------------------------------------------------------------------

TH_ROOT = Path(TH_ROOT)
LOG_DIR = TH_ROOT / "logs"
REGISTRY_DIR = TH_ROOT / "registry"
WS_EVENTS_DIR = REGISTRY_DIR / "events"

# -------------------------------------------------------------------
# Health
# -------------------------------------------------------------------


@app.get("/health")
def health():
    return {"status": "ok"}


# -------------------------------------------------------------------
# Install / Subscription ID
# -------------------------------------------------------------------


@app.get("/api/v1/sys/subscription")
def get_subscription():
    path = TH_ROOT / "subscription_id.txt"
    if not path.exists():
        raise HTTPException(404, "subscription_id not found")

    return {
        "subscription_id": path.read_text().strip(),
        "created_at": int(path.stat().st_ctime),
    }


# -------------------------------------------------------------------
# Global State Snapshot (agents / chains / runtimes)
# -------------------------------------------------------------------


@app.get("/api/state")
def get_state():
    return snapshot()


# -------------------------------------------------------------------
# Metrics
# -------------------------------------------------------------------


@app.get("/api/metrics")
def get_metrics():
    return metrics().snapshot()


# -------------------------------------------------------------------
# Logs (JSON lines)
# -------------------------------------------------------------------


@app.get("/api/logs")
def get_logs():
    if not LOG_DIR.exists():
        return []
    return read_logs(LOG_DIR)


# -------------------------------------------------------------------
# Chain YAML Viewer
# -------------------------------------------------------------------


@app.get("/api/v1/chains/{chain}/yaml")
def get_chain_yaml(chain: str):
    chain_dir = REGISTRY_DIR / "chains"
    matches = list(chain_dir.glob(f"{chain}-*/chain.yaml"))

    if not matches:
        raise HTTPException(404, f"Chain YAML not found: {chain}")

    return {
        "chain": chain,
        "yaml": matches[0].read_text(),
    }


# -------------------------------------------------------------------
# Agent YAML Viewer
# -------------------------------------------------------------------


@app.get("/api/v1/agents/{agent}/yaml")
def get_agent_yaml(agent: str):
    agent_dir = REGISTRY_DIR / "agents"
    matches = list(agent_dir.glob(f"{agent}-*/agent.yaml"))

    if not matches:
        raise HTTPException(404, f"Agent YAML not found: {agent}")

    return {
        "agent": agent,
        "yaml": matches[0].read_text(),
    }


# -------------------------------------------------------------------
# Last Run JSON Viewer (per chain)
# -------------------------------------------------------------------


@app.get("/api/v1/chains/{chain}/runs/last")
def get_last_run(chain: str):
    chain_dir = REGISTRY_DIR / "chains"
    matches = list(chain_dir.glob(f"{chain}-*/last_run.json"))

    if not matches:
        raise HTTPException(404, f"No runs found for chain: {chain}")

    return json.loads(matches[0].read_text())


# -------------------------------------------------------------------
# Live WebSocket Event Stream (logs + runtime events)
# -------------------------------------------------------------------


@app.websocket("/api/v1/ws/events")
async def ws_events(ws: WebSocket):
    await ws.accept()

    try:
        # Very lightweight polling-based tail
        last_sizes: dict = {}

        while True:
            events = []

            if WS_EVENTS_DIR.exists():
                for log_file in WS_EVENTS_DIR.glob("*.events.jsonl"):
                    size = log_file.stat().st_size
                    last = last_sizes.get(log_file, 0)

                    if size > last:
                        with open(log_file, "r", encoding="utf-8") as f:
                            f.seek(last)
                            for line in f:
                                try:
                                    events.append(json.loads(line))
                                except Exception:
                                    pass

                        last_sizes[log_file] = size

            for event in events:
                await ws.send_json(event)

            await asyncio.sleep(0.5)

    except WebSocketDisconnect as e:
        print(f"[ws_events] - {str(e)}")
        pass


@app.websocket("/api/v1/ws/proxy/{chain_port}/{run_id}")
async def ws_chain_proxy(ws: WebSocket, chain_port: int, run_id: str):
    await ws.accept()

    async def sink(event):
        await ws.send_json(event)

    try:
        await proxy_chain_ws(chain_port, run_id, sink)
    except WebSocketDisconnect as e:
        print(f"[ws_chain_proxy] - {str(e)}")
        pass


# -------------------------------------------------------------------
# Static UI (single-page visualizer)
# -------------------------------------------------------------------

app.mount(
    "/",
    StaticFiles(directory=Path(__file__).parent / "static", html=True),
    name="ui",
)
