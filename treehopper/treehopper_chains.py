# treehopper/treehopper_chains.py
import json
import os

# import re
import signal
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, NoReturn
import socket
import requests
import yaml
import asyncio
import hashlib
from treehopper.agent_runtime import run_agent_path as _run_agent_path_local
from treehopper.treehopper_cancellation import (
    cancel_chain_id,
    cancel_batch,
)

from treehopper.utils.shared_files import (
    has_only_one_shared_file,
    get_the_only_shared_file,
)
from treehopper.utils.commons import get_or_create_subscription_id, validate_chain_name
from treehopper.treehopper_parallel import parallel_chain_run_entry
from treehopper.utils import run_registry as run_registry_mod
from treehopper.utils.config import read_pid_and_port

from treehopper.th_config import (
    API_KEY,
    MAIN_PORT,
    BASE_URL,
    # HOME,
    TH_ROOT,
    # REGISTRY_DIR,
    # REGISTRY_AGENTS,
    # REGISTRY_AGENTS_INDEX,
    CHAINS_DIR,
    # CHAINS_INDEX,
    RUNTIME_DIR,
    CHAIN_PID_PREFIX,
    CANCEL_DIR,
    DEFAULT_MAX_STEPS_PER_CHAIN,
    DEFAULT_MAX_PARALLEL_PER_STEP,
    BUILTIN_MERGE_AGENTS,
    BUILTIN_AGENTS,
    DEFAULT_API_KEY,
    ensure_dirs,
)

# from treehopper.visualizer.db_init import DBInitializer
from treehopper.th_setup import setup_treehopper
from treehopper.logging import get_logger
from treehopper.maintainance.maintainer import startup_maintenance
from treehopper.utils.commons import (
    load_chains_index,
    save_chains_index,
    load_agents_index,
    ensure_registry_dirs,
)

# Add with other imports
from treehopper.sync_to_sqlite import sync_chains, sync_yaml
from treehopper.visualizer.chain_vu import chain_flow_viewer

logger = get_logger()
logger.info("Inside Treehopper chains")

# -----------------------------------------------------------------------------
# MODELS / HELPERS
# -----------------------------------------------------------------------------


@dataclass
class ChainRef:
    chain_name: str
    chain_id: str
    cfg_path: Path
    dir_path: Path


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex(("127.0.0.1", port)) == 0


# def derive_chain_port(chain_id: str) -> int:
#     """
#     Predictable hash-based port:
#       20000–24999 range based on chain_id.
#     """
#     h = abs(hash(chain_id))
#     return 20000 + (h % 5000)


def derive_chain_port(chain_id: str) -> int:
    """
    Deterministic, stable port mapping for chain runtimes.
    Uses SHA256 instead of Python's non-deterministic hash().
    """
    h = hashlib.sha256(chain_id.encode()).hexdigest()
    num = int(h[:6], 16)  # first 3 bytes
    return 20000 + (num % 5000)


def read_pid(path: Path) -> Optional[int]:
    if not path.exists():
        return None
    try:
        text = path.read_text().strip()
        if ":" in text:
            pid_str, _ = text.split(":", 1)
            return int(pid_str)
        return int(text)
    except Exception:
        return None


def write_pid(path: Path, pid: int, port: int | None = None) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    if port is not None:
        path.write_text(f"{pid}:{port}")
    else:
        path.write_text(str(pid))


def kill_pid(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    time.sleep(3)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return


def agent_exists(agent_name: str) -> bool:
    """
    Check whether an agent exists in the local registry.
    """
    agents = load_agents_index()
    return any(a.get("agent_name") == agent_name for a in agents)


def load_agent_spec(agent_name: str) -> Dict[str, Any]:
    """
    Load agent specification (inputs / outputs) from registry.

    This is a CLI-time contract check, not a runtime import.
    """
    agents = load_agents_index()
    for agent in agents:
        if agent.get("agent_name") == agent_name:
            return {
                "inputs": agent.get("inputs", []),
                "outputs": agent.get("outputs", []),
            }

    fail(f"Agent '{agent_name}' not found in registry")


def is_input_resolvable(
    inp: Dict[str, Any],
    agent: Dict[str, Any],
    available_outputs: set,
) -> bool:
    """
    Determine whether an input can be resolved at runtime.

    Resolution rules:
    1. Explicit source: step.agent.field must exist
    2. Request payload inputs are always allowed
    3. Implicit reference to previous step outputs is allowed
    """
    source = inp.get("source")
    name = inp.get("name")

    # 1️⃣ Explicit request mapping
    if source == "request":
        return True

    # 2️⃣ Explicit fully-qualified reference
    # e.g. extract.pdf_extractor.text
    if isinstance(source, str) and "." in source:
        return source in available_outputs

    # 3️⃣ Implicit resolution by name (from previous steps only)
    return name in {out.split(".")[-1] for out in available_outputs}


def ensure_main_server() -> None:
    """
    Simple health check + lazy start for the MAIN server on MAIN_PORT.
    """
    from dotenv import load_dotenv

    load_dotenv()
    # 🚨 TEST MODE GUARD
    if os.getenv("TREEHOPPER_RUNTIME_MODE") == "1":
        print("Test Mode Enabled - Returning")
        logger.info("Test Mode Enabled - Returning")
        return
    print("Chain Run Mode Enabled - continuing")
    logger.info("Chain Run Mode Enabled - continuing")
    try:
        r = requests.get(f"{BASE_URL}/api/v1/sys/health", timeout=0.3)
        if r.status_code == 200:
            return
    except Exception:
        pass

    print("⚠️  Main Treehopper server not running — starting...")
    subprocess.Popen(["treehopper", "run"])

    for _ in range(30):
        time.sleep(0.25)
        try:
            r = requests.get(f"{BASE_URL}/api/v1/sys/health", timeout=0.25)
            if r.status_code == 200:
                print("✅ Main server is up")
                return
        except Exception:
            continue

    print("⚠️ Could not confirm main server health — continuing anyway.")


def resolve_chain(ref: str) -> ChainRef:
    """
    Resolve a chain either by name or id.
    """
    ensure_registry_dirs()
    index = load_chains_index()

    match = None
    for c in index:
        if c.get("chain_name") == ref or c.get("chain_id") == ref:
            match = c
            break

    if not match:
        # fallback: look by folder
        for folder in CHAINS_DIR.glob("*"):
            cfg_path = folder / "chain.yaml"
            if not cfg_path.exists():
                continue
            try:
                cfg = yaml.safe_load(cfg_path.read_text())
            except Exception:
                continue
            if cfg.get("chain_name") == ref or cfg.get("chain_id") == ref:
                match = {
                    "chain_name": cfg["chain_name"],
                    "chain_id": cfg["chain_id"],
                }
                break

    if not match:
        print(f"❌ No chain found matching '{ref}'")
        sys.exit(1)

    cid = match["chain_id"]
    cname = match["chain_name"]
    dir_path = CHAINS_DIR / cid
    cfg_path = dir_path / "chain.yaml"
    if not cfg_path.exists():
        print(f"❌ chain.yaml missing for chain {cid}")
        sys.exit(1)

    return ChainRef(
        chain_name=cname, chain_id=cid, cfg_path=cfg_path, dir_path=dir_path
    )


def load_chain_cfg(ref: ChainRef) -> Dict[str, Any]:
    try:
        return yaml.safe_load(ref.cfg_path.read_text())
    except Exception as e:
        print(f"❌ Failed to read chain.yaml: {e}")
        sys.exit(1)


# -----------------------------------------------------------------------------
# CHAIN BUILD
# -----------------------------------------------------------------------------


def chain_build(chain_name: str, agent_names: List[str]) -> None:
    if not agent_names:
        print("❌ You must provide at least one agent for the chain")
        sys.exit(1)

    try:
        cname = validate_chain_name(chain_name)
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)

    ensure_registry_dirs()
    chains_index = load_chains_index()

    if any(c["chain_name"] == cname for c in chains_index):
        print(f"❌ Chain name '{cname}' already exists")
        sys.exit(1)

    agents_index = load_agents_index()
    if not agents_index:
        print("❌ No agents installed in registry. Build agents first.")
        sys.exit(1)

    registry_by_name = {a["agent_name"]: a for a in agents_index}

    steps: List[Dict[str, Any]] = []
    for agent_name in agent_names:
        if agent_name not in registry_by_name:
            print(f"❌ Unknown agent: '{agent_name}'")
            sys.exit(1)

        meta = registry_by_name[agent_name]
        steps.append(
            {
                "agent_name": agent_name,
                "path": meta["routes"]["by_name"],  # /api/v1/agents/<name>
                "inputs": meta.get("inputs", []),
                "outputs": meta.get("outputs", []),
            }
        )

    chain_id = f"{cname}-{uuid.uuid4().hex[:8]}"
    chain_dir = CHAINS_DIR / chain_id
    chain_dir.mkdir(parents=True, exist_ok=False)

    endpoint = f"/api/v1/chains/{cname}"
    subscription_id = get_or_create_subscription_id()

    cfg = {
        "chain_name": cname,
        "chain_id": chain_id,
        "subscription_id": subscription_id,
        "endpoint": endpoint,
        "method": "POST",
        "agents": steps,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "description": f"Chain '{cname}' with {len(steps)} agents.",
    }

    (chain_dir / "chain.yaml").write_text(
        yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8"
    )

    chains_index.append(cfg)
    save_chains_index(chains_index)
    # ✅ NEW: Sync to SQLite
    try:
        sync_chains()
        logger.info("[sqlite_sync] completed")
    except Exception as e:
        print(f"⚠️  SQLite sync failed: {e}")
        logger.error(f"⚠️  SQLite sync failed: {e}")

    # ✅ NEW: Cache YAML in SQLite (Phase 2)
    try:
        sync_yaml(
            entity_type="chain",
            entity_name=cname,
            entity_id=chain_id,
            yaml_content=yaml.dump(cfg, default_flow_style=False, sort_keys=False),
        )
        print("✅ Chain YAML cached in database")
    except Exception as e:
        print(f"⚠️  Failed to cache YAML: {e}")

    print(f"✅ Created chain '{cname}' ({chain_id})")
    print(f"📌 Endpoint: {endpoint} [POST]")
    print("📌 Agents in sequence:")
    for i, s in enumerate(steps):
        print(f"  {i+1}. {s['agent_name']}  →  {s['path']}")

    print("\n▶ Example run via CLI (non-detached):")
    print(f'  treehopper chain run {cname} --payload \'{{"doc_text": "..."}}\'')
    print("▶ Example run via HTTP:")
    print(
        f"  curl -X POST http://localhost:{MAIN_PORT}{endpoint} -H 'x-api-key: demo-key-123' \
             -H 'Content-Type: application/json' -d '{{\"doc_text\": \"...\"}}'"
    )


