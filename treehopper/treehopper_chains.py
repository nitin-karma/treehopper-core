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

import requests
import yaml

from treehopper.utils.shared_files import (
    has_only_one_shared_file,
    get_the_only_shared_file,
)
from treehopper.treehopper_cli import get_or_create_subscription_id


# -----------------------------------------------------------------------------
# CONSTANTS & PATHS
# -----------------------------------------------------------------------------

API_KEY = {"x-api-key": "demo-key-123"}
MAIN_PORT = int(os.getenv("TH_PORT", 1560))
BASE_URL = f"http://localhost:{MAIN_PORT}"

HOME = Path.home()
TH_ROOT = HOME / ".treehopper"
REGISTRY_DIR = TH_ROOT / "registry"
REGISTRY_AGENTS = REGISTRY_DIR / "agents"
REGISTRY_AGENTS_INDEX = REGISTRY_DIR / "agents.json"

CHAINS_DIR = REGISTRY_DIR / "chains"
CHAINS_INDEX = REGISTRY_DIR / "chains.json"

RUNTIME_DIR = TH_ROOT / "runtime"
CHAIN_PID_PREFIX = "det_chain_"


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


def derive_chain_port(chain_id: str) -> int:
    """
    Predictable hash-based port:
      20000–24999 range based on chain_id.
    """
    h = abs(hash(chain_id))
    return 20000 + (h % 5000)


def read_pid(path: Path) -> Optional[int]:
    if not path.exists():
        return None
    try:
        return int(path.read_text().strip())
    except Exception:
        return None


def write_pid(path: Path, pid: int) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
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


def chain_run_detached(chain_ref: ChainRef, payload: Dict[str, Any]) -> None:
    """
    Start a dedicated uvicorn *chain micro-app* for this chain on a predictable port,
    then execute the chain once via its /api/v1/chain/run endpoint.

    The micro-app is treehopper.chain_runtime_app:app
    and is stateless: each call must send {agents, payload}.
    """
    detached = True
    cfg = load_chain_cfg(chain_ref)
    port = derive_chain_port(chain_ref.chain_id)
    chain_url = f"http://localhost:{port}"
    pid_file = RUNTIME_DIR / f"{CHAIN_PID_PREFIX}{chain_ref.chain_id}.pid"

    # If already running, reuse it
    existing_pid = read_pid(pid_file)
    if existing_pid:
        try:
            os.kill(existing_pid, 0)
            print(
                f"ℹ️ Chain runtime already running for '{chain_ref.chain_name}' "
                f"(PID {existing_pid}) on {chain_url}"
            )
        except ProcessLookupError:
            pid_file.unlink(missing_ok=True)
            existing_pid = None

    if not existing_pid:
        print(
            f"🚀 Starting dedicated chain runtime for '{chain_ref.chain_name}' on {chain_url}"
        )
        env = os.environ.copy()
        env["PROD"] = "1"
        # ▶ NOTE: use the *chain micro-app* here, not the full Treehopper app
        proc = subprocess.Popen(
            [
                "uvicorn",
                "treehopper.chain_runtime_app:app",
                "--host",
                "0.0.0.0",
                "--port",
                str(port),
            ],
            env=env,
        )
        write_pid(pid_file, proc.pid)

        # wait for /health
        for _ in range(40):
            time.sleep(0.25)
            try:
                r = requests.get(
                    f"{chain_url}/api/v1/{chain_ref.chain_name}/health", timeout=0.25
                )
                if r.status_code == 200:
                    print("✅ Chain micro-app runtime healthy")
                    break
            except Exception:
                continue
        else:
            print("⚠️ Chain micro-app did not report healthy; continuing anyway.")

    # Prepare request body for micro-app
    agents_spec = cfg.get("agents", [])
    body = {"agents": agents_spec, "payload": payload or {}}

    url = f"{chain_url}/api/v1/{chain_ref.chain_name}/run"
    print(f"▶ Executing chain via {url}")
    r = requests.post(url, json=body, headers=API_KEY)

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

    # For detached micro-app: CLI writes last_run.json itself
    history_path = chain_ref.dir_path / "last_run.json"
    history = {
        "chain_name": cfg.get("chain_name"),
        "chain_id": cfg.get("chain_id"),
        "executed_at": datetime.utcnow().isoformat() + "Z",
        "input": payload or {},
        "results": results,
        "detached": detached,
    }
    history_path.write_text(json.dumps(history, indent=2), encoding="utf-8")

    print("\n🔍 Full response stored at:")
    print(f"  {history_path}")
    print(f"🌐 Chain micro-app runtime still available at: {chain_url}")


# def chain_run_detached(chain_ref: ChainRef, payload: Dict[str, Any]) -> None:
#     """
#     Start a dedicated uvicorn runtime for this chain on a predictable port,
#     then execute the chain once via its /api/v1/chains/{name} endpoint.
#     """
#     cfg = load_chain_cfg(chain_ref)
#     port = derive_chain_port(chain_ref.chain_id)
#     chain_url = f"http://localhost:{port}"
#     pid_file = RUNTIME_DIR / f"{CHAIN_PID_PREFIX}{chain_ref.chain_id}.pid"

#     # If already running, reuse
#     existing_pid = read_pid(pid_file)
#     if existing_pid:
#         try:
#             os.kill(existing_pid, 0)
#             print(
#                 f"ℹ️ Chain runtime already running for '{chain_ref.chain_name}' "
#                 f"(PID {existing_pid}) on {chain_url}"
#             )
#         except ProcessLookupError:
#             pid_file.unlink(missing_ok=True)
#             existing_pid = None

