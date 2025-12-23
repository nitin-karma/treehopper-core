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

from fastapi.responses import FileResponse  # , RedirectResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import json
import asyncio
import yaml
from datetime import datetime
from collections import Counter, defaultdict
from typing import Counter as CounterType, Dict
import time
from treehopper.visualizer.state import snapshot
from treehopper.visualizer.log_tail import read_logs
from treehopper.visualizer.db_util import db
from treehopper.visualizer.user_routes import router as user_router
from treehopper.logging import metrics
from treehopper.th_config import (
    TH_ROOT,
    LOG_RENDER_LIMIT,
    DASHBOARD_HEADER,
    LOG_SCHEDULE,
)
from treehopper.logging import get_logger

logger = get_logger()

# from treehopper.visualizer.ws_proxy import proxy_chain_ws

# app = FastAPI(title="TreehopperAI Visualizer")

app = FastAPI(
    title="TreehopperAI Visualizer",
    docs_url=None,  # Disable /docs
    redoc_url=None,  # Disable /redoc
    openapi_url=None,  # Disable openapi.json
)

app.include_router(user_router)


# --- Initialize Database on startup ---
@app.on_event("startup")
async def startup_event():
    db.init_db()


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

    path_obj = Path(request.url.path)
    extension = path_obj.suffix  # This will be '.css' or '.js'

    # 1. ONLY apply security to /api routes
    if request.url.path.startswith("/api") or extension in [".css", ".js"]:
        referer = request.headers.get("referer")
        custom_header = request.headers.get("x-requested-with")

        # 2. Allow if it has the Referer OR the custom header
        # We check "localhost" or "127.0.0.1" for local dev
        is_valid_referer = referer and (
            "localhost" in referer or "127.0.0.1" in referer
        )
        is_valid_header = custom_header == DASHBOARD_HEADER

        if not (is_valid_referer or is_valid_header):
            return Response(
                content=json.dumps({"detail": "Direct API access forbidden"}),
                status_code=403,
                media_type="application/json",
            )

    # 3. For everything else (/, style.css, script.js), just let it pass through
    return await call_next(request)


# 1. Login Page (Root)
@app.get("/")
async def serve_login():
    return FileResponse(Path(__file__).parent / "static" / "login.html")