# -----------------------------------------------------------------------------
# CHAIN RUN HELPERS
# -----------------------------------------------------------------------------


def parse_payload_args(args: List[str]) -> Dict[str, Any]:
    """
    Parse --payload and --payload-file out of args.
    Returns: (clean_args, payload_dict)
    """
    payload: Optional[Dict[str, Any]] = None
    remaining: List[str] = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--payload" and i + 1 < len(args):
            raw = args[i + 1]
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as e:
                print(f"❌ Invalid JSON in --payload: {e}")
                sys.exit(1)
            i += 2
        elif arg == "--payload-file" and i + 1 < len(args):
            path = Path(args[i + 1])
            if not path.exists():
                print(f"❌ Payload file not found: {path}")
                sys.exit(1)
            try:
                payload = json.loads(path.read_text())
            except json.JSONDecodeError as e:
                print(f"❌ Invalid JSON in file {path}: {e}")
                sys.exit(1)
            i += 2
        else:
            remaining.append(arg)
            i += 1

    return {"args": remaining, "payload": payload or {}}


def chain_start(chain_ref: ChainRef, port_override: int | None = None) -> None:
    """
    Start chain runtime ONLY.
    No execution, no run_id, no registry writes.
    """
    ensure_main_server()

    pid_file = RUNTIME_DIR / f"{CHAIN_PID_PREFIX}{chain_ref.chain_id}.pid"

    existing_pid, existing_port = read_pid_and_port(pid_file)
    if existing_pid:
        try:
            os.kill(existing_pid, 0)
            print(f"🟢 Chain runtime already running on port {existing_port}")
            return
        except OSError:
            pid_file.unlink(missing_ok=True)

    actual_port = port_override or derive_chain_port(chain_ref.chain_id)

    env = os.environ.copy()
    env["CHAIN_NAME"] = chain_ref.chain_name
    env["CHAIN_ID"] = chain_ref.chain_id
    env["CHAIN_DIR"] = str(chain_ref.dir_path)
    env["TREEHOPPER_TH_ROOT"] = str(TH_ROOT.resolve())
    # env["TREEHOPPER_HOME"] = str(TH_ROOT.resolve())
    env["TREEHOPPER_RUNTIME_DIR"] = str(RUNTIME_DIR.resolve())
    env["TREEHOPPER_CANCEL_DIR"] = str(CANCEL_DIR.resolve())
    env["PROD"] = "1"
    env["UVICORN_WORKERS"] = "1"

    LOG_FILE = RUNTIME_DIR / f"chain_{chain_ref.chain_name}-{chain_ref.chain_id}.log"

    proc = subprocess.Popen(
        [
            "uvicorn",
            "treehopper.chain_runtime_app:app",
            "--host",
            "0.0.0.0",
            "--port",
            str(actual_port),
        ],
        env=env,
        stdout=open(LOG_FILE, "w"),
        stderr=subprocess.STDOUT,
    )

    write_pid(pid_file, proc.pid, actual_port)

    print(f"🚀 Chain runtime started for {chain_ref.chain_name}")
    print(f"📡 Listening on http://localhost:{actual_port}")


def chain_run_local(chain_ref: ChainRef, payload: Dict[str, Any]) -> None:
    """
    Execute the chain via the main Treehopper server's
    /api/v1/chains/{name} endpoint.
    """
    # detached = False
    ensure_main_server()
    cfg = load_chain_cfg(chain_ref)
    endpoint = cfg.get("endpoint") or f"/api/v1/chains/{chain_ref.chain_name}"
    # endpoint = f"/api/v1/chains/run/{chain_ref.chain_name}"

    url = f"{BASE_URL}{endpoint}/run"

    # --- Auto file_path injection for first agent if payload is empty ---
    cfg = load_chain_cfg(chain_ref)
    first_agent = cfg.get("agents", [])[0] if cfg.get("agents") else None
    if first_agent:
        first_agent_name = first_agent.get("agent_name", "")
        first_agent_id = first_agent.get("agent_id", "")
        if payload == {} and has_only_one_shared_file(first_agent_id):
            auto_path = get_the_only_shared_file(first_agent_id)
            print(
                f"🔌 Auto-injecting payload for '{first_agent_name}': file_path='{auto_path}'"
            )
            payload = {"file_path": auto_path}

    print(f"▶ Executing chain '{chain_ref.chain_name}' via {url}")
    r = requests.post(url, json=payload or {}, headers=API_KEY)

    try:
        data = r.json()
    except Exception:
        print(f"HTTP {r.status_code}")
        print(r.text)
        return

    if r.status_code != 200:
        print(f"HTTP {r.status_code}")
        print(data)
        return

    results = data.get("results", [])
    agents = cfg.get("agents", [])

    print("📊 Chain step results:")
    for i, res in enumerate(results):
        name = agents[i]["agent_name"] if i < len(agents) else f"step_{i}"
        status = "✓ success"
        if isinstance(res, dict) and "error" in res:
            status = f"✗ error: {res['error']}"
        print(f"  [{name}] {status}")

    # last_run.json is written by server; just show path
    history_path = chain_ref.dir_path / "last_run.json"
    if history_path.exists():
        print("\n🔍 Full response stored at:")
        print(f"  {history_path}")
    else:
        print("\nℹ️ No last_run.json written by server (check Treehopper logs).")


