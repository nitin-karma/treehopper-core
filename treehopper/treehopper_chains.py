import json
import os
import re
import signal
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
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
from treehopper.treehopper_cli import get_or_create_subscription_id
from treehopper.treehopper_parallel import parallel_chain_run_entry
from treehopper.utils import run_registry as run_registry_mod
from treehopper.utils.config import read_pid_and_port

from treehopper.th_config import (
    API_KEY,
    MAIN_PORT,
    BASE_URL,
    # HOME,
    TH_ROOT,
    REGISTRY_DIR,
    # REGISTRY_AGENTS,
    REGISTRY_AGENTS_INDEX,
    CHAINS_DIR,
    CHAINS_INDEX,
    RUNTIME_DIR,
    CHAIN_PID_PREFIX,
    CANCEL_DIR,
)


# -----------------------------------------------------------------------------
# MODELS / HELPERS
# -----------------------------------------------------------------------------


@dataclass
class ChainRef:
    chain_name: str
    chain_id: str
    cfg_path: Path
    dir_path: Path


def ensure_registry_dirs() -> None:
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    CHAINS_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def load_chains_index() -> List[Dict[str, Any]]:
    ensure_registry_dirs()
    if not CHAINS_INDEX.exists():
        return []
    try:
        return json.loads(CHAINS_INDEX.read_text())
    except json.JSONDecodeError:
        return []


def save_chains_index(index: List[Dict[str, Any]]) -> None:
    ensure_registry_dirs()
    CHAINS_INDEX.write_text(json.dumps(index, indent=2))


def load_agents_index() -> List[Dict[str, Any]]:
    ensure_registry_dirs()
    if not REGISTRY_AGENTS_INDEX.exists():
        return []
    try:
        return json.loads(REGISTRY_AGENTS_INDEX.read_text())
    except json.JSONDecodeError:
        return []


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex(("127.0.0.1", port)) == 0


def validate_chain_name(name: str) -> str:
    """
    Same rules as agent names:
      - strip whitespace
      - no spaces inside
      - 4–25 chars
      - start with a letter
      - letters / numbers / underscore only
    """
    clean = name.strip()
    if " " in clean:
        raise ValueError("Chain name cannot contain spaces")

    if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]{3,24}$", clean):
        raise ValueError(
            "Invalid chain name. Must:\n"
            " • start with a letter\n"
            " • be 4–25 chars\n"
            " • contain only letters, numbers, underscore"
        )
    return clean.lower()


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


def ensure_main_server() -> None:
    """
    Simple health check + lazy start for the MAIN server on MAIN_PORT.
    """
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

    chains_index.append(
        {"chain_name": cname, "chain_id": chain_id, "subscription_id": subscription_id}
    )
    save_chains_index(chains_index)

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


