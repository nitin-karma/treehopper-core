import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
import ast

import requests
import uvicorn
import yaml
from dotenv import load_dotenv
from tabulate import tabulate

import signal

load_dotenv()

API_KEY = {"x-api-key": "demo-key-123"}
BASE_URL = "http://localhost:1560"
PROD = os.getenv("PROD", "0") == "1"  # 🔥 ADD THIS LINE
HOME = Path.home()
TH_ROOT = HOME / ".treehopper"
REGISTRY_DIR = TH_ROOT / "registry"
REGISTRY_AGENTS = REGISTRY_DIR / "agents"
REGISTRY_AGENTS_INDEX = REGISTRY_DIR / "agents.json"
SUBSCRIPTION_FILE = TH_ROOT / "subscription_id.txt"

PACKAGE_AGENTS_DIR = Path(__file__).parent / "agents"

RUNTIME_DIR = TH_ROOT / "runtime"
MAIN_PID_FILE = RUNTIME_DIR / "main_server.pid"
CHAIN_PID_PREFIX = "chain_"


# ---------------------------------------------------------------------
# PID RELATED HELPERS
# ---------------------------------------------------------------------


def ensure_runtime_dir():
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def write_pid(path: Path, pid: int):
    ensure_runtime_dir()
    path.write_text(str(pid))


def read_pid(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        return int(path.read_text().strip())
    except Exception:
        return None


def kill_pid(pid: int):
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    time.sleep(3)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    return True


# ---------------------------------------------------------------------
# REGISTRY / SUBSCRIPTION HELPERS
# ---------------------------------------------------------------------
def ensure_registry_dirs() -> None:
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    REGISTRY_AGENTS.mkdir(parents=True, exist_ok=True)


def get_or_create_subscription_id() -> str:
    ensure_registry_dirs()
    if SUBSCRIPTION_FILE.exists():
        return SUBSCRIPTION_FILE.read_text().strip()
    sid = str(uuid.uuid4())
    SUBSCRIPTION_FILE.write_text(sid)
    return sid


def load_agents_index() -> list[dict]:
    ensure_registry_dirs()
    if not REGISTRY_AGENTS_INDEX.exists():
        return []
    try:
        return json.loads(REGISTRY_AGENTS_INDEX.read_text())
    except json.JSONDecodeError:
        return []


def save_agents_index(index: list[dict]) -> None:
    ensure_registry_dirs()
    REGISTRY_AGENTS_INDEX.write_text(json.dumps(index, indent=2))


def validate_agent_name(name: str) -> str:
    # strip accidental quotes / whitespace
    clean = name.strip()

    if " " in clean:
        raise ValueError("Agent name cannot contain spaces")
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]{3,24}$", clean):
        raise ValueError(
            "Invalid agent name. Must:\n"
            " • start with a letter\n"
            " • be 4–25 chars\n"
            " • contain only letters, numbers, underscore"
        )
    return clean.lower()


# ---------------------------------------------------------------------
# SERVER HELPERS
# ---------------------------------------------------------------------
def run(
    th_port: int = int(os.getenv("TH_PORT", 1560)), background: bool = False
) -> None:
    ensure_runtime_dir()
    LOG_FILE = RUNTIME_DIR / "server.log"

    # rotate if >1 MB
    if LOG_FILE.exists() and LOG_FILE.stat().st_size > 1_000_000:
        LOG_FILE.unlink(missing_ok=True)

    # overwrite log each run
    LOG_FILE.write_text("")

    if background:
        print(f"🚀 Starting Treehopper in background on port {th_port}")
        env = os.environ.copy()
        env["PROD"] = "1"

        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",  # <<< FIX
                "treehopper.treehopper:app",
                "--host",
                "0.0.0.0",
                "--port",
                str(th_port),
            ],
            stdout=open(LOG_FILE, "w"),
            stderr=subprocess.STDOUT,
            env=env,
        )

        write_pid(MAIN_PID_FILE, proc.pid)
        print(f"sys-executable path - {sys.executable}")
        print(f"📌 PID: {proc.pid}")
        print(f"📝 Logs: {LOG_FILE}")
        return

    # foreground mode
    write_pid(MAIN_PID_FILE, os.getpid())
    uvicorn.run(
        "treehopper.treehopper:app",
        host="0.0.0.0",
        port=th_port,
        reload=not (PROD or bool(os.getenv("PYTEST_CURRENT_TEST"))),
    )