def chain_run_detached(
    chain_ref: ChainRef,
    payload: Dict[str, Any],
    port_override: int | None = None,
) -> None:
    """
    Execute a chain run against a detached runtime.
    Starts runtime ONLY if not already running.
    """

    ensure_main_server()

    cfg = load_chain_cfg(chain_ref)
    print(f"chain config : {cfg}")

    pid_file = RUNTIME_DIR / f"{CHAIN_PID_PREFIX}{chain_ref.chain_id}.pid"

    # ------------------------------------------------------------
    # Resolve runtime port (prefer existing runtime)
    # ------------------------------------------------------------
    existing_pid, existing_port = read_pid_and_port(pid_file)
    actual_port = (
        existing_port or port_override or derive_chain_port(chain_ref.chain_id)
    )

    runtime_spawned = False

    # ------------------------------------------------------------
    # Start runtime ONLY if not alive
    # ------------------------------------------------------------
    if existing_pid:
        try:
            os.kill(existing_pid, 0)
        except OSError:
            pid_file.unlink(missing_ok=True)
            existing_pid = None

    if not existing_pid:
        runtime_spawned = True
        print(f"Runtime Spawned - {runtime_spawned}")

        LOG_FILE = (
            RUNTIME_DIR / f"chain_{chain_ref.chain_name}-{chain_ref.chain_id}.log"
        )

        env = os.environ.copy()

        # --- forward only safe runtime env ---
        for k in [
            "TH_LLM_PROVIDER",
            "TH_TEST_MODE",
            "OPENAI_API_KEY",
            "PERPLEXITY_API_KEY",
            "GEMINI_API_KEY",
            "TH_OPENAI_MODEL",
            "TH_PERPLEXITY_MODEL",
            "TH_GEMINI_MODEL",
            "TH_OPENAI_TEMPERATURE",
        ]:
            value = os.getenv(k)
            if value is not None:
                env[k] = value

        env.update(
            {
                "CHAIN_NAME": chain_ref.chain_name,
                "CHAIN_ID": chain_ref.chain_id,
                "CHAIN_DIR": str(chain_ref.dir_path),
                "TREEHOPPER_TH_ROOT": str(TH_ROOT.resolve()),
                # "TREEHOPPER_HOME": str(TH_ROOT.resolve()),
                "TREEHOPPER_RUNTIME_DIR": str(RUNTIME_DIR.resolve()),
                "TREEHOPPER_CANCEL_DIR": str(CANCEL_DIR.resolve()),
                "PROD": "1",
                "PYTHONUNBUFFERED": "1",
                "UVICORN_WORKERS": "1",
            }
        )

        # Optional dev injection
        try:
            if os.getenv("TREEHOPPER_DEV_MODE") == "1":
                from treehopper.environment import inject_pythonpath

                inject_pythonpath(env)
        except Exception:
            pass

        proc = subprocess.Popen(
            [
                "uvicorn",
                "treehopper.chain_runtime_app:app",
                "--host",
                "0.0.0.0",
                "--port",
                str(actual_port),
            ],
            env=env,
            stdout=open(LOG_FILE, "w"),
            stderr=subprocess.STDOUT,
        )

        write_pid(pid_file, proc.pid, actual_port)

        # wait for runtime health
        for _ in range(40):
            try:
                r = requests.get(
                    f"http://localhost:{actual_port}/api/v1/{chain_ref.chain_name}/health",
                    timeout=0.3,
                )
                if r.status_code == 200:
                    break
            except Exception:
                pass
            time.sleep(0.25)

    # ------------------------------------------------------------
    # Generate run_id (single source of truth)
    # ------------------------------------------------------------
    run_id = run_registry_mod.make_run_id(chain_ref.chain_name)

    run_registry_mod.record_chain_run(
        chain_name=chain_ref.chain_name,
        chain_id=chain_ref.chain_id,
        chain_dir=chain_ref.dir_path,
        payload=payload,
        results=[],
        detached=True,
        success=False,
        run_id=run_id,
        cancelled=False,
        status="pending",
        current_step_index=-1,
    )

    # ------------------------------------------------------------
    # Fire-and-forget POST to runtime
    # ------------------------------------------------------------
    url = f"http://localhost:{actual_port}/api/v1/{chain_ref.chain_name}/run"

    headers = {
        "x-api-key": DEFAULT_API_KEY,
        "X-Treehopper-Run-Id": run_id,
    }

    _post_runtime_detached(url=url, payload=payload or {}, headers=headers)

    print(f"🚀 Detached chain triggered → run_id={run_id}")
    print(f"📡 Runtime: http://localhost:{actual_port}")
    print(f"📁 Track: {chain_ref.dir_path}/runs/{run_id}.json")
    print(f"RUN_ID: {run_id}")


# def chain_run_detached(
#     chain_ref: ChainRef,
#     payload: Dict[str, Any],
#     port_override: int | None = None,
#     run_once: bool = True,
# ) -> None:

#     ensure_main_server()

#     cfg = load_chain_cfg(chain_ref)
#     print(f"chain config : {cfg}")

#     pid_file = RUNTIME_DIR / f"{CHAIN_PID_PREFIX}{chain_ref.chain_id}.pid"

#     # Prefer existing runtime port if available
#     existing_pid, existing_port = read_pid_and_port(pid_file)
#     if existing_pid and existing_port:
#         actual_port = existing_port
#     else:
#         actual_port = port_override or derive_chain_port(chain_ref.chain_id)

#     # ----------------------------------------------------------------------
#     # ALWAYS GENERATE RUN_ID HERE — SINGLE SOURCE OF TRUTH
#     # ----------------------------------------------------------------------
#     run_id = run_registry_mod.make_run_id(chain_ref.chain_name)
#     batch_id = None  # batch mode not used in direct detached run

#     # ----------------------------------------------------------------------
#     # Early checkpoint (pending)
#     # ----------------------------------------------------------------------
#     run_registry_mod.record_chain_run(
#         chain_name=chain_ref.chain_name,
#         chain_id=chain_ref.chain_id,
#         chain_dir=chain_ref.dir_path,
#         payload=payload,
#         results=[],
#         detached=True,
#         success=False,
#         run_id=run_id,
#         cancelled=False,
#         status="pending",
#         current_step_index=-1,
#     )

#     # ----------------------------------------------------------------------
#     # START RUNTIME IF NOT ALIVE
#     # ----------------------------------------------------------------------
#     existing_pid, existing_port = read_pid_and_port(pid_file)
#     if existing_pid:
#         try:
#             os.kill(existing_pid, 0)
#             actual_port = existing_port or actual_port
#         except OSError:
#             print("Process is not alive")
#             existing_pid = None

#     if not existing_pid:
#         LOG_FILE = (
#             RUNTIME_DIR / f"chain_{chain_ref.chain_name}-{chain_ref.chain_id}.log"
#         )

#         # ======================================================================
#         # 🔥 CRITICAL PATCH — Inject absolute, unified FS paths into runtime
#         # ======================================================================
#         env = os.environ.copy()

#         # ------------------------------------------------------------------
#         # ⭐ CLEAN FIX: Forward ONLY essential LLM environment variables
#         # ------------------------------------------------------------------
#         LLM_ENV_KEYS = [
#             "TH_LLM_PROVIDER",
#             "TH_TEST_MODE",
#             "OPENAI_API_KEY",
#             "PERPLEXITY_API_KEY",
#             "GEMINI_API_KEY",
#             "TH_OPENAI_MODEL",
#             "TH_PERPLEXITY_MODEL",
#             "TH_GEMINI_MODEL",
#             "TH_OPENAI_TEMPERATURE",
#         ]

#         for key in LLM_ENV_KEYS:
#             value = os.getenv(key)
#             if value:
#                 env[key] = value
#         # ------------------------------------------------------------------
#         env["CHAIN_NAME"] = chain_ref.chain_name
#         env["CHAIN_ID"] = chain_ref.chain_id
#         env["CHAIN_DIR"] = str(chain_ref.dir_path)
#         # 🔥 ADD THESE LINES:
#         # from treehopper.treehopper_cancellation import DB_PATH
#         # env["TREEHOPPER_DB_PATH"] = str(DB_PATH.resolve())  # ← Force same DB

#         env["PROD"] = "1"

#         # Absolute paths — the FIX for cancellation detection
#         env["TREEHOPPER_TH_ROOT"] = str(TH_ROOT.resolve())
#         env["TREEHOPPER_RUNTIME_DIR"] = str(RUNTIME_DIR.resolve())
#         env["TREEHOPPER_CANCEL_DIR"] = str(CANCEL_DIR.resolve())

#         # Uvicorn & Python safety
#         env["PYTHONUNBUFFERED"] = "1"  # real-time logs
#         env["UVICORN_WORKERS"] = "1"  # avoid forked workers (breaks FS sync)

#         # ----------------------------------------------------------------------
#         # DEV: inject local source into PYTHONPATH for subprocesses (guarded)
#         # ----------------------------------------------------------------------
#         # This is opt-in: set TREEHOPPER_DEV_MODE=1 in your shell / CI env to enable.
#         try:
#             # mark dev-mode for the child process (only when you explicitly opt in)
#             if os.getenv("TREEHOPPER_DEV_MODE") == "1":
#                 env["TREEHOPPER_DEV_MODE"] = "1"
#             # import helper if present
#             from treehopper.environment import inject_pythonpath

