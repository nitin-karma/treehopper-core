# treehopper/visualizer/app.py
import os
import time
import httpx
from fastapi import (
    FastAPI,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    Request,
    Response,
    # Header,
    Query,
    Body,
)
from treehopper.sync_to_sqlite import get_subscription
from fastapi.responses import FileResponse  # , RedirectResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import json
import asyncio
import yaml
from datetime import datetime

# from collections import Counter, defaultdict
from typing import Any
from treehopper.visualizer.state import snapshot
from treehopper.visualizer.log_tail import read_logs
from treehopper.visualizer.db_init import DBInitializer
from treehopper.visualizer.db_util import db
from treehopper.visualizer.user_routes import router as user_router
from treehopper.visualizer.summary_utils import _build_summary, _file_stats
from treehopper.logging import metrics
from treehopper.maintainance.maintainer import get_storage_metrics
from treehopper.th_config import (
    TH_ROOT,
    LOG_RENDER_LIMIT,
    DASHBOARD_HEADER,
    DEFAULT_API_KEY,
    # LOG_SCHEDULE,
)

from treehopper.sync_to_sqlite import (
    get_all_agents,
    get_all_chains,
    get_recent_runs,
    get_yaml,
)
from treehopper.logging import get_logger

# At top of app.py

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
    dbInit = DBInitializer()
    dbInit.init_db()


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


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(Path(__file__).parent / "static" / "favicon.ico")


# 2. Main Dashboard Page
@app.get("/home")
async def serve_home():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


# -------------------------------------------------------------------
# API Routes (Example of clean route)
# -------------------------------------------------------------------

# ---------- Some additional endpoints unused ------------------------------


@app.get("/api/agents")
def get_agents():
    """Get all agents from SQLite (10x faster than reading JSON)"""
    return get_all_agents()


@app.get("/api/chains")
def get_chains():
    """Get all chains from SQLite (10x faster than reading JSON)"""
    return get_all_chains()


# ---------- Some additional endpoints unused ------------------------------


