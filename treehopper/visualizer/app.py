# treehopper/visualizer/app.py
# import os
from fastapi import (
    FastAPI,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    Request,
    Response,
    # Header,
    Query,
)

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import json
import asyncio
import yaml

from treehopper.visualizer.state import snapshot
from treehopper.visualizer.log_tail import read_logs
from treehopper.logging import metrics
from treehopper.th_config import TH_ROOT, LOG_RENDER_LIMIT

# from treehopper.visualizer.ws_proxy import proxy_chain_ws

# app = FastAPI(title="TreehopperAI Visualizer")

app = FastAPI(
    title="TreehopperAI Visualizer",
    docs_url=None,  # Disable /docs
    redoc_url=None,  # Disable /redoc
    openapi_url=None,  # Disable openapi.json
)


# -------------------------------------------------------------------
# Security Middleware (Blocks direct browser access to /api)
# -------------------------------------------------------------------
@app.middleware("http")
async def restrict_to_ui(request: Request, call_next):

    # If it's a WebSocket upgrade request, just check the Referer/Origin
    if request.headers.get("upgrade") == "websocket":
        print("[middleware] Web socket request")
        referer = request.headers.get("referer")
        if not referer or "localhost" not in referer:
            print(f"[middleware] referer - {referer}")
            return Response(status_code=403)
        return await call_next(request)

    path = request.url.path

    # 1. ONLY apply security to /api routes
    if (
        path.startswith("/api")
        or path.startswith("/script.css")
        or path.startswith("/script.js")
    ):
        referer = request.headers.get("referer")
        custom_header = request.headers.get("x-requested-with")

        # 2. Allow if it has the Referer OR the custom header
        # We check "localhost" or "127.0.0.1" for local dev
        is_valid_referer = referer and (
            "localhost" in referer or "127.0.0.1" in referer
        )
        is_valid_header = custom_header == "TreehopperDash"

        if not (is_valid_referer or is_valid_header):
            return Response(
                content=json.dumps({"detail": "Direct API access forbidden"}),
                status_code=403,
                media_type="application/json",
            )

    # 3. For everything else (/, style.css, script.js), just let it pass through
    return await call_next(request)


# -------------------------------------------------------------------
# API Routes (Example of clean route)
# -------------------------------------------------------------------
@app.get("/api/state")
def get_state():
    return snapshot()


# -------------------------------------------------------------------
# Paths
# -------------------------------------------------------------------

TH_ROOT = Path(TH_ROOT)
LOG_DIR = TH_ROOT / "logs"
REGISTRY_DIR = TH_ROOT / "registry"
WS_EVENTS_DIR = REGISTRY_DIR / "chains" / "events"

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


# @app.get("/api/state")
# def get_state():
#     return snapshot()


# -------------------------------------------------------------------
# Metrics
# -------------------------------------------------------------------


@app.get("/api/metrics")
def get_metrics():
    return metrics().snapshot()


# -------------------------------------------------------------------
# Logs (JSON lines)
# -------------------------------------------------------------------


# @app.get("/api/logs")
# def get_logs():
#     if not LOG_DIR.exists():
#         return []
#     return read_logs(LOG_DIR)


@app.get("/api/logs")
def get_logs():
    if not LOG_DIR.exists():
        return []
    # Fetch LOG_RENDER_LIMIT = 750 logs to support 5 pages of 150
    return read_logs(LOG_DIR, limit=LOG_RENDER_LIMIT)


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
# Chain Flow Viewer
# -------------------------------------------------------------------


@app.get("/api/v1/chains/{chain}/flow")
def get_chain_flow(chain: str):
    chain_dir = REGISTRY_DIR / "chains"
    matches = list(chain_dir.glob(f"{chain}-*/chain.yaml"))

    if not matches:
        raise HTTPException(404, f"Chain YAML not found: {chain}")

    data = yaml.safe_load(matches[0].read_text())

    nodes = {}
    edges = []

    def add_node(node_id, label, ntype="agent"):
        nodes[node_id] = {"id": node_id, "label": label, "type": ntype}

    def add_edge(src, dst, label=None):
        edges.append({"from": src, "to": dst, "label": label})

    # ------------------------------------------------------------------
    # CASE 1: SIMPLE CHAIN (agents[])
    # ------------------------------------------------------------------
    if "agents" in data:
        prev = None
        for agent in data["agents"]:
            aid = agent["agent_name"]
            add_node(aid, aid)

            if prev:
                add_edge(prev, aid)
            prev = aid

    # ------------------------------------------------------------------
    # CASE 2 & 3: MULTI-STEP CHAINS (steps[])
    # ------------------------------------------------------------------
    elif "steps" in data:
        step_outputs = {}

        for step in data["steps"]:
            step_id = step["step_id"]
            agents = step.get("agents", [])
            mode = step.get("execution_mode", "sequential")

            agent_nodes = []

            for agent in agents:
                aid = f"{step_id}:{agent['agent_name']}"
                add_node(aid, agent["agent_name"])
                agent_nodes.append(aid)

            # Sequential inside step
            if mode == "sequential":
                for i in range(len(agent_nodes) - 1):
                    add_edge(agent_nodes[i], agent_nodes[i + 1])

            # Parallel: fan-out
            step_outputs[step_id] = agent_nodes

            # Merge agent
            if "merge_agent" in step:
                mid = f"{step_id}:merge:{step['merge_agent']}"
                add_node(mid, step["merge_agent"], "merge")

                for a in agent_nodes:
                    add_edge(a, mid)

                step_outputs[step_id] = [mid]

        # Step-to-step edges (default linear order)
        steps = data["steps"]
        for i in range(len(steps) - 1):
            src = steps[i]["step_id"]
            dst = steps[i + 1]["step_id"]

            for s in step_outputs.get(src, []):
                for d in step_outputs.get(dst, []):
                    add_edge(s, d)

        # ------------------------------------------------------------------
        # CONDITIONAL ROUTING (route_on)
        # ------------------------------------------------------------------
        for step in steps:
            if "route_on" not in step:
                continue

            src_step = step["step_id"]
            for rule in step["route_on"]:
                condition = rule["if"]
                goto = rule["goto"]

                cond_node = f"{src_step}:cond:{condition}"
                add_node(cond_node, condition, "condition")

                for s in step_outputs.get(src_step, []):
                    add_edge(s, cond_node, "if")

                for d in step_outputs.get(goto, []):
                    add_edge(cond_node, d, condition)

    else:
        raise HTTPException(400, "Unsupported chain format")

    # ------------------------------------------------------------------
    # GRAPHVIZ DOT OUTPUT
    # ------------------------------------------------------------------
    dot = ["digraph chain {", "rankdir=LR;", "node [shape=box];"]

    for n in nodes.values():
        shape = {
            "agent": "box",
            "merge": "diamond",
            "condition": "hexagon",
        }.get(n["type"], "box")

        dot.append(f'"{n["id"]}" [label="{n["label"]}", shape={shape}];')

    for e in edges:
        if e["label"]:
            dot.append(f'"{e["from"]}" -> "{e["to"]}" [label="{e["label"]}"];')
        else:
            dot.append(f'"{e["from"]}" -> "{e["to"]}";')

    dot.append("}")

    return {
        "chain": chain,
        "nodes": list(nodes.values()),
        "edges": edges,
        "dot": "\n".join(dot),
    }