#             # only run injection when dev flag present in environment or parent process
#             if env.get("TREEHOPPER_DEV_MODE") == "1":
#                 inject_pythonpath(env)
#         except Exception:
#             # Don't break if the helper isn't available — fallback to default behavior.
#             pass
#         # ----------------------------------------------------------------------

#         # ======================================================================
#         # Launch chain runtime
#         # ======================================================================
#         proc = subprocess.Popen(
#             [
#                 "uvicorn",
#                 "treehopper.chain_runtime_app:app",
#                 "--host",
#                 "0.0.0.0",
#                 "--port",
#                 str(actual_port),
#             ],
#             env=env,
#             stdout=open(LOG_FILE, "w"),
#             stderr=subprocess.STDOUT,
#         )

#         write_pid(pid_file, proc.pid, actual_port)

#         # Wait for runtime health
#         for _ in range(40):
#             try:
#                 r = requests.get(
#                     f"http://localhost:{actual_port}/api/v1/{chain_ref.chain_name}/health"
#                 )
#                 if r.status_code == 200:
#                     break
#             except requests.RequestException:
#                 pass
#             time.sleep(0.25)

#     # ----------------------------------------------------------------------
#     # POST request to runtime with forwarded run_id
#     # ----------------------------------------------------------------------
#     url = f"http://localhost:{actual_port}/api/v1/{chain_ref.chain_name}/run"

#     headers = {
#         "x-api-key": "demo-key-123",
#         "X-Treehopper-Run-Id": run_id,
#     }
#     if batch_id:
#         headers["X-Treehopper-Batch-Id"] = batch_id

#     # ----------------------------------------------------------------------
#     # 🔥 Minimal Patch:
#     #   Fire-and-forget JSON POST using curl in a background subprocess.
#     #   CLI returns immediately, chain runtime logs progress independently.
#     #   No blocking → cancellation polling becomes correct.
#     # ----------------------------------------------------------------------
#     _post_runtime_detached(
#         url=url, payload=payload or {}, headers=headers  # ← dict, NOT json.dumps
#     )

#     print(f"🚀 Detached chain triggered → run_id={run_id}")
#     print(f"📡 Runtime executing independently at http://localhost:{actual_port}")
#     print(f"📁 Track status via JSON at: {chain_ref.dir_path}/runs/{run_id}.json")

#     print(f"RUN_ID: {run_id}")

#     if run_once:
#         pid = read_pid(pid_file)
#         if pid:
#             kill_pid(pid)
#             pid_file.unlink(missing_ok=True)


# -----------------------------------------------------------------------------
# CHAIN STOP / DELETE / LOGS
# -----------------------------------------------------------------------------


def chain_stop(ref: str) -> None:
    ensure_registry_dirs()
    chain_ref = resolve_chain(ref)
    pid_file = RUNTIME_DIR / f"{CHAIN_PID_PREFIX}{chain_ref.chain_id}.pid"
    print(
        f"[chains] STOP requested for chain={chain_ref.chain_name} id={chain_ref.chain_id}"
    )
    print(f"[chains] PID file = {pid_file}")
    pid = read_pid(pid_file)
    if not pid:
        print(f"ℹ️ No running runtime found for chain '{chain_ref.chain_name}'")
        return

    print(f"🛑 Stopping chain runtime '{chain_ref.chain_name}' (PID {pid})")
    kill_pid(pid)
    pid_file.unlink(missing_ok=True)
    print("✔ Stopped")


# Helper to delete a single chain (contains the core logic)
def chain_delete_single(ref: str) -> bool:
    ensure_registry_dirs()
    try:
        chain_ref = resolve_chain(ref)
    except Exception as e:
        print(f"❌ Error resolving chain '{ref}': {e}")
        return False

    # Skip confirmation when processing a list (assuming confirmation is done upfront)
    # NOTE: I've removed the interactive confirmation here for mass deletion.
    # If you want confirmation, it should be asked once in the new chain_delete function.

    pid_file = RUNTIME_DIR / f"{CHAIN_PID_PREFIX}{chain_ref.chain_id}.pid"
    pid = read_pid(pid_file)

    print(
        f"\n[chains] DELETE requested for chain={chain_ref.chain_name} id={chain_ref.chain_id}"
    )
    print(f"[chains] run directory = {chain_ref.dir_path}")

    success = True

    # Stop runtime if alive
    if pid:
        print(f"🛑 Stopping chain runtime PID {pid} before delete...")
        kill_pid(pid)
        pid_file.unlink(missing_ok=True)

    # Remove directory recursively
    if chain_ref.dir_path.exists():
        import shutil

        try:
            shutil.rmtree(chain_ref.dir_path)
            print("🗑 Chain directory removed")
        except Exception as e:
            print(f"❌ Error removing directory {chain_ref.dir_path}: {e}")
            success = False

    # Remove chain entry from index
    if success:
        index = load_chains_index()
        original_len = len(index)
        index = [c for c in index if c["chain_id"] != chain_ref.chain_id]

        if len(index) < original_len:
            save_chains_index(index)
            print("📦 Chain removed from registry index")
            # ✅ NEW: Sync to SQLite
            try:
                sync_chains()
                logger.info("[chain_delete_single] sqlite_sync")
            except Exception as e:
                print(f"⚠️  SQLite sync failed: {e}")
                logger.error(f"⚠️  SQLite sync failed: {e}")

        else:
            print("⚠️ Chain not found in registry index (skipped)")

    chain_log_file = (
        RUNTIME_DIR / f"chain_{chain_ref.chain_name}-{chain_ref.chain_id}.log"
    )
    if chain_log_file.exists():
        chain_log_file.unlink(missing_ok=True)
        print(f"✔ Deleted Log file, if existed - '{chain_log_file}'")

    # Clean up stray cancel markers
    for cancel_file in CANCEL_DIR.glob(f"{chain_ref.chain_name}-*.cancel"):
        cancel_file.unlink(missing_ok=True)
        print(f"✔ Deleted Cancel file, if existed - '{cancel_file}'")

    if success:
        print(f"✔ Deleted chain '{chain_ref.chain_name}' ({chain_ref.chain_id})")
    else:
        print(
            f"❌ Failed to delete chain '{chain_ref.chain_name}' ({chain_ref.chain_id})"
        )

    return success


# New wrapper function to handle multiple chains
def chain_delete(refs: List[str]) -> None:
    if not refs:
        print("Usage: treehopper chain delete <name|id> [<name|id>...]")
        sys.exit(1)

    if len(refs) > 1:
        # Ask for global confirmation only if deleting multiple items
        confirm = input(f"⚠️ Delete {len(refs)} chains permanently? y/N: ")
        if confirm.lower() not in ("y", "yes"):
            print("❎ Cancelled mass deletion")
            return

    for ref in refs:
        chain_delete_single(ref)


# def chain_delete(ref: str) -> None:
#     ensure_registry_dirs()
#     chain_ref = resolve_chain(ref)

#     # Confirm deletion
#     confirm = input(
#         f"⚠️ Delete chain '{chain_ref.chain_name}' ({chain_ref.chain_id}) permanently? y/N: "
#     )
#     if confirm.lower() not in ("y", "yes"):
#         print("❎ Cancelled")
#         return

#     pid_file = RUNTIME_DIR / f"{CHAIN_PID_PREFIX}{chain_ref.chain_id}.pid"
#     pid = read_pid(pid_file)

#     print(
#         f"[chains] DELETE requested for chain={chain_ref.chain_name} id={chain_ref.chain_id}"
#     )
#     print(f"[chains] run directory = {chain_ref.dir_path}")

#     # Stop runtime if alive
#     if pid:
#         print(f"🛑 Stopping chain runtime PID {pid} before delete...")
#         kill_pid(pid)
#         pid_file.unlink(missing_ok=True)

#     # Remove directory recursively
#     if chain_ref.dir_path.exists():
#         import shutil

#         shutil.rmtree(chain_ref.dir_path)
#         print("🗑 Chain directory removed")

#     # Remove chain entry from index
#     index = load_chains_index()
#     index = [c for c in index if c["chain_id"] != chain_ref.chain_id]
#     save_chains_index(index)
#     print("📦 Chain removed from registry index")

#     # Clean up stray cancel markers
#     for cancel_file in CANCEL_DIR.glob(f"{chain_ref.chain_name}-*.cancel"):
#         cancel_file.unlink(missing_ok=True)

#     print(f"✔ Deleted chain '{chain_ref.chain_name}' ({chain_ref.chain_id})")