#     if not existing_pid:
#         print(
#             f"🚀 Starting dedicated chain runtime for '{chain_ref.chain_name}' on {chain_url}"
#         )
#         env = os.environ.copy()
#         env["PROD"] = "1"
#         proc = subprocess.Popen(
#             [
#                 "uvicorn",
#                 "treehopper.treehopper:app",
#                 "--host",
#                 "0.0.0.0",
#                 "--port",
#                 str(port),
#             ],
#             env=env,
#         )
#         write_pid(pid_file, proc.pid)

#         # wait for /health
#         for _ in range(40):
#             time.sleep(0.25)
#             try:
#                 r = requests.get(f"{chain_url}/api/v1/sys/health", timeout=0.25)
#                 if r.status_code == 200:
#                     print("✅ Chain runtime healthy")
#                     break
#             except Exception:
#                 continue
#         else:
#             print("⚠️ Chain runtime did not report healthy; continuing anyway.")

#     endpoint = cfg.get("endpoint") or f"/api/v1/chains/{chain_ref.chain_name}"
#     url = f"{chain_url}{endpoint}"

#     # ⬇ INSERT PATCH HERE
#     first_agent = cfg.get("agents", [])[0] if cfg.get("agents") else None
#     if first_agent:
#         first_agent_id = first_agent.get("agent_id", "")
#         if payload == {} and has_only_one_shared_file(first_agent_id):
#             auto_path = get_the_only_shared_file(first_agent_id)
#             print(f"🔌 Auto-injecting payload: file_path='{auto_path}'")
#             payload = {"file_path": auto_path}
#     # ⬆ PATCH END

#     print(f"▶ Executing chain via {url}")
#     r = requests.post(url, json=payload or {}, headers=API_KEY)

#     try:
#         data = r.json()
#     except Exception:
#         print(f"HTTP {r.status_code}")
#         print(r.text)
#         return

#     results = data.get("results", [])
#     agents = cfg.get("agents", [])

#     print("📊 Chain step results:")
#     for i, res in enumerate(results):
#         name = agents[i]["agent_name"] if i < len(agents) else f"step_{i}"
#         status = "✓ success"
#         if isinstance(res, dict) and "error" in res:
#             status = f"✗ error: {res['error']}"
#         print(f"  [{name}] {status}")

#     history_path = chain_ref.dir_path / "last_run.json"
#     if history_path.exists():
#         print("\n🔍 Full response stored at:")
#         print(f"  {history_path}")
#     else:
#         print("\nℹ️ No last_run.json written by server (check Treehopper logs).")

#     print(f"🌐 Chain runtime still available at: {chain_url}")


# -----------------------------------------------------------------------------
# CHAIN STOP / DELETE / LOGS
# -----------------------------------------------------------------------------


def chain_stop(ref: str) -> None:
    ensure_registry_dirs()
    chain_ref = resolve_chain(ref)
    pid_file = RUNTIME_DIR / f"{CHAIN_PID_PREFIX}{chain_ref.chain_id}.pid"
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

    confirm = input(
        f"⚠️ Delete chain '{chain_ref.chain_name}' ({chain_ref.chain_id}) permanently? y/N: "
    )
    if confirm.lower() not in ("y", "yes"):
        print("❎ Cancelled")
        return

    # stop runtime if any
    pid_file = RUNTIME_DIR / f"{CHAIN_PID_PREFIX}{chain_ref.chain_id}.pid"
    pid = read_pid(pid_file)
    if pid:
        print(f"🛑 Stopping chain runtime PID {pid} before delete...")
        kill_pid(pid)
        pid_file.unlink(missing_ok=True)

    # remove directory
    if chain_ref.dir_path.exists():
        for p in chain_ref.dir_path.rglob("*"):
            if p.is_file():
                p.unlink()
        chain_ref.dir_path.rmdir()

    # remove from index
    index = load_chains_index()
    index = [c for c in index if c["chain_id"] != chain_ref.chain_id]
    save_chains_index(index)

    print(f"🗑 Deleted chain '{chain_ref.chain_name}' ({chain_ref.chain_id})")


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
────────────────────────────────────────────
  treehopper chain build <name> <agent1> <agent2> ...
      Register a named chain using registered agents.
      Creates ~/.treehopper/registry/chains/<id>/chain.yaml
      and a POST endpoint /api/v1/chains/<name>.

  treehopper chain run <name|id> [--payload '{...}'] [--payload-file path] [--detached]
      Execute a named chain via /api/v1/chains/{name}.
      Payload (if provided) is passed only to the first agent.

  treehopper chain stop <name|id>
      Stop a dedicated chain runtime if running.

  treehopper chain delete <name|id>
      Delete chain metadata and last run logs.

  treehopper chain logs <name|id>
      Show last execution summary + JSON.

Legacy:
  treehopper chain <agent_path1> <agent_path2> ...
      Direct call to /api/v1/dev/chain with static agent paths.
"""
    )


def chain_entry(argv: List[str]) -> None:
    if not argv:
        print_chain_help()
        sys.exit(1)

    sub = argv[0]

    # new subcommand mode
    if sub in {"build", "run", "stop", "delete", "logs", "help"}:
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
                print("Usage: treehopper chain run <name|id> [--payload ...]")
                sys.exit(1)

            ref = argv[1]
            parsed = parse_payload_args(argv[2:])
            extra_args = parsed["args"]
            payload = parsed["payload"]

            detached = False
            if "--detached" in extra_args:
                detached = True
                extra_args = [a for a in extra_args if a != "--detached"]

            if extra_args:
                print(f"⚠️ Ignoring unrecognized args: {extra_args}")

            chain_ref = resolve_chain(ref)
            if detached:
                chain_run_detached(chain_ref, payload)
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

    # legacy mode: treat all args as agent paths
    simple_chain_run(argv)