@app.get("/api/runs/recent")
def get_recent_runs_endpoint(limit: int = Query(50)):
    """
    Get recent chain runs from SQLite (NEW FEATURE)

    Args:
        limit: Maximum number of runs to return (default: 50)

    Returns:
        List of recent runs with payload, results, status
    """
    return get_recent_runs(limit)


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
def get_subscription_info():
    """
    Get subscription information from SQLite (Phase 1)

    Falls back to file if SQLite is empty (first run)
    """

    # Try SQLite first
    sub = get_subscription()

    if sub:

        # Convert ISO timestamp to epoch for backward compatibility
        try:
            created_dt = datetime.fromisoformat(
                sub["created_at"].replace("Z", "+00:00")
            )
            created_epoch = int(created_dt.timestamp())
        except Exception as e:
            logger.error(f"[get_subscription_info] datetime creation error: {e}")
            created_epoch = int(time.time())

        return {
            "subscription_id": sub["subscription_id"],
            "created_at": created_epoch,
            "status": sub.get("status", "active"),
            "plan": sub.get("plan", "trial"),
        }

    # Fallback to file (first run before sync)
    path = TH_ROOT / "subscription_id.txt"
    if not path.exists():
        raise HTTPException(404, "subscription_id not found")

    return {
        "subscription_id": path.read_text().strip(),
        "created_at": int(path.stat().st_ctime),
        "status": "active",
        "plan": "trial",
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


# @app.get("/api/v1/chains/{chain}/yaml")
# def get_chain_yaml(chain: str):
#     chain_dir = REGISTRY_DIR / "chains"
#     matches = list(chain_dir.glob(f"{chain}-*/chain.yaml"))

#     if not matches:
#         raise HTTPException(404, f"Chain YAML not found: {chain}")

#     return {
#         "chain": chain,
#         "yaml": matches[0].read_text(),
#     }


@app.get("/api/v1/chains/{chain}/yaml")
def get_chain_yaml(chain: str):
    """
    Get chain YAML from SQLite cache (Phase 2)
    Falls back to file if not cached
    """
    # Try SQLite cache first (10x faster)
    yaml_content = get_yaml("chain", chain)

    if yaml_content:
        return {"chain": chain, "yaml": yaml_content}

    # Fallback to file (not yet cached)
    chain_dir = REGISTRY_DIR / "chains"
    matches = list(chain_dir.glob(f"{chain}-*/chain.yaml"))

    if not matches:
        raise HTTPException(404, f"chain.yaml not found: {chain}")

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
    """
    Get last run for a chain from SQLite (no race conditions)

    Uses runs table instead of reading last_run.json file.
    Benefits:
    - No file locks
    - Atomic reads
    - 10x faster
    - No race conditions
    """
    from treehopper.sync_to_sqlite import get_recent_runs

    # Query SQLite for most recent run of this chain
    all_recent = get_recent_runs(limit=100)
    chain_runs = [r for r in all_recent if r.get("chain_name") == chain]

    if not chain_runs:
        raise HTTPException(404, f"No runs found for chain: {chain}")

    # Return most recent (already sorted by created_at DESC)
    last_run = chain_runs[0]

    return {"chain": chain, "last_run": last_run}


# -------------------------------------------------------------------
# Agent YAML Viewer
# -------------------------------------------------------------------


# @app.get("/api/v1/agents/{agent}/yaml")
# def get_agent_yaml(agent: str):
#     agent_dir = REGISTRY_DIR / "agents"
#     matches = list(agent_dir.glob(f"{agent}-*/agent.yaml"))

#     if not matches:
#         raise HTTPException(404, f"Agent YAML not found: {agent}")

#     return {
#         "agent": agent,
#         "yaml": matches[0].read_text(),
#     }


@app.get("/api/v1/agents/{agent}/yaml")
def get_agent_yaml(agent: str):
    """
    Get agent YAML from SQLite cache (Phase 2)
    Falls back to file if not cached
    """
    # Try SQLite cache first (10x faster)
    yaml_content = get_yaml("agent", agent)

    if yaml_content:
        return {"agent": agent, "yaml": yaml_content}

    # Fallback to file (not yet cached)
    agent_dir = REGISTRY_DIR / "agents"
    matches = list(agent_dir.glob(f"{agent}-*/agent.yaml"))

    if not matches:
        raise HTTPException(404, f"agent.yaml not found for: {agent}")

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


def format_value(v: Any) -> Any:
    """Helper to convert numbers >= 1,000,000 to '1MN' string format."""
    if isinstance(v, (int, float)) and v >= 1000000:
        return f"{v / 1000000:.1f}MN".replace(".0MN", "MN")
    return v


def recursive_format(data: Any) -> Any:
    """Recursively walks through dicts and lists to format numbers."""
    if isinstance(data, dict):
        return {k: recursive_format(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [recursive_format(i) for i in data]
    else:
        return format_value(data)


@app.get("/admin/storage")
def admin_storage():
    # mock data testing
    return get_storage_metrics()


# FIXED: Accept window parameter and return only that data
@app.get("/api/v1/summary")
def get_summary(window: str = Query("24h", regex="^(1h|24h|7d)$")):
    """
    Get analytics summary for specified time window.

    Args:
        window: Time window - one of: 1h, 24h, 7d (default: 24h)

    Returns:
        Analytics summary for the requested time window
    """
    now = time.time()

    window_seconds = {
        "1h": 3600,
        "24h": 86400,
        "7d": 604800,
    }

    # Get seconds for requested window
    seconds = window_seconds.get(window, 86400)  # default to 24h
    cutoff = now - seconds

    # Fetch data for requested window
    rows = db.fetch_all(
        """
        SELECT *
        FROM analytics_events
        WHERE ts >= ?
        """,
        (cutoff,),
    )

    # Build summary for this window
    summary = _build_summary(rows, window)

    # Inject shared files info
    files_summary = _file_stats()
    summary["files"] = files_summary

    logger.info(f"Analytics for window={window}")
    logger.info(summary)

    # Return data directly (not nested in window key)
    return summary


# -------------------------------------------------------------------
# Chain Execution Endpoints (NEW)
# -------------------------------------------------------------------


def get_chain_steps(chain_name: str):
    print(chain_name)
    if not chain_name:
        return
    steps = []
    all_chains = get_all_chains()
    # print(all_chains)
    for chain in all_chains:
        if chain["chain_name"] == chain_name:
            # print(chain["steps"])
            steps = chain["steps"]
            break
    # print(steps)
    return steps


@app.post("/api/v1/chains/{chain_name}/run")
async def run_chain(chain_name: str, payload: dict = Body(...)):
    """
    Run a chain from the dashboard UI

    This endpoint:
    1. Gets the chain's runtime info (port, endpoint)
    2. Forwards the request to the chain runtime
    3. Returns the execution result

    Args:
        chain_name: Name of the chain to run
        payload: Request payload (includes 'detached' flag for async)

    Returns:
        Chain execution result or error

    Example:
        POST /api/v1/chains/basic_support/run
        {
            "text": "How do I reset my password?",
            "detached": true
        }
    """
    try:
        print(f"[run_chain] Recieved paylaod - {payload}")
        logger.info(f"[run_chain] Recieved paylaod - {payload}")
        # 1. Get runtime info for the chain
        runtime_info = get_chain_runtime_info(chain_name)

        if not runtime_info:
            raise HTTPException(
                status_code=404,
                detail=f"Chain runtime not found for '{chain_name}'. "
                f"Please start the chain first: th chain start {chain_name} --bg --port <PORT>",
            )

        # 2. Check if chain is actually running
        if not runtime_info.get("is_running"):
            raise HTTPException(
                status_code=503,
                detail=f"Chain runtime found but not running (PID {runtime_info.get('pid')} is dead). "
                f"Please restart the chain.",
            )

        # 3. Build the chain runtime endpoint
        port = runtime_info["port"]
        chain_run_url = f"http://localhost:{port}/api/v1/{chain_name}/run"

        logger.info(f"[run_chain] Forwarding request to {chain_run_url}")
        logger.info(f"[run_chain] Payload: {payload}")

        # 4. Forward request to chain runtime
        headers = {
            "x-api-key": DEFAULT_API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(chain_run_url, json=payload, headers=headers)

            # 5. Return response from chain runtime
            if response.status_code == 200:
                result = response.json()
                logger.info(f"[run_chain] Success: {result}")
                return result
            else:
                logger.error(f"[run_chain] Chain runtime error: {response.text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Chain runtime error: {response.text}",
                )

    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to chain runtime. "
            "Is the chain running on the expected port?",
        )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504, detail="Chain execution timed out after 120 seconds"
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"[run_chain] Unexpected error: {str(e)}")
        logger.error(f"[run_chain] Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


def get_chain_runtime_info(chain_name_or_id: str) -> dict | None:
    """
    Get runtime information for a chain

    Checks ~/.treehopper/runtime/ for PID files and returns runtime info

    Args:
        chain_name_or_id: Chain name or chain ID

    Returns:
        Dictionary with runtime info or None
    """
    runtime_dir = TH_ROOT / "runtime"

    if not runtime_dir.exists():
        return None

    # Look for PID file
    # Format: det_chain_{chain_name}-{chain_id}.pid or det_chain_{chain_id}.pid
    pid_files = list(runtime_dir.glob(f"det_chain_*{chain_name_or_id}*.pid"))

    if not pid_files:
        # Try exact match
        pid_files = list(runtime_dir.glob(f"det_chain_{chain_name_or_id}.pid"))

    if not pid_files:
        return None

    # Use first match
    pid_file = pid_files[0]

    try:
        # Read PID file to get port and PID
        with open(pid_file, "r") as f:
            content = f.read().strip()

        # Parse PID file format: "PID:PORT"

        # Parse PID file
        line = content.split(":")
        print(f"[get_chain_runtime_info] {line}")
        logger.info(f"[get_chain_runtime_info] {line}")

        pid = port = 0
        pid, port = int(line[0]), int(line[1])
        print(f"[get_chain_runtime_info] {pid}, {port}")
        logger.info(f"[get_chain_runtime_info] {pid}, {port}")

        if pid == 0 or port == 0:
            return None

        # Check if process is actually running
        try:
            os.kill(pid, 0)  # Signal 0 doesn't kill, just checks existence
            is_running = True
        except OSError:
            is_running = False

        # Extract chain name and ID from filename
        # Format: det_chain_{chain_name}-{chain_id}.pid
        filename = pid_file.stem.replace("det_chain_", "")

        if "-" in filename:
            chain_name, chain_id = filename.rsplit("-", 1)
        else:
            chain_name = filename
            chain_id = filename

        return {
            "chain_name": chain_name,
            "chain_id": chain_id,
            "pid": pid,
            "port": port,
            "is_running": is_running,
            "pid_file": str(pid_file),
        }

    except Exception as e:
        logger.error(f"Error reading PID file {pid_file}: {e}")
        return None


@app.get("/api/v1/chains/{chain_name}/runtime")
async def get_chain_runtime(chain_name: str):
    """
    Get runtime information for a chain

    Returns the server URL, port, and endpoints for a running chain

    Args:
        chain_name: Chain name or chain ID

    Returns:
        Runtime information including endpoints

    Example:
        GET /api/v1/chains/basic_support/runtime

        Response:
        {
            "success": true,
            "data": {
                "chain_name": "basic_support",
                "chain_id": "basic_support-38716e14",
                "runtime_status": "running",
                "runtime_url": "http://localhost:20100",
                "port": 20100,
                "pid": 12345,
                "run_endpoint": "http://localhost:20100/api/v1/basic_support/run",
                "health_endpoint": "http://localhost:20100/api/v1/basic_support/health",
                "logs_endpoint": "http://localhost:20100/api/v1/basic_support/logs"
            }
        }
    """
    try:
        runtime_status = "Running"
        runtime_info = get_chain_runtime_info(chain_name)

        if not runtime_info:
            raise HTTPException(
                status_code=404,
                detail=f"Chain runtime not found for: {chain_name}. Is the chain running?",
            )

        chain_name = runtime_info["chain_name"]
        chain_id = runtime_info["chain_id"]
        port = runtime_info["port"]
        pid = runtime_info["pid"]
        is_running = runtime_info["is_running"]

        if not is_running:
            raise HTTPException(
                status_code=503,
                detail=f"Chain runtime found but not running (PID {pid} is dead)",
            )

        # Build runtime URLs
        base_url = f"http://localhost:{port}"
        api_base = f"{base_url}/api/v1/{chain_name}"
        steps = get_chain_steps(chain_name=chain_name)
        print(f"[get_chain_runtime] chain steps count: {len(steps)}")
        logger.info(f"[get_chain_runtime] chain steps count: {len(steps)}")
        return {
            "success": True,
            "data": {
                "chain_name": chain_name,
                "chain_id": chain_id,
                "runtime_status": runtime_status,
                "runtime_url": base_url,
                "port": port,
                "pid": pid,
                "stepCount": len(steps),
                "run_endpoint": f"{api_base}/run",
                "health_endpoint": f"{api_base}/health",
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting chain runtime info: {str(e)}"
        )


@app.get("/api/v1/chains/list-running")
async def list_running_chains():
    """
    List all currently running chains

    Returns:
        List of running chains with their runtime info

    Example:
        GET /api/v1/chains/list-running

        Response:
        {
            "success": true,
            "count": 2,
            "chains": [
                {
                    "chain_name": "basic_support",
                    "chain_id": "basic_support-38716e14",
                    "port": 20100,
                    "pid": 12345,
                    "runtime_url": "http://localhost:20100",
                    "run_endpoint": "http://localhost:20100/api/v1/basic_support/run"
                }
            ]
        }
    """
    try:
        runtime_dir = TH_ROOT / "runtime"
        print(runtime_dir.exists())
        if not runtime_dir.exists():
            return {"success": True, "count": 0, "chains": []}

        running_chains = []
        runtime_status = "Running"
        # Find all PID files

        for pid_file in runtime_dir.glob("det_chain_*.pid"):
            try:
                # Read PID file
                with open(pid_file, "r") as f:
                    content = f.read().strip()

                # Parse PID file
                line = content.split(":")
                print(f"[list_running_chains] {line}")
                logger.info(f"[list_running_chains] {line}")
                pid = port = 0
                pid, port = int(line[0]), int(line[1])
                print(f"[list_running_chains] {pid}, {port}")
                logger.info(f"[list_running_chains] {pid}, {port}")
                # Check if running

                try:
                    os.kill(pid, 0)
                    is_running = True
                except OSError:
                    is_running = False

                if is_running:
                    runtime_status = "Running"
                    print(f"[list_running_chains] Is Chain running: {is_running}")
                    logger.info(f"[list_running_chains] Is Chain running: {is_running}")
                    # Extract chain info from filename
                    filename = pid_file.stem.replace("det_chain_", "")

                    print(f"[list_running_chains] PID File: {pid_file}")
                    logger.info(f"[list_running_chains] PID File: {pid_file}")

                    if "-" in filename:
                        chain_name, chain_id = filename.rsplit("-", 1)
                    else:
                        chain_name = filename
                        chain_id = filename

                    base_url = f"http://localhost:{port}"
                    steps = get_chain_steps(chain_name=chain_name)
                    print(f"[list_running_chains] chain steps count: {len(steps)}")
                    logger.info(
                        f"[list_running_chains] chain steps count: {len(steps)}"
                    )
                    api_base = f"{base_url}/api/v1/{chain_name}"
                    chain_cfg = {
                        "chain_name": chain_name,
                        "chain_id": chain_id,
                        "port": port,
                        "pid": pid,
                        "stepCount": len(steps),
                        "runtime_url": base_url,
                        "run_endpoint": f"{api_base}/run",
                        "runtime_status": runtime_status,
                        "health_endpoint": f"{api_base}/health",
                    }
                    print(f"[list_running_chains] {chain_cfg}")
                    logger.info(f"[list_running_chains] {chain_cfg}")
                    running_chains.append(chain_cfg)
            except Exception as e:
                print(f"[list_running_chains] Error processing {pid_file}: {e}")
                logger.error(f"[list_running_chains] Error processing {pid_file}: {e}")
                continue

        return {"success": True, "count": len(running_chains), "chains": running_chains}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error listing running chains: {str(e)}"
        )


@app.get("/api/v1/chains/{chain_name}/status")
async def get_chain_status(chain_name: str):
    """
    Quick status check for a chain

    Returns:
        Simple status object

    Example:
        GET /api/v1/chains/basic_support/status

        Response:
        {
            "status": "running",
            "chain_name": "basic_support",
            "chain_id": "basic_support-38716e14",
            "port": 20100,
            "pid": 12345
        }
    """
    try:
        runtime_info = get_chain_runtime_info(chain_name)

        if not runtime_info:
            return {"status": "stopped", "message": "Chain runtime not found"}

        is_running = runtime_info["is_running"]

        return {
            "status": "running" if is_running else "stopped",
            "chain_name": runtime_info["chain_name"],
            "chain_id": runtime_info["chain_id"],
            "port": runtime_info["port"] if is_running else None,
            "pid": runtime_info["pid"],
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}


# -------------------------------------------------------------------
# Static UI (single-page visualizer)
# -------------------------------------------------------------------

app.mount(
    "/",
    StaticFiles(directory=Path(__file__).parent / "static", html=True),
    name="ui",
)