def chain_logs(ref: str) -> None:
    chain_ref = resolve_chain(ref)
    history_path = chain_ref.dir_path / "last_run.json"
    if not history_path.exists():
        print(f"ℹ️ No previous run found for chain '{chain_ref.chain_name}'")
        return

    data = json.loads(history_path.read_text())
    agents = load_chain_cfg(chain_ref).get("agents", [])
    results = data.get("results", [])

    print(f"📜 Last run for chain '{chain_ref.chain_name}':")
    for i, res in enumerate(results):
        name = agents[i]["agent_name"] if i < len(agents) else f"step_{i}"
        status = "✓ success"
        if isinstance(res, dict) and "error" in res:
            status = f"✗ error: {res['error']}"
        print(f"  [{name}] {status}")

    print("\nFull JSON:")
    print(json.dumps(data, indent=2))


def resume_run(run_id: str) -> None:
    """
    Resume an interrupted run by run_id.
    Behavior:
      - Look up run file under CHAINS_DIR/*/runs/<run_id>.json
      - Load chain.yaml for that chain
      - Determine current_step_index (None => 0) and re-run that step
        (Option B semantics: always re-run the current/incomplete step)
      - Execute remaining steps sequentially via MAIN server chain endpoint
        (or call agents directly), updating run history using run_registry.record_chain_run
        (keep same run_id).
    """
    # 1) find run file
    found = None
    for folder in CHAINS_DIR.glob("*"):
        run_file = folder / "runs" / f"{run_id}.json"
        if run_file.exists():
            found = (folder, run_file)
            break
    if not found:
        print(f"❌ Run {run_id} not found")
        sys.exit(1)

    chain_dir, run_file = found
    history = json.loads(run_file.read_text())

    # canonical fields
    cancelled = history.get("cancelled", False)
    status = history.get("status")

    # Do NOT resume already completed runs
    if status == "completed":
        print("❌ Run already completed — not resuming")
        return

    # Determine resume start index:
    # Option B: re-run the 'current_step_index' if it is >= 0.
    # If current_step_index is missing or -1 (pending), start from 0.
    raw_idx = history.get("current_step_index", -1)
    if isinstance(raw_idx, int) and raw_idx >= 0:
        start_idx = raw_idx
    else:
        start_idx = 0

    print(
        f"ℹ️ Resuming run {run_id} (cancelled={cancelled}) starting at step {start_idx}..."
    )

    cfg = yaml.safe_load((chain_dir / "chain.yaml").read_text())
    agents = cfg.get("agents", [])
    payload = history.get("input", {})

    # If run was detached, resume via dedicated micro-app if possible
    detached = history.get("detached", False)

    chain_name = cfg["chain_name"]
    chain_id = cfg["chain_id"]

    # function to run a step locally (calling agent path)
    # Use local agent runner which matches chain runtime behavior
    # from treehopper.agent_runtime import run_agent_path as _run_agent_path_local

    results = history.get("results", []) or []

    # If results exist but we plan to re-run an earlier step, trim results to start_idx
    # For example: if results has entries for steps 0..i but run was marked `current_step_index = i`,
    # we re-run step i and should drop any results[i:] to avoid duplicated downstream inputs.
    if len(results) > start_idx:
        results = results[:start_idx]

    for idx in range(start_idx, len(agents)):
        step = agents[idx]
        path = step.get("path")
        inputs = step.get("inputs", [])
        # build params using same logic as in chain_runtime_app
        if idx == 0:
            params = dict(payload)
        else:
            params = {}
            prev = results[-1] if results else {}
            if inputs:
                for inp in inputs:
                    name = inp.get("name")
                    if name in prev:
                        params[name] = prev[name]
            else:
                params = dict(prev)

        # checkpoint running (mark step idx as running)
        run_registry_mod.record_chain_run(
            chain_name=chain_name,
            chain_id=chain_id,
            chain_dir=chain_dir,
            payload=payload,
            results=results,
            detached=detached,
            success=False,
            run_id=run_id,
            status="running",
            current_step_index=idx,
        )

        try:
            # call agent directly (same as _run_agent_path)
            res = asyncio.run(_run_agent_path_local(path, params))
        except Exception as e:
            # record failure
            run_registry_mod.record_chain_run(
                chain_name=chain_name,
                chain_id=chain_id,
                chain_dir=chain_dir,
                payload=payload,
                results=results + [{"error": str(e)}],
                detached=detached,
                success=False,
                run_id=run_id,
                status="failed",
                current_step_index=idx,
            )
            print(f"✗ Step {idx} failed: {e}")
            return

        results.append(res)

    # final success
    run_registry_mod.record_chain_run(
        chain_name=chain_name,
        chain_id=chain_id,
        chain_dir=chain_dir,
        payload=payload,
        results=results,
        detached=detached,
        success=True,
        run_id=run_id,
        status="completed",
        current_step_index=len(results) - 1 if results else None,
    )
    print(f"✅ Resume completed for run {run_id}")


# -----------------------------------------------------------------------------
# LEGACY SIMPLE CHAIN (for backward compatibility)
# -----------------------------------------------------------------------------


def simple_chain_run(agent_paths: List[str]) -> None:
    """
    Backward-compatible simple mode:

      treehopper chain /api/v1/agents/greet /api/v1/agents/math

    This just calls /api/v1/dev/chain with empty params for each path.
    """
    if not agent_paths:
        print("Usage: treehopper chain <agent_path1> <agent_path2> ...")
        sys.exit(1)

    ensure_main_server()
    body = {"chain": [{"path": p, "params": {}} for p in agent_paths]}
    r = requests.post(f"{BASE_URL}/api/v1/dev/chain", json=body, headers=API_KEY)
    print(r.text)


# -----------------------------------------------------------------------------
# ENTRY POINT FROM treehopper_cli
# -----------------------------------------------------------------------------


def print_chain_help() -> None:
    print(
        """
Treehopper Chain Commands
───────────────────────────────────────────────────────────────────────────────
  [treehopper | th] chain build <name> <agent1> <agent2> ...
      Create a new chain. Installs ~/.treehopper/registry/chains/<chain_id>.

  [treehopper | th] chain run <name|id>
      [--payload '{...}'] [--payload-file file.json]
      [--detached]
      [--parallel N] [--concurrency M]
      Execute a chain sequentially.
      First agent gets payload; later agents receive mapped fields.

      --detached
           Launch a dedicated chain micro-app (async, cancellable, resumable).

      --parallel N
           Run N independent chain executions in parallel (N run_ids).

      --concurrency M
           Max number of parallel runs at a time.

Cancellation Support Matrix
───────────────────────────────────────────────────────────────────────────────---------------------------------
| Execution Mode                          | Cancellable? | Reason                                              |
|-----------------------------------------|--------------|-----------------------------------------------------|
| chain start <chain_name> --bg           |     YES      | to start async micro-app runtime                    |
| chain run <chain_name> --detached       |     YES      | to esxcute async micro-app runtime                  |
| chain run <chain_name> (non detached)   |     NO       | to execute chain on main serverblocking HTTP request|

Resume Functionality (Hybrid)
───────────────────────────────────────────────────────────────────────────────
  [treehopper | th] chain resume <run_id>
      Resume an interrupted chain execution.
      • Skips completed steps (checkpointed)
      • Re-runs only remaining steps
      • Works with detached micro-app runs
      • Will NOT resume completed or cancelled runs

[treehopper | th] chain sweep-resume
            • Scan ALL run files under ~/.treehopper/registry/chains/*/runs/*.json
            • Resume only runs where:
                status in {"pending", "running", "failed"}
                AND cancelled == False
            • Skips:
                completed, cancelled

Other Commands
───────────────────────────────────────────────────────────────────────────────
  [treehopper | th] chain cancel --run <run_id>    Cancel a running detached chain.
  [treehopper | th] chain cancel --batch <batch_id> Cancel all runs in batch.
  [treehopper | th] chain cancel --all <name|id>    Cancel all active runs for a chain.
  [treehopper | th] chain stop <name|id>            Stop detached chain runtime.
  [treehopper | th] chain delete <name|id>          Delete chain & history.
  [treehopper | th] chain logs <name|id>            Show last run summary.
  [treehopper | th] chains status                   show all running chains.
  [treehopper | th] chain vu <name>                 Visualize chain logic flow
  [treehopper | th] chain vu <name> --raw           View raw YAML source
  [treehopper | th] chain vu <name> --json          View raw parsed JSON structure
"""
    )