def restart(th_port: int = 1560) -> None:
    print("🔄 Restarting Treehopper server...")

    # 1️⃣ Kill running uvicorn + treehopper servers
    subprocess.run(["pkill", "-f", "uvicorn"], stderr=subprocess.DEVNULL)
    subprocess.run(["pkill", "-f", "treehopper run"], stderr=subprocess.DEVNULL)
    subprocess.run(["pkill", "-f", "treehopper"], stderr=subprocess.DEVNULL)

    # 2️⃣ Wait until the port is fully released
    for _ in range(20):  # wait up to ~5 sec
        time.sleep(0.25)
        proc = subprocess.run(
            ["lsof", "-t", f"-i:{th_port}"], capture_output=True, text=True
        )
        if not proc.stdout.strip():  # free
            break
        # force kill hanging PID
        pid = proc.stdout.strip()
        subprocess.run(["kill", "-9", pid], stderr=subprocess.DEVNULL)

    # 3️⃣ Start server
    env = os.environ.copy()
    env["PROD"] = "1"
    subprocess.Popen(["treehopper", "run", "--bg"], env=env)

    # 4️⃣ Wait for server to pass health check
    for _ in range(40):
        time.sleep(0.25)
        try:
            r = requests.get(
                f"http://localhost:{th_port}/api/v1/sys/health", timeout=0.25
            )
            if r.status_code == 200:
                print("🚀 Treehopper restarted")
                return
        except Exception:
            pass

    print(
        "⚠️ Restart attempted, but health did not confirm — server may still be starting."
    )


def status():
    pid = read_pid(MAIN_PID_FILE)
    if not pid:
        print("⛔ Treehopper is NOT running")
        return

    # confirm process exists
    try:
        os.kill(pid, 0)  # does nothing if process exists
        print(f"🟢 Treehopper server is RUNNING (PID {pid})")
        print("URL: http://localhost:1560")
    except ProcessLookupError:
        print("⚠️ PID file exists but process is not running — cleaning...")
        MAIN_PID_FILE.unlink(missing_ok=True)


def ensure_server() -> None:
    try:
        if (
            requests.get(f"{BASE_URL}/api/v1/sys/health", timeout=0.3).status_code
            == 200
        ):
            return
    except Exception:
        pass

    print("⚠️  API server not running — starting FastAPI now...")
    subprocess.Popen(["treehopper", "run"])

    for _ in range(15):
        time.sleep(0.25)
        try:
            if (
                requests.get(f"{BASE_URL}/api/v1/sys/health", timeout=0.20).status_code
                == 200
            ):
                return
        except Exception:
            continue

    print("ℹ️  API may already be running — continuing")


def call(path: str, params: dict) -> None:
    ensure_server()
    r = requests.get(f"{BASE_URL}/api/v1/dev/agents", headers=API_KEY)
    r.raise_for_status()
    agents = r.json()

    method = next((a["method"] for a in agents if a["path"] == path), None)
    if not method:
        print(f"❌ Agent not found: {path}")
        return

    if method == "GET":
        response = requests.get(f"{BASE_URL}{path}", params=params, headers=API_KEY)
    else:
        response = requests.post(f"{BASE_URL}{path}", json=params, headers=API_KEY)

    print(response.text)


def list_agents() -> None:
    ensure_server()
    r = requests.get(f"{BASE_URL}/api/v1/dev/agents", headers=API_KEY)
    r.raise_for_status()
    agents = r.json()
    table_data = [
        [agent["path"], agent["goal"], ", ".join(agent.get("tags", []))]
        for agent in agents
    ]
    print(tabulate(table_data, headers=["AGENT PATH", "GOAL", "TAGS"], tablefmt="grid"))