# 2. Main Dashboard Page
@app.get("/home")
async def serve_home():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


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

    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def add_node(node_id, label, ntype="agent"):
        nodes[node_id] = {
            "id": node_id,
            "label": label,
            "type": ntype,
        }

    def add_edge(src, dst, label=None):
        edges.append(
            {
                "from": src,
                "to": dst,
                "label": label,
            }
        )

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
        step_entry: dict[str, list[str]] = {}
        step_exit: dict[str, list[str]] = {}

        for step in data["steps"]:
            step_id = step["step_id"]
            agents = step.get("agents", [])
            mode = step.get("execution_mode", "sequential")
            agent_nodes: list[str] = []

            # ---- Create agent nodes
            for agent in agents:
                aid = f"{step_id}:{agent['agent_name']}"
                add_node(aid, agent["agent_name"])
                agent_nodes.append(aid)

            # ---- Internal edges
            if mode == "sequential":
                for i in range(len(agent_nodes) - 1):
                    add_edge(agent_nodes[i], agent_nodes[i + 1])

            # ---- Merge handling
            if "merge_agent" in step:
                mid = f"{step_id}:merge:{step['merge_agent']}"
                add_node(mid, step["merge_agent"], "merge")
                for a in agent_nodes:
                    add_edge(a, mid)
                step_entry[step_id] = agent_nodes
                step_exit[step_id] = [mid]
            else:
                step_entry[step_id] = agent_nodes
                step_exit[step_id] = agent_nodes if agent_nodes else []

        # ---- Step-to-step linear flow
        steps = data["steps"]
        for i in range(len(steps) - 1):
            src_step = steps[i]["step_id"]
            dst_step = steps[i + 1]["step_id"]
            for src in step_exit.get(src_step, []):
                for dst in step_entry.get(dst_step, []):
                    add_edge(src, dst)

        # ------------------------------------------------------------------
        # CONDITIONAL ROUTING
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
                for s in step_exit.get(src_step, []):
                    add_edge(s, cond_node, "if")
                for d in step_entry.get(goto, []):
                    add_edge(cond_node, d, condition)
    else:
        raise HTTPException(400, "Unsupported chain format")

    # ------------------------------------------------------------------
    # ENHANCED GRAPHVIZ DOT GENERATION
    # ------------------------------------------------------------------
    dot = [
        "digraph chain {",
        "  rankdir=LR;",
        "  splines=ortho;",  # Changed from curved to ortho for cleaner lines
        "  nodesep=1.2;",  # Increased spacing
        "  ranksep=2.0;",  # Increased spacing
        '  bgcolor="transparent";',
        "  pad=0.5;",
        "  ",
        "  // Global node defaults",
        "  node [",
        '    fontname="SF Pro Display, Inter, system-ui, sans-serif",',
        "    fontsize=16,",
        '    style="filled,rounded",',
        '    fillcolor="#1a1f2e",',
        '    color="#10b981",',
        '    fontcolor="#ffffff",',
        "    penwidth=3,",
        "    margin=0.3,",
        "    height=0.8,",
        "    width=2.5",
        "  ];",
        "  ",
        "  // Edge defaults",
        "  edge [",
        '    color="#6366f180",',  # Semi-transparent indigo
        "    penwidth=2.5,",
        "    arrowsize=1.0,",
        '    fontcolor="#94a3b8",',
        "    fontsize=11,",
        '    fontname="SF Pro Display, Inter, system-ui, sans-serif"',
        "  ];",
    ]

    shape_map = {"agent": "box", "merge": "diamond", "condition": "hexagon"}

    # Generate Node Definitions with enhanced styling
    for n in nodes.values():
        shape = shape_map.get(n["type"], "box")
        logger.info(shape)
        nid = dot_escape(n["id"])
        lbl = dot_escape(n["label"])

        if n["type"] == "condition":
            # Condition nodes - Yellow/Amber theme
            dot.append(
                f'  "{nid}" ['
                f'label="{lbl}", '
                f"shape=hexagon, "
                f'fillcolor="#451a03", '
                f'color="#fbbf24", '
                f'fontcolor="#fef3c7", '
                f"penwidth=3.5, "
                f'style="filled"'
                f"];"
            )
        elif n["type"] == "merge":
            # Merge nodes - Purple theme
            dot.append(
                f'  "{nid}" ['
                f'label="{lbl}", '
                f"shape=diamond, "
                f'fillcolor="#1e1b4b", '
                f'color="#a78bfa", '
                f'fontcolor="#e9d5ff", '
                f"penwidth=3.5, "
                f"width=2.0, "
                f"height=2.0, "
                f'style="filled"'
                f"];"
            )
        else:
            # Agent nodes - Emerald theme with gradient effect
            dot.append(
                f'  "{nid}" ['
                f'label="{lbl}", '
                f"shape=box, "
                f'fillcolor="#064e3b", '
                f'color="#34d399", '
                f'fontcolor="#d1fae5", '
                f"penwidth=3, "
                f'style="filled,rounded"'
                f"];"
            )

    # Generate Edge Definitions with conditional styling
    for e in edges:
        src = dot_escape(e["from"])
        dst = dot_escape(e["to"])

        # Check if this edge connects to a condition node
        is_conditional = any(
            n["id"] == e["to"] and n["type"] == "condition" for n in nodes.values()
        )

        if e["label"]:
            lbl = dot_escape(e["label"])
            edge_color = "#fbbf24" if is_conditional else "#6366f1"
            dot.append(
                f'  "{src}" -> "{dst}" ['
                f'label=" {lbl} ", '
                f'color="{edge_color}", '
                f'fontcolor="{edge_color}", '
                f"penwidth=2.5"
                f"];"
            )
        else:
            dot.append(f'  "{src}" -> "{dst}";')

    dot.append("}")

    return {
        "chain": chain,
        "nodes": list(nodes.values()),
        "edges": edges,
        "dot": "\n".join(dot),
    }