def _post_runtime_detached(url: str, payload: dict, headers: dict):
    cmd = [
        "curl",
        "-s",
        "-X",
        "POST",
        url,
        "-H",
        f"x-api-key: {headers['x-api-key']}",
        "-H",
        f"X-Treehopper-Run-Id: {headers['X-Treehopper-Run-Id']}",
        "-H",
        "Content-Type: application/json",
        "-d",
        json.dumps(payload),
    ]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def chain_sweep_resume():
    """
    Scan all chain run histories and resume any run that is:
       - pending, running, or failed
       - NOT cancelled
       - NOT completed

    Uses the existing `resume_run(run_id)` function.

    This version is verbose for debugging reasons and explains why runs are skipped.
    """
    ensure_registry_dirs()

    resumable = []  # list of (run_id, run_file_path)

    for chain_dir in CHAINS_DIR.glob("*"):
        runs_dir = chain_dir / "runs"
        if not runs_dir.exists():
            continue

        for run_file in runs_dir.glob("*.json"):
            try:
                data = json.loads(run_file.read_text())
            except Exception as e:
                print(f"[sweep] Skipping {run_file} — invalid JSON: {e}")
                continue

            run_id = data.get("run_id")
            status = data.get("status")
            cancelled = data.get("cancelled", False)
            success = data.get("success", False)
            current_idx = data.get("current_step_index", None)
            executed_at = data.get("executed_at", "")

            if not run_id:
                print(f"[sweep] Skipping {run_file} — no run_id")
                continue

            # Decision diagnostics
            if cancelled:
                print(f"[sweep] Skipping {run_id} — cancelled=True")
                continue
            if success:
                print(f"[sweep] Skipping {run_id} — success=True")
                continue

            # Accept explicit statuses or implicit pending marker (current_step_index == -1)
            if status in ("pending", "running", "failed") or current_idx == -1:
                resumable.append((run_id, run_file, executed_at, status, current_idx))
                print(
                    f"[sweep] Candidate: {run_id} status={status} current_idx={current_idx}"
                )
            else:
                print(
                    f"[sweep] Skipping {run_id} — status={status} current_idx={current_idx}"
                )

    # sort by executed_at for deterministic ordering (fallback to filename if missing)
    def _key(item):
        _, run_file, executed_at, _, _ = item
        if executed_at:
            return executed_at
        return run_file.name

    resumable.sort(key=_key)

    if not resumable:
        print("✔ No resumable runs found.")
        return

    print(f"🔍 Found {len(resumable)} resumable runs:")
    for r, _, executed_at, status, current_idx in resumable:
        print(
            f"   • {r}  (status={status} current_step_index={current_idx} executed_at={executed_at})"
        )

    print("\n▶ Resuming sequentially...\n")

    resumed_count = 0
    for run_id, run_file, _, _, _ in resumable:
        print(f"⏩ resume({run_id})...")
        try:
            # call existing resume_run (keeps same run_id)
            resume_run(run_id)
            resumed_count += 1
        except Exception as e:
            print(f"❌ Failed to resume {run_id}: {e}")
        print("")

    print(
        f"✅ Sweep complete — attempted resume on {resumed_count}/{len(resumable)} runs"
    )


def chain_build_multistep(chain_name: str, steps: List[Dict[str, Any]]):
    """
    Multi-step chain supporting sequential + parallel execution.
    Input format must be:
    [
      { "step_id": "...", "execution_mode": "sequential|parallel", "agents": [...] },
      ...
    ]
    """
    try:
        cname = validate_chain_name(chain_name)
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)

    ensure_registry_dirs()

    if len(steps) > DEFAULT_MAX_STEPS_PER_CHAIN:
        print(f"❌ Too many steps. Max = {DEFAULT_MAX_STEPS_PER_CHAIN}")
        sys.exit(1)

    chains_index = load_chains_index()
    if any(c["chain_name"] == cname for c in chains_index):
        print(f"❌ Chain '{cname}' already exists")
        sys.exit(1)

    agents_index = load_agents_index()
    registry_by_name = {a["agent_name"]: a for a in agents_index}

    # Validate steps + inject metadata
    for step in steps:
        mode = step.get("execution_mode")
        agents = step.get("agents", [])

        if mode == "sequential" and len(agents) != 1:
            print("❌ Sequential step must contain exactly 1 agent")
            sys.exit(1)

        if mode == "parallel" and len(agents) > DEFAULT_MAX_PARALLEL_PER_STEP:
            print(f"❌ Parallel step exceeds limit {DEFAULT_MAX_PARALLEL_PER_STEP}")
            sys.exit(1)

        for ag in agents:
            name = ag["agent_name"]
            if name not in registry_by_name:
                print(f"❌ Unknown agent: {name}")
                sys.exit(1)

            meta = registry_by_name[name]
            ag["path"] = meta["routes"]["by_name"]
            ag["inputs"] = meta.get("inputs", [])
            ag["outputs"] = meta.get("outputs", [])

    # Create chain folder
    chain_id = f"{cname}-{uuid.uuid4().hex[:8]}"
    endpoint = f"/api/v1/chains/{cname}"
    subscription_id = get_or_create_subscription_id()

    cfg = {
        "chain_name": cname,
        "chain_id": chain_id,
        "subscription_id": subscription_id,
        "endpoint": endpoint,
        "method": "POST",
        "steps": steps,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "description": f"Multi-step chain '{cname}'",
    }

    # 🔒 VALIDATION GATE (hard stop)
    try:
        validate_chain_cfg(cfg)
        chain_dir = CHAINS_DIR / chain_id
        chain_dir.mkdir(parents=True, exist_ok=False)
    except Exception as e:
        print(f"\n❌ Failed to build chain '{cname}'")
        print(str(e))
        sys.exit(1)

    (chain_dir / "chain.yaml").write_text(
        yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8"
    )

    chains_index.append(cfg)
    save_chains_index(chains_index)
    # ✅ NEW: Sync to SQLite
    try:
        sync_chains()
        print("✅ Chain synced to database")
        logger.info("✅ Chain synced to database")
    except Exception as e:
        print(f"⚠️  SQLite sync failed: {e}")
        logger.error(f"⚠️  SQLite sync failed: {e}")

    # ✅ NEW: Cache YAML in SQLite (Phase 2)
    try:
        sync_yaml(
            entity_type="chain",
            entity_name=cname,
            entity_id=chain_id,
            yaml_content=yaml.dump(cfg, default_flow_style=False, sort_keys=False),
        )
        logger.info("✅ Chain YAML cached in database")
        print("✅ Chain YAML cached in database")
    except Exception as e:
        logger.error(f"⚠️  Failed to cache YAML: {e}")
        print(f"⚠️  Failed to cache YAML: {e}")

    print(f"✅ Multi-step chain created: {cname} ({chain_id})")
    for s in steps:
        print(f"  → Step {s['step_id']} [{s['execution_mode']}]")


def chain_build_parallel(step_name: str, agent_names: List[str]):
    """
    Build a single-step chain whose only step is parallel.
    Equivalent YAML:
    steps:
      - step_id: <step_name>
        execution_mode: parallel
        agents: [...]
    """
    fail(
        """
Invalid command: build-parallel

Parallel execution is only supported inside multi-step chains.

Use:
  th chain build-steps <chain_name> \
      --step <id> parallel \
          --merge-agent smart_data_aggregator <agents...>
"""
    )
    if len(agent_names) == 0:
        print("❌ Provide at least one agent")
        sys.exit(1)

    if len(agent_names) > DEFAULT_MAX_PARALLEL_PER_STEP:
        print(f"❌ Parallel step exceeds max {DEFAULT_MAX_PARALLEL_PER_STEP}")
        sys.exit(1)

    # Validate chain name
    sname = validate_chain_name(step_name)

    # Ensure agents exist
    agents_index = load_agents_index()
    registry_by_name = {a["agent_name"]: a for a in agents_index}

    agents = []
    for name in agent_names:
        if name not in registry_by_name:
            print(f"❌ Unknown agent: {name}")
            sys.exit(1)

        meta = registry_by_name[name]
        agents.append(
            {
                "agent_name": name,
                "path": meta["routes"]["by_name"],
                "inputs": meta.get("inputs", []),
                "outputs": meta.get("outputs", []),
            }
        )

    step = {
        "step_id": sname,
        "execution_mode": "parallel",
        "agents": agents,
    }

    # Delegate to multi-step builder with only 1 step
    chain_build_multistep(sname, [step])


def fail(message: str) -> NoReturn:
    """
    Hard-stop chain build with a clean, user-facing error.

    This is intentionally NOT an exception type exposed to runtime.
    It is a CLI validation guard.
    """
    print("\n❌ Chain validation failed\n")
    print(message.strip())
    print("\nℹ️ Fix the issue and re-run the build command.\n")
    logger.info("\n❌ Chain validation failed\n")
    logger.info(message.strip())
    logger.info("\nℹ️ Fix the issue and re-run the build command.\n")
    sys.exit(1)