def chain_run_local(chain_ref: ChainRef, payload: Dict[str, Any]) -> None:
    """
    Execute the chain via the main Treehopper server's
    /api/v1/chains/{name} endpoint.
    """
    # detached = False
    ensure_main_server()
    cfg = load_chain_cfg(chain_ref)
    endpoint = cfg.get("endpoint") or f"/api/v1/chains/{chain_ref.chain_name}"

    url = f"{BASE_URL}{endpoint}"

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
    run_once: bool = True,
) -> None:

    ensure_main_server()

    cfg = load_chain_cfg(chain_ref)
    print(f"chain config : {cfg}")

    pid_file = RUNTIME_DIR / f"{CHAIN_PID_PREFIX}{chain_ref.chain_id}.pid"

    # Prefer existing runtime port if available
    existing_pid, existing_port = read_pid_and_port(pid_file)
    if existing_pid and existing_port:
        actual_port = existing_port
    else:
        actual_port = port_override or derive_chain_port(chain_ref.chain_id)

    # ----------------------------------------------------------------------
    # ALWAYS GENERATE RUN_ID HERE — SINGLE SOURCE OF TRUTH
    # ----------------------------------------------------------------------
    run_id = run_registry_mod.make_run_id(chain_ref.chain_name)
    batch_id = None  # batch mode not used in direct detached run

    # ----------------------------------------------------------------------
    # Early checkpoint (pending)
    # ----------------------------------------------------------------------
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

    # ----------------------------------------------------------------------
    # START RUNTIME IF NOT ALIVE
    # ----------------------------------------------------------------------
    existing_pid, existing_port = read_pid_and_port(pid_file)
    if existing_pid:
        try:
            os.kill(existing_pid, 0)
            actual_port = existing_port or actual_port
        except OSError:
            print("Process is not alive")
            existing_pid = None

    if not existing_pid:
        LOG_FILE = (
            RUNTIME_DIR / f"chain_{chain_ref.chain_name}-{chain_ref.chain_id}.log"
        )

        # ======================================================================
        # 🔥 CRITICAL PATCH — Inject absolute, unified FS paths into runtime
        # ======================================================================
        env = os.environ.copy()
        env["CHAIN_NAME"] = chain_ref.chain_name
        env["CHAIN_ID"] = chain_ref.chain_id
        env["CHAIN_DIR"] = str(chain_ref.dir_path)
        # 🔥 ADD THESE LINES:
        # from treehopper.treehopper_cancellation import DB_PATH
        # env["TREEHOPPER_DB_PATH"] = str(DB_PATH.resolve())  # ← Force same DB

        env["PROD"] = "1"

        # Absolute paths — the FIX for cancellation detection
        env["TREEHOPPER_TH_ROOT"] = str(TH_ROOT.resolve())
        env["TREEHOPPER_RUNTIME_DIR"] = str(RUNTIME_DIR.resolve())
        env["TREEHOPPER_CANCEL_DIR"] = str(CANCEL_DIR.resolve())

        # Uvicorn & Python safety
        env["PYTHONUNBUFFERED"] = "1"  # real-time logs
        env["UVICORN_WORKERS"] = "1"  # avoid forked workers (breaks FS sync)

        # ----------------------------------------------------------------------
        # DEV: inject local source into PYTHONPATH for subprocesses (guarded)
        # ----------------------------------------------------------------------
        # This is opt-in: set TREEHOPPER_DEV_MODE=1 in your shell / CI env to enable.
        try:
            # mark dev-mode for the child process (only when you explicitly opt in)
            if os.getenv("TREEHOPPER_DEV_MODE") == "1":
                env["TREEHOPPER_DEV_MODE"] = "1"
            # import helper if present
            from treehopper.environment import inject_pythonpath

            # only run injection when dev flag present in environment or parent process
            if env.get("TREEHOPPER_DEV_MODE") == "1":
                inject_pythonpath(env)
        except Exception:
            # Don't break if the helper isn't available — fallback to default behavior.
            pass
        # ----------------------------------------------------------------------

        # ======================================================================
        # Launch chain runtime
        # ======================================================================
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

        # Wait for runtime health
        for _ in range(40):
            try:
                r = requests.get(
                    f"http://localhost:{actual_port}/api/v1/{chain_ref.chain_name}/health"
                )
                if r.status_code == 200:
                    break
            except requests.RequestException:
                pass
            time.sleep(0.25)

    # ----------------------------------------------------------------------
    # POST request to runtime with forwarded run_id
    # ----------------------------------------------------------------------
    url = f"http://localhost:{actual_port}/api/v1/{chain_ref.chain_name}/run"

    headers = {
        "x-api-key": "demo-key-123",
        "X-Treehopper-Run-Id": run_id,
    }
    if batch_id:
        headers["X-Treehopper-Batch-Id"] = batch_id

    # ----------------------------------------------------------------------
    # 🔥 Minimal Patch:
    #   Fire-and-forget JSON POST using curl in a background subprocess.
    #   CLI returns immediately, chain runtime logs progress independently.
    #   No blocking → cancellation polling becomes correct.
    # ----------------------------------------------------------------------
    _post_runtime_detached(
        url=url, payload=payload or {}, headers=headers  # ← dict, NOT json.dumps
    )

    print(f"🚀 Detached chain triggered → run_id={run_id}")
    print(f"📡 Runtime executing independently at http://localhost:{actual_port}")
    print(f"📁 Track status via JSON at: {chain_ref.dir_path}/runs/{run_id}.json")

    print(f"RUN_ID: {run_id}")

    if run_once:
        pid = read_pid(pid_file)
        if pid:
            kill_pid(pid)
            pid_file.unlink(missing_ok=True)


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