# -------------------------------------------------------------------
# Chain Flow Viewer
# -------------------------------------------------------------------


@app.get("/api/v1/chains/{chain}/lastrun")
def get_chain_lastrun(chain: str):
    chain_dir = REGISTRY_DIR / "chains"
    matches = list(chain_dir.glob(f"{chain}-*/last_run.json"))

    if not matches:
        raise HTTPException(404, f"lastrun json not found: {chain}")
    print(
        {
            "chain": chain,
            "content": json.loads(matches[0].read_text()),
        }
    )

    return {
        "chain": chain,
        "last_run": json.loads(matches[0].read_text()),
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
# Shared directory viewer for each agent inputs
# -------------------------------------------------------------------


@app.get("/api/v1/fs/shared")
def list_shared_files():
    shared_dir = REGISTRY_DIR / "shared"

    if not shared_dir.exists():
        # print(f"[list_shared_files] {shared_dir} not exists")
        return {"base": "registry/shared", "files": []}

    results = []

    for path in shared_dir.rglob("*"):
        if path.is_file():
            results.append(
                {
                    "path": str(path.relative_to(shared_dir)),
                    "size": path.stat().st_size,
                    "modified": int(path.stat().st_mtime),
                }
            )
    # print(f"[list_shared_files] {shared_dir}")
    # print(f"[list_shared_files] {results}")
    return {
        "base": "registry/shared",
        "files": results,
    }


@app.get("/api/v1/fs/shared/download")
def download_shared_file(path: str = Query(...)):
    shared_dir = (REGISTRY_DIR / "shared").resolve()

    # Construct the full path and resolve it to prevent ../ traversal
    file_path = (shared_dir / path).resolve()

    # Security check: Ensure the requested file is actually inside the shared directory
    if not str(file_path).startswith(str(shared_dir)):
        raise HTTPException(
            status_code=403, detail="Access denied: Path outside shared directory"
        )

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    # This sends the file to the browser and forces a 'Save As' dialog
    return FileResponse(
        path=file_path,
        filename=file_path.name,  # The name the user sees
        media_type="application/octet-stream",
    )


def walk_dir(base: Path, depth: int = 3):
    def _walk(p: Path, d: int):
        if d <= 0:
            return []

        items = []
        for child in sorted(p.iterdir()):
            try:
                if child.is_dir():
                    items.append(
                        {
                            "name": child.name,
                            "type": "dir",
                            "children": _walk(child, d - 1),
                        }
                    )
                else:
                    items.append(
                        {
                            "name": child.name,
                            "type": "file",
                            "size": child.stat().st_size,
                        }
                    )
            except Exception:
                continue
        return items

    return _walk(base, depth)


@app.get("/api/v1/fs/tree")
def fs_tree():
    return {
        "root": str(TH_ROOT),
        "tree": walk_dir(TH_ROOT, depth=4),
    }


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


@app.websocket("/api/v1/ws/replay/{run_id}")
async def ws_replay(ws: WebSocket, run_id: str):
    await ws.accept()

    event_files = sorted(WS_EVENTS_DIR.glob(f"*{run_id}*.jsonl"))

    if not event_files:
        await ws.send_json(
            {
                "type": "replay_error",
                "message": "No events found for run_id",
                "run_id": run_id,
            }
        )
        await ws.close()
        return

    try:
        for file in event_files:
            with open(file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        await ws.send_json(json.loads(line))
                        await asyncio.sleep(0.1)  # playback pacing
                    except Exception:
                        continue

        await ws.send_json(
            {
                "type": "replay_complete",
                "run_id": run_id,
            }
        )

    except WebSocketDisconnect:
        pass


# -------------------------------------------------------------------
# Static UI (single-page visualizer)
# -------------------------------------------------------------------

app.mount(
    "/",
    StaticFiles(directory=Path(__file__).parent / "static", html=True),
    name="ui",
)