def validate_chain_metadata(cfg: dict):
    required = [
        "chain_name",
        "chain_id",
        "subscription_id",
        "endpoint",
        "method",
    ]

    for key in required:
        if key not in cfg:
            raise ValueError(f"chain.yaml missing required field: '{key}'")


# Chain validations
def validate_chain_cfg(chain_cfg: dict):
    validate_chain_metadata(chain_cfg)

    if "steps" not in chain_cfg:
        raise ValueError("chain.yaml must contain a 'steps' list")
    validate_limits(chain_cfg)
    validate_step_structure(chain_cfg)
    validate_agent_existence(chain_cfg)
    validate_input_resolution(chain_cfg)
    validate_merge_rules(chain_cfg)
    validate_routing_rules(chain_cfg)


def validate_limits(cfg):
    max_steps = cfg.get("max_steps", DEFAULT_MAX_STEPS_PER_CHAIN)
    max_parallel = cfg.get("max_parallel", DEFAULT_MAX_PARALLEL_PER_STEP)

    steps = cfg["steps"]
    if len(steps) > max_steps:
        fail(f"Chain has {len(steps)} steps. Max allowed is {max_steps}")

    for step in steps:
        if step["execution_mode"] == "parallel":
            if len(step["agents"]) > max_parallel:
                fail(
                    f"Step '{step['step_id']}' has {len(step['agents'])} agents. "
                    f"Max allowed is {max_parallel}"
                )


def validate_step_structure(cfg):
    for step in cfg["steps"]:
        if step["execution_mode"] not in ("sequential", "parallel"):
            fail(f"Invalid execution_mode in step '{step['step_id']}'")

        if step["execution_mode"] == "sequential" and len(step["agents"]) != 1:
            fail(f"Sequential step '{step['step_id']}' must have exactly one agent")


def validate_agent_existence(cfg):
    for step in cfg["steps"]:
        for agent in step["agents"]:
            name = agent["agent_name"]

            if name in BUILTIN_AGENTS:
                fail(
                    f"""
Invalid agent: {name}

'{name}' is a builtin runtime capability and must NOT be listed as an agent.

How it works:
• Language detection is applied automatically during merge
• Access via output.language / output.confidence
"""
                )

            if not agent_exists(name):
                fail(f"Agent '{name}' does not exist")


def validate_input_resolution(cfg):
    available_outputs: set[str] = set()

    steps = cfg["steps"]

    for idx, step in enumerate(steps):
        step_outputs = set()

        for agent in step["agents"]:
            spec = load_agent_spec(agent["agent_name"])

            for inp in spec["inputs"]:
                if inp.get("required", True) is False:
                    continue
                name = inp["name"]
                source = inp.get("source")
                logger.info(f"Source - {source}")

                # ✅ FIRST STEP: allow request inputs
                if idx == 0:
                    # Only allow request-bound inputs
                    if inp.get("source") == "request":
                        continue

                    # Implicit request input is allowed ONLY if explicitly declared
                    if inp.get("source") is None:
                        continue
                    fail(
                        f"""
Unresolved input detected

Step: {step['step_id']}
Agent: {agent['agent_name']}
Missing input: {name}

Why this happened:
• First step inputs must come from request
• This input is neither request-bound nor produced earlier

Suggested fix:
Add source: request
"""
                    )

                if not is_input_resolvable(inp, agent, available_outputs):
                    fail(
                        f"""
Unresolved input detected

Step: {step['step_id']}
Agent: {agent['agent_name']}
Missing input: {name}

Why this happened:
• This step does not receive data from previous steps
• Parallel steps cannot read sibling outputs
• Input not found in request payload

Suggested fix:
Add a producer step before '{step['step_id']}'
"""
                    )

            # Register outputs AFTER validation
            for out in spec["outputs"]:
                step_outputs.add(out["name"])

        available_outputs |= step_outputs


def validate_merge_rules(cfg):
    for step in cfg["steps"]:
        merge = step.get("merge_agent")

        if step["execution_mode"] == "parallel":
            if not merge:
                fail(
                    f"""
Missing merge-agent

Step '{step['step_id']}' is parallel but has no merge-agent.

Why this matters:
• Parallel steps produce multiple outputs
• Downstream steps require a single merged output
• Routing requires a deterministic 'output'

Suggested fix:
Add --merge-agent smart_data_aggregator
"""
                )

            if merge not in BUILTIN_MERGE_AGENTS:
                fail(
                    f"""
Unknown merge-agent: {merge}

Allowed merge-agents:
• {", ".join(BUILTIN_MERGE_AGENTS.keys())}
"""
                )

        if merge and step["execution_mode"] != "parallel":
            fail(
                f"""
Invalid merge-agent usage

merge-agent is only allowed on parallel steps
(step '{step['step_id']}')
"""
            )


def validate_routing_rules(cfg):
    step_ids = {s["step_id"] for s in cfg["steps"]}

    for step in cfg["steps"]:
        for rule in step.get("route_on", []):
            if rule["goto"] not in step_ids:
                fail(
                    f"Routing target '{rule['goto']}' does not exist "
                    f"(from step '{step['step_id']}')"
                )