def chain_delete(ref: str) -> None:
    ensure_registry_dirs()
    chain_ref = resolve_chain(ref)

    # Confirm deletion
    confirm = input(
        f"⚠️ Delete chain '{chain_ref.chain_name}' ({chain_ref.chain_id}) permanently? y/N: "
    )
    if confirm.lower() not in ("y", "yes"):
        print("❎ Cancelled")
        return

    pid_file = RUNTIME_DIR / f"{CHAIN_PID_PREFIX}{chain_ref.chain_id}.pid"
    pid = read_pid(pid_file)

    print(
        f"[chains] DELETE requested for chain={chain_ref.chain_name} id={chain_ref.chain_id}"
    )
    print(f"[chains] run directory = {chain_ref.dir_path}")

    # Stop runtime if alive
    if pid:
        print(f"🛑 Stopping chain runtime PID {pid} before delete...")
        kill_pid(pid)
        pid_file.unlink(missing_ok=True)

    # Remove directory recursively
    if chain_ref.dir_path.exists():
        import shutil

        shutil.rmtree(chain_ref.dir_path)
        print("🗑 Chain directory removed")

    # Remove chain entry from index
    index = load_chains_index()
    index = [c for c in index if c["chain_id"] != chain_ref.chain_id]
    save_chains_index(index)
    print("📦 Chain removed from registry index")

    # Clean up stray cancel markers
    for cancel_file in CANCEL_DIR.glob(f"{chain_ref.chain_name}-*.cancel"):
        cancel_file.unlink(missing_ok=True)

    print(f"✔ Deleted chain '{chain_ref.chain_name}' ({chain_ref.chain_id})")


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
      [--detached] [--bg]
      [--parallel N] [--concurrency M]
      Execute a chain sequentially.
      First agent gets payload; later agents receive mapped fields.

      --detached
           Launch a dedicated chain micro-app (async, cancellable, resumable).

      --bg
           Run the detached micro-app in background.

      --parallel N
           Run N independent chain executions in parallel (N run_ids).

      --concurrency M
           Max number of parallel runs at a time.

Cancellation Support Matrix
───────────────────────────────────────────────────────────────────────────────
| Execution Mode                          | Cancellable? | Reason                          |
|-----------------------------------------|--------------|---------------------------------|
| chain run --detached                    |     YES      | async micro-app runtime         |
| chain run --detached --bg               |     YES      | async runtime with background   |
| chain run (non-detached)                |     NO       | blocking HTTP request           |
| chain run --parallel N                  |     NO       | each run is blocking            |
| chain run --parallel N --detached       |     NO       | still blocking main-thread POST |

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


def chain_entry(argv: List[str]) -> None:
    if not argv:
        print_chain_help()
        sys.exit(1)

    sub = argv[0].lower()

    if sub in {
        "build",
        "run",
        "stop",
        "delete",
        "logs",
        "help",
        "cancel",
        "cancel-batch",
        "resume",
        "sweep-resume",
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
                    run_once=not bg,
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
            if len(argv) != 2:
                print("Usage: treehopper chain delete <name|id>")
                sys.exit(1)
            chain_delete(argv[1])
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

    # fall back → legacy mode
    simple_chain_run(argv)