def dot_escape(s: str) -> str:
    if s is None:
        return ""
    return s.replace("\\", "\\\\").replace('"', '\\"')


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


def normalize_ts(ts):
    """
    Convert timestamp to epoch seconds (float).
    Supports:
    - int / float epoch
    - ISO-8601 strings
    - None / invalid values
    """
    if ts is None:
        return None

    # Already numeric
    if isinstance(ts, (int, float)):
        # Handle ms timestamps
        if ts > 10_000_000_000:
            ts = ts / 1000
        return float(ts)

    # ISO / string timestamps
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
        except Exception:
            return None

    return None


@app.get("/api/v1/summary")
def get_summary(window: str = Query("24h", enum=LOG_SCHEDULE)):

    now = time.time()
    window_sec = {"1h": 3600, "24h": 86400, "7d": 604800}[window]
    cutoff = now - window_sec

    # -------------------------------------------------
    # 1. Parse runtime events
    # -------------------------------------------------
    event_counts: CounterType[str] = Counter()
    chain_counts: CounterType[str] = Counter()
    agent_counts: CounterType[str] = Counter()
    runs_success: int = 0
    runs_failed: int = 0
    timeline: Dict[str, int] = defaultdict(int)

    if WS_EVENTS_DIR.exists():
        for f in WS_EVENTS_DIR.glob("*.jsonl"):
            with open(f, "r") as fh:
                for line in fh:
                    try:
                        ev = json.loads(line)
                    except Exception:
                        continue

                    raw_ts = ev.get("ts") or ev.get("timestamp")
                    ts = normalize_ts(raw_ts)
                    if ts is None:
                        print("[summary] Skipping event with invalid ts:", raw_ts)

                    if ts is None or ts < cutoff:
                        continue

                    etype = ev.get("type")
                    event_counts[etype] += 1

                    if "chain" in ev:
                        chain_counts[ev["chain"]] += 1

                    if "agent" in ev:
                        agent_counts[ev["agent"]] += 1

                    if etype == "run_completed":
                        runs_success += 1
                    if etype == "error":
                        runs_failed += 1

                    if ts:
                        hour = time.strftime("%H:00", time.localtime(ts))
                        timeline[hour] += 1

    # -------------------------------------------------
    # 2. Shared files stats (reuse existing endpoint logic)
    # -------------------------------------------------
    shared_dir = REGISTRY_DIR / "shared"
    file_ext: CounterType[str] = Counter()
    total_size = 0
    file_count = 0

    if shared_dir.exists():
        for p in shared_dir.rglob("*"):
            if p.is_file():
                file_count += 1
                total_size += p.stat().st_size
                ext = p.suffix.lstrip(".") or "unknown"
                file_ext[ext] += 1

    # -------------------------------------------------
    # 3. Response
    # -------------------------------------------------
    res = {
        "time_window": window,
        "runs": {
            "total": runs_success + runs_failed,
            "success": runs_success,
            "failed": runs_failed,
        },
        "chains": {"by_chain": dict(chain_counts)},
        "agents": {"invocations": dict(agent_counts)},
        "files": {
            "count": file_count,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "by_extension": dict(file_ext),
        },
        "events": {"by_type": dict(event_counts)},
        "timeline": {
            "runs_per_hour": [
                {"hour": h, "count": c} for h, c in sorted(timeline.items())
            ]
        },
    }
    logger.info(res)
    return res


# -------------------------------------------------------------------
# Static UI (single-page visualizer)
# -------------------------------------------------------------------

app.mount(
    "/",
    StaticFiles(directory=Path(__file__).parent / "static", html=True),
    name="ui",
)