def chain_entry(argv: List[str]) -> None:
    # logger.info("[treehopper_chains] Initialising the DB if not exists")
    # dbInit = DBInitializer()
    # dbInit.init_db()
    logger.info("[treehopper_chains] Initialising TreehopperAI setup")
    print("[treehopper_chains] Initialising TreehopperAI setup")
    setup_treehopper()

    if not os.getenv("TH_TEST_MODE"):
        logger.info("[treehopper_chains] Ensuring all directories exists")
        ensure_dirs()
        print("[treehopper_chains] Ensuring maintaince checks and actions")
        logger.info("[treehopper_chains] Ensuring maintaince checks and actions")
        startup_maintenance()

    if not argv:
        print_chain_help()
        sys.exit(1)

    sub = argv[0].lower()

    if sub in {
        "vu",
        "view",
        "build",
        "start",
        "run",
        "stop",
        "delete",
        "logs",
        "help",
        "cancel",
        "cancel-batch",
        "resume",
        "sweep-resume",
        "build-parallel",
        "build-steps",
    }:

        if sub == "help":
            print_chain_help()
            return

        if sub == "build":
            if len(argv) < 3:
                print("Usage: treehopper chain build <name> <agent1> <agent2> ...")
                sys.exit(1)
            name = argv[1]
            agents = argv[2:]
            chain_build(name, agents)
            return

        if sub == "build-parallel":
            if len(argv) < 3:
                print(
                    "Usage: treehopper chain build-parallel <step_name> <agent1> <agent2> ..."
                )
                sys.exit(1)

            step_name = argv[1]
            agents = argv[2:]
            chain_build_parallel(step_name, agents)
            return

        if sub == "build-steps":
            """
            Example:
            th chain build-steps doc_intel \
            --step extract sequential pdf_extractor \
            --step analyze parallel content_analyzer keyword_extractor \
            --step report sequential report_generator
            """

            if len(argv) < 3:
                print(
                    "Usage: th chain build-steps <chain_name> --step <id> <mode> <agents...>"
                )
                sys.exit(1)

            chain_name = argv[1]
            args = argv[2:]

            steps = []
            i = 0
            while i < len(args):
                if args[i] != "--step":
                    print(f"❌ Unexpected token: {args[i]}")
                    sys.exit(1)

                if i + 3 >= len(args):
                    print("❌ Invalid --step format")
                    sys.exit(1)

                step_id = args[i + 1]
                mode = args[i + 2]
                step_agents: List[Dict[str, Any]] = []

                j = i + 3
                merge_agent = None
                route_on = None
                while j < len(args) and args[j] != "--step":
                    if args[j] == "--merge-agent":
                        if j + 1 >= len(args):
                            fail("--merge-agent requires an agent name")
                        merge_agent = args[j + 1]
                        j += 2
                        continue

                    if args[j] == "--route-on":
                        if j + 1 >= len(args):
                            fail("--route-on requires a JSON value")
                        try:
                            route_on = json.loads(args[j + 1])
                        except Exception:
                            fail("Invalid JSON passed to --route-on")
                        j += 2
                        continue

                    step_agents.append({"agent_name": args[j]})
                    j += 1

                # --- Step Configuration Assembly ---
                current_step_config = {
                    "step_id": step_id,
                    "execution_mode": mode,
                    "agents": step_agents,
                }

                if merge_agent:
                    current_step_config["merge_agent"] = merge_agent

                if route_on:
                    current_step_config["route_on"] = route_on

                steps.append(current_step_config)
                i = j

            chain_build_multistep(chain_name, steps)
            return

        if sub == "start":
            ref = argv[1]
            chain_ref = resolve_chain(ref)
            parsed = parse_payload_args(argv[2:])
            extra_args = parsed["args"]
            # 3) detect --port <value>
            port_override = None
            if "--bg" not in extra_args:
                print("❌ Missing --bg")
                print("Usage - treehopper chain start <chain_name> --bg [--port]")
                sys.exit(1)
            if "--port" in extra_args:
                idx = extra_args.index("--port")
                if idx + 1 >= len(extra_args):
                    print("❌ Missing value for --port")
                    sys.exit(1)
                try:
                    port_override = int(extra_args[idx + 1])
                except ValueError:
                    print("❌ Invalid value for --port (must be integer)")
                    sys.exit(1)
                del extra_args[idx : idx + 2]
            chain_start(chain_ref, port_override=port_override)

        if sub == "run":
            if len(argv) < 2:
                print(
                    "Usage: treehopper chain run <name|id> [--payload ...] [--detached] [--port X] [--bg]"
                )
                sys.exit(1)

            ref = argv[1]
            parsed = parse_payload_args(argv[2:])
            extra_args = parsed["args"]
            payload = parsed["payload"]
            # 1) detect detached
            detached = "--detached" in extra_args
            extra_args = [a for a in extra_args if a != "--detached"]

            # 2) detect bg (run-only)
            bg = "--bg" in extra_args
            print(f"Background flag - {bg}")
            extra_args = [a for a in extra_args if a != "--bg"]

            # 3) detect --port <value>
            port_override = None
            if "--port" in extra_args:
                idx = extra_args.index("--port")
                if idx + 1 >= len(extra_args):
                    print("❌ Missing value for --port")
                    sys.exit(1)
                try:
                    port_override = int(extra_args[idx + 1])
                except ValueError:
                    print("❌ Invalid value for --port (must be integer)")
                    sys.exit(1)
                del extra_args[idx : idx + 2]

            # ----------------------------------------
            # NEW: Parallel execution flags
            # ----------------------------------------
            parallel = 1
            concurrency = None

            # --parallel N
            if "--parallel" in extra_args:
                idx = extra_args.index("--parallel")
                try:
                    parallel = int(extra_args[idx + 1])
                except Exception:
                    print("❌ Invalid value for --parallel")
                    sys.exit(1)
                # remove flags from extra args
                del extra_args[idx : idx + 2]

            # --concurrency M
            if "--concurrency" in extra_args:
                idx = extra_args.index("--concurrency")
                try:
                    concurrency = int(extra_args[idx + 1])
                except Exception:
                    print("❌ Invalid value for --concurrency")
                    sys.exit(1)
                del extra_args[idx : idx + 2]

            # default concurrency
            if concurrency is None:
                concurrency = parallel

            # ----------------------------------------
            # NEW: Parallel Execution Entry
            # ----------------------------------------
            if parallel > 1:
                print(
                    f"🌿 Parallel execution: {parallel} runs  | concurrency={concurrency} | detached={detached}"
                )
                # broadcast payload
                payloads = [payload] * parallel

                parallel_chain_run_entry(ref, payloads, parallel, concurrency, detached)
                return

            # 4) unrecognized args check
            if extra_args:
                print(f"⚠️ Ignoring unrecognized args: {extra_args}")

            chain_ref = resolve_chain(ref)

            if detached:
                chain_run_detached(
                    chain_ref,
                    payload,
                    port_override=port_override,
                    # run_once=not bg,
                )
            else:
                chain_run_local(chain_ref, payload)
            return

        if sub == "stop":
            if len(argv) != 2:
                print("Usage: treehopper chain stop <name|id>")
                sys.exit(1)
            chain_stop(argv[1])
            return

        if sub == "delete":
            if len(argv) < 2:
                print("Usage: treehopper chain delete <name|id> [<name|id>...]")
                sys.exit(1)
            # Pass all arguments after 'delete' as a list to the new chain_delete function
            chain_delete(argv[1:])
            return

        if sub == "logs":
            if len(argv) != 2:
                print("Usage: treehopper chain logs <name|id>")
                sys.exit(1)
            chain_logs(argv[1])
            return

        if sub == "cancel":
            # Unified CLI syntax:
            #   treehopper chain cancel --run <run_id>
            #   treehopper chain cancel --batch <batch_id>
            #   treehopper chain cancel --all <chain_name_or_id>

            if "--run" in argv:
                idx = argv.index("--run")
                if idx + 1 >= len(argv):
                    print("❌ Missing value for --run")
                    sys.exit(1)
                run_id = argv[idx + 1]
                print(f"[chains] CANCEL REQUEST for run_id={run_id}")
                from treehopper.treehopper_cancellation import create_cancel_marker
                from treehopper.utils.config import read_pid_and_port

                # import requests

                # 1 — Create FS cancel marker (source=cli, modifier includes CLI PID)
                marker = create_cancel_marker(
                    run_id, source="cli", modifier=f"cli:{os.getpid()}"
                )
                print(f"[cancel] wrote FS cancel marker → {marker}")

                # 2 — Notify runtimes (best-effort)
                chain_prefix = run_id.rsplit("-", 1)[0]  # cancel_test_chain
                pattern = f"{CHAIN_PID_PREFIX}{chain_prefix}-*.pid"
                for pid_file in RUNTIME_DIR.glob(pattern):
                    pid, port = read_pid_and_port(pid_file)
                    if port:
                        url = f"http://127.0.0.1:{port}/api/v1/cancel/run/{run_id}"
                        print(f"[notify] POST → {url}")
                        try:
                            # small timeout; we don't want CLI to block long
                            _post_runtime_detached(
                                url, payload={}, headers={"x-api-key": "demo-key-123"}
                            )
                        except Exception:
                            pass
                print("✅ Cancel requested (global cancel marker)")
                return

            if "--batch" in argv:
                idx = argv.index("--batch")
                if idx + 1 >= len(argv):
                    print("❌ Missing value for --batch")
                    sys.exit(1)
                batch_id = argv[idx + 1]
                n = asyncio.run(cancel_batch(batch_id))
                print(f"✅ Cancelled {n} run(s) in batch {batch_id}")
                return

            if "--all" in argv:
                idx = argv.index("--all")
                if idx + 1 >= len(argv):
                    print("❌ Missing chain name/id for --all")
                    sys.exit(1)
                ref = argv[idx + 1]
                chain_ref = resolve_chain(ref)
                n = asyncio.run(cancel_chain_id(chain_ref.chain_id))
                print(f"✅ Cancelled {n} run(s) for chain {chain_ref.chain_name}")
                return

            print(
                "❌ Usage:\n"
                "  treehopper chain cancel --run <run_id>\n"
                "  treehopper chain cancel --batch <batch_id>\n"
                "  treehopper chain cancel --all <chain>"
            )
            sys.exit(1)

        if sub == "cancel-batch":
            # Usage: treehopper chain cancel-batch <batch_id>
            if len(argv) != 2:
                print("Usage: treehopper chain cancel-batch <batch_id>")
                sys.exit(1)
            batch_id = argv[1]
            n = asyncio.run(cancel_batch(batch_id))
            print(f"✅ Cancelled {n} run(s) in batch {batch_id}")
            return

        if sub == "resume":
            if len(argv) != 2:
                print("Usage: treehopper chain resume <run_id>")
                sys.exit(1)
            run_id = argv[1]
            resume_run(run_id)
            return

        if sub == "sweep-resume":
            """
            treehopper chain sweep-resume

            Scan ALL run files under ~/.treehopper/registry/chains/*/runs/*.json
            Resume only runs where:
                status in {"pending", "running", "failed"}
                AND cancelled == False
            Skips:
                completed, cancelled
            """
            chain_sweep_resume()
            return

        if sub in ("vu", "view"):
            if len(argv) < 2:
                print("Usage: treehopper chain vu <chain_name> [--raw] [--json]")
                sys.exit(1)

            chain_name = argv[1]
            show_raw = "--raw" in argv
            show_json = "--json" in argv
            chain_flow_viewer(chain_name, raw_yaml=show_raw, raw_json=show_json)
            return

    # fall back → legacy mode
    simple_chain_run(argv)