# ---------------------------------------------------------------------
# INIT (SCAFFOLD)
# ---------------------------------------------------------------------
def agent_name_exists(agent_name: str) -> bool:
    name = agent_name.lower()  # normalize

    # 1️⃣ Built-in framework agents
    for f in PACKAGE_AGENTS_DIR.glob("*.py"):
        if f.stem.lower() == name:
            return True

    ensure_registry_dirs()

    # 2️⃣ Registry index
    index = load_agents_index()
    if any(a.get("agent_name", "").lower() == name for a in index):
        return True

    # 3️⃣ Folder scan fallback (in case index corrupted)
    if REGISTRY_AGENTS.exists():
        for folder in REGISTRY_AGENTS.iterdir():
            yaml_path = folder / "agent.yaml"
            if yaml_path.exists():
                try:
                    cfg = yaml.safe_load(yaml_path.read_text())
                    if cfg.get("agent_name", "").lower() == name:
                        return True
                except Exception:
                    continue

    return False


def init_agent(agent_name: str) -> None:
    agent_name = validate_agent_name(agent_name)

    if agent_name_exists(agent_name):
        print(f"❌ Agent '{agent_name}' already exists")
        sys.exit(1)

    target_dir = Path.cwd() / agent_name
    if target_dir.exists():
        print(f"❌ Directory '{agent_name}' already exists here.")
        sys.exit(1)

    ensure_registry_dirs()
    subscription_id = get_or_create_subscription_id()
    agent_id = f"{agent_name}-{uuid.uuid4().hex[:8]}"

    target_dir.mkdir(parents=True, exist_ok=False)

    # ------------------------------------------------
    # Modern YAML including input + output schema
    # ------------------------------------------------
    (target_dir / "agent.yaml").write_text(
        yaml.safe_dump(
            {
                "agent_name": agent_name,
                "agent_id": agent_id,
                "subscription_id": subscription_id,
                "entrypoint": f"/{agent_name}",
                "description": f"{agent_name} agent",
                "inputs": [{"name": "name", "type": "string"}],  # default template
                "outputs": [{"name": "message", "type": "string"}],  # default template
                "tags": [],
                "version": "1.0",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    # ------------------------------------------------
    # Schema – JSON ONLY, no query parameters
    # ------------------------------------------------
    (target_dir / "schema.py").write_text(
        f"""from pydantic import BaseModel

class {agent_name.capitalize()}Request(BaseModel):
    name: str
""",
        encoding="utf-8",
    )

    # ------------------------------------------------
    # Handler – POST only, clean JSON body pattern
    # ------------------------------------------------
    (target_dir / "handler.py").write_text(
        f"""from fastapi import Body
from fastapi.responses import JSONResponse
from treehopper.treehopper import agent
from .schema import {agent_name.capitalize()}Request

class {agent_name.capitalize()}Agent:
    async def run(self, name: str) -> dict:
        return {{"message": f"Hello {{name}} from {agent_name} agent!"}}

@agent("{agent_name}", method="POST", goal="Example agent created via `treehopper init`")
async def handle(payload: {agent_name.capitalize()}Request = Body(...)):
    ag = {agent_name.capitalize()}Agent()
    return JSONResponse(await ag.run(payload.name))
""",
        encoding="utf-8",
    )

    (target_dir / "__init__.py").write_text("", encoding="utf-8")

    print(f"✨ Scaffold created at {target_dir}")
    print(f"🆔 agent_id: {agent_id}")
    print(f"🔑 subscription_id: {subscription_id}")


# ---------------------------------------------------------------------
# VALIDATE & BUILD
# ---------------------------------------------------------------------
def validate_agent_yaml(agent_dir: Path) -> dict:
    yaml_path = agent_dir / "agent.yaml"
    if not yaml_path.exists():
        raise SystemExit(f"❌ Missing agent.yaml in {agent_dir}")
    try:
        data = yaml.safe_load(yaml_path.read_text())
    except yaml.YAMLError as e:
        raise SystemExit(f"❌ Invalid agent.yaml: {e}")

    for key in ["agent_name", "agent_id", "subscription_id", "entrypoint"]:
        if key not in data:
            raise SystemExit(f"❌ agent.yaml missing required field: {key}")
    return data


def lint_agent(agent_ref: str) -> None:
    agent_dir = Path.cwd() / agent_ref
    cfg = validate_agent_yaml(agent_dir)
    validate_agent_name(cfg["agent_name"])

    handler_path = agent_dir / "handler.py"
    if not handler_path.exists():
        print("❌ handler.py missing")
        sys.exit(1)

    tree = ast.parse(handler_path.read_text())

    found = False
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "handle"
        ):
            found = True

            # must accept exactly one parameter: payload
            params = [p.arg for p in node.args.args]
            if params != ["payload"]:
                print(
                    "❌ Handler must accept exactly one argument: payload: SchemaClass = Body(...)"
                )
                sys.exit(1)

            # must contain Body(...) annotation
            ann = node.args.args[0].annotation
            if not ann:
                print("❌ payload must be typed with Schema")
                sys.exit(1)

    if not found:
        print("❌ No handler() function found")
        sys.exit(1)

    print(f"🟢 Lint passed for {agent_ref}")


def build_agent(agent_ref: str) -> None:
    agent_dir = Path.cwd() / agent_ref
    if not agent_dir.exists() or not agent_dir.is_dir():
        print(f"❌ Agent folder '{agent_ref}' does not exist")
        sys.exit(1)

    cfg = validate_agent_yaml(agent_dir)
    agent_name = validate_agent_name(cfg["agent_name"])
    agent_id = cfg["agent_id"]
    entrypoint = cfg["entrypoint"]

    # 🚨 enforce schema fields
    inputs = cfg.get("inputs")
    outputs = cfg.get("outputs")
    if not isinstance(inputs, list) or not isinstance(outputs, list):
        print("❌ agent.yaml must include 'inputs' and 'outputs' list fields")
        sys.exit(1)

    ensure_registry_dirs()
    index = load_agents_index()

    # 🚫 Prevent duplicate agent names
    for agent in index:
        if agent["agent_name"] == agent_name and agent["agent_id"] != agent_id:
            print(f"❌ Agent name '{agent_name}' already exists")
            sys.exit(1)

    target_dir = REGISTRY_AGENTS / agent_id
    if target_dir.exists():
        shutil.rmtree(target_dir)
    shutil.copytree(agent_dir, target_dir)

    # Store full metadata (including schema)
    index = [a for a in index if a["agent_id"] != agent_id]
    index.append(
        {
            "agent_name": agent_name,
            "agent_id": agent_id,
            "entrypoint": entrypoint,
            "routes": {
                "by_name": f"/api/v1/agents/{agent_name}",
                "by_id": f"/api/v1/agents/{agent_id}",
            },
            "inputs": inputs,
            "outputs": outputs,
        }
    )
    save_agents_index(index)

    print(f"✅ Built agent '{agent_name}' → {target_dir}")
    print("📌 Call example:")
    ex_key = inputs[0]["name"]
    print(f'  treehopper call /api/v1/agents/{agent_name} \'{{"{ex_key}": "sample"}}\'')


# ---------------------------------------------------------------------
# AGENT INFO
# ---------------------------------------------------------------------
def agent_info(ref: str) -> None:
    ensure_registry_dirs()
    index = load_agents_index()
    match = next(
        (a for a in index if a["agent_name"] == ref or a["agent_id"] == ref), None
    )
    if not match:
        print(f"❌ No agent found matching '{ref}'")
        sys.exit(1)

    yaml_path = REGISTRY_AGENTS / match["agent_id"] / "agent.yaml"
    print("📄 Agent metadata:\n")
    print(yaml.safe_dump(yaml.safe_load(yaml_path.read_text()), sort_keys=False))


def delete_agent(ref: str):
    ref = validate_agent_name(ref)
    ensure_registry_dirs()
    index = load_agents_index()

    match = next(
        (a for a in index if a["agent_name"] == ref or a["agent_id"] == ref), None
    )
    if not match:
        print(f"❌ No agent found matching '{ref}'")
        sys.exit(1)

    agent_name = match["agent_name"]
    agent_id = match["agent_id"]
    agent_path = REGISTRY_AGENTS / agent_id

    confirm = input(f"⚠️ Delete agent '{agent_name}' (ID {agent_id}) permanently? y/N: ")
    if confirm.lower() not in ("y", "yes"):
        print("❎ Cancelled")
        return

    # remove folder
    if agent_path.exists():
        shutil.rmtree(agent_path)

    # remove from index
    index = [a for a in index if a["agent_id"] != agent_id]
    save_agents_index(index)

    print(f"🗑 Deleted agent '{agent_name}' ({agent_id})")
    print("🔄 Restarting server to refresh agent registry...")

    restart()


# ---------------------------------------------------------------------
# STOP MAIN SERVER
# ---------------------------------------------------------------------
def stop():
    pid = read_pid(MAIN_PID_FILE)
    if not pid:
        print("ℹ️ No running Treehopper server found")
        return
    print(f"🛑 Stopping Treehopper server (PID {pid}) ...")
    kill_pid(pid)
    MAIN_PID_FILE.unlink(missing_ok=True)
    print("✔ Stopped")


# ---------------------------------------------------------------------
# CHAIN RUNTIME STOP
# ---------------------------------------------------------------------
def stop_chain():
    ensure_runtime_dir()
    stopped = False
    for f in RUNTIME_DIR.iterdir():
        if f.name.startswith(CHAIN_PID_PREFIX) and f.suffix == ".pid":
            pid = read_pid(f)
            print(f"🛑 Stopping chain runtime {f.name} (PID {pid})")
            kill_pid(pid)
            f.unlink(missing_ok=True)
            stopped = True
    if not stopped:
        print("ℹ️ No chain runtimes found")


# ---------------------------------------------------------------------
# CHAIN FROM CLI
# ---------------------------------------------------------------------


def run_chain_from_cli(args: list[str]):
    """
    Usage:
      treehopper chain /api/v1/agents/A /api/v1/agents/B ...
    """
    if len(args) < 1:
        print("Usage: treehopper chain <agent1> <agent2> ...")
        sys.exit(1)

    agents = args
    chain_body = {"chain": [{"path": agent, "params": {}} for agent in agents]}

    ensure_server()
    r = requests.post(f"{BASE_URL}/api/v1/dev/chain", json=chain_body, headers=API_KEY)
    print(r.text)


# ---------------------------------------------------------------------
# TREEHOPPER HELP
# ---------------------------------------------------------------------


def print_help():
    print(
        """
Treehopper CLI Commands
────────────────────────────────────────────
  treehopper run                         Start the main server
  treehopper run --bg                    Start the main server in background
  treehopper stop                        Stop the main server
  treehopper restart                     Restart main server
  treehopper list                        List installed agents
  treehopper call <path> '<json>'        Call an agent
  treehopper init <agent_name>           Create agent scaffold template
  treehopper lint <agent_folder>         Validate handler.py + YAML
  treehopper build <agent_folder>        Install agent to registry
  treehopper agent info <ref>            Show metadata
  treehopper status                     Show if the main server is running
  treehopper agent delete <ref>         Delete installed agent safely
  treehopper chain                      To view all Chain related commands
"""
    )


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------
def main() -> None:
    if len(sys.argv) < 2:
        print_help()
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "help":
        print_help()
    elif cmd == "run":
        bg = "--bg" in sys.argv
        run(background=bg)
    elif cmd == "stop":
        stop()
    elif cmd == "restart":
        restart()
    elif cmd == "list":
        list_agents()
    elif cmd == "call":
        call(sys.argv[2], json.loads(sys.argv[3]))
    elif cmd == "init":
        if len(sys.argv) != 3:
            print("❌ Usage: treehopper init <agent_name>")
            sys.exit(1)
        agent_name = validate_agent_name(sys.argv[2])
        init_agent(agent_name)
    elif cmd == "lint":
        lint_agent(sys.argv[2])
    elif cmd == "build":
        build_agent(sys.argv[2])
    elif cmd == "agent" and sys.argv[2] == "info":
        agent_info(sys.argv[3])
    elif cmd == "chain" and len(sys.argv) > 2 and sys.argv[2] == "stop":
        stop_chain()
    elif cmd == "chain":
        from .treehopper_chains import chain_entry

        chain_entry(sys.argv[2:])
    elif cmd == "status":
        status()
    elif cmd == "agent" and sys.argv[2] == "delete":
        delete_agent(sys.argv[3])
    else:
        print(f"Unknown command: {cmd}")
        print_help()
        sys.exit(1)
