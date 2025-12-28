# treehopper/treehopper_cli.py
import os

# Add these with the other imports at the top
import uuid

# import importlib.util
import sys
import argparse
from pathlib import Path
from treehopper.th_config import (
    API_KEY,
    BASE_URL,
    # HOME,
    # TH_ROOT,
    REGISTRY_DIR,
    REGISTRY_AGENTS,
    # REGISTRY_AGENTS_INDEX,
    # SUBSCRIPTION_FILE,
    RUNTIME_DIR,
    MAIN_PID_FILE,
    CHAIN_PID_PREFIX,
    ensure_dirs,
)
from treehopper.chains_agents_refresh_status import (
    chains_status,
    # chains_restart,
    agents_status,
    # agents_restart,
)

from treehopper.whatis import print_whatis
from treehopper.th_ui_cli import launch_ui, stop_ui

# from treehopper.visualizer.db_init import DBInitializer
from treehopper.admin_cli import admin_entry
from treehopper.maintainance.maintainer import startup_maintenance
from treehopper.utils.commons import (
    get_or_create_subscription_id,
    load_agents_index,
    save_agents_index,
    ensure_registry_dirs,
    validate_agent_name,
)
from treehopper.treehopper_cleaner import main as clean_main
from treehopper.th_setup import setup_treehopper
from treehopper.agent_template_cli import (
    agent_create_from_template,
    list_templates,
)
from treehopper.workspace_cli import workspace_create, workspace_info

# Add with other imports
from treehopper.sync_to_sqlite import sync_agents, sync_yaml
from treehopper.help_str import help_string
from treehopper.visualizer.inspect_db import (
    run_view_db,
)  # Assuming logic is in a separate file or import it here

from treehopper.visualizer.log_tail import run_view_logs
from treehopper.visualizer.system_view import show_root_tree, show_pids

# ==============================================================================
# GLOBAL OVERRIDE FOR DEVELOPMENT
# Make CLI always import local treehopper source first (instead of pip package)
# ==============================================================================
if os.getenv("TREEHOPPER_FORCE_LOCAL", "1") == "1":
    PROJECT_ROOT = Path(__file__).resolve().parents[1]  # /treehopper-core/treehopper
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    print(f"[FORCE_LOCAL] Treehopper CLI using local source at: {PROJECT_ROOT}")
    print(f"[FORCE_LOCAL] sys.path[0] = {sys.path[0]}")

# ==============================================================================

import json

# import re
import shutil
import subprocess
import time
import ast
from typing import List
import requests
import uvicorn
import yaml
from dotenv import load_dotenv
from tabulate import tabulate
import socket

import signal

from treehopper.logging import get_logger

logger = get_logger()
logger.info("Inside CLI")
load_dotenv()


PACKAGE_AGENTS_DIR = Path(__file__).parent / "agents"
PROD = os.getenv("PROD", "0") == "1"  # 🔥 ADD THIS LINE


# ------------------------------------------------------------------------------
# DEV MODE — GUARD: Inject local project root into PYTHONPATH only when needed
# ------------------------------------------------------------------------------
def maybe_inject_dev_pythonpath(env: dict):
    """
    Inject local source path into PYTHONPATH for dev-mode ONLY.
    - Activated when TREEHOPPER_DEV_MODE=1 in env of parent or child.
    - Safe: silently ignored if treehopper.environment doesn't exist.
    """

    # Pass treehopper-dev flag down to subprocess
    if os.getenv("TREEHOPPER_DEV_MODE") == "1":
        env["TREEHOPPER_DEV_MODE"] = "1"

    # Only inject when opted-in
    if env.get("TREEHOPPER_DEV_MODE") != "1":
        return env

    try:
        from treehopper.environment import inject_pythonpath

        inject_pythonpath(env)
    except Exception as e:
        logger.error(f"{str(e)}")
        pass

    return env


# ---------------------------------------------------------------------
# PID RELATED HELPERS
# ---------------------------------------------------------------------


def ensure_runtime_dir():
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def write_pid(path: Path, pid: int, port: int | None = None):
    """
    Write pid file. Format:
      - legacy: "<pid>"
      - new   : "<pid>:<port>"

    We write pid:port when port is known so future checks can report the exact port.
    """
    ensure_runtime_dir()
    if port is not None:
        path.write_text(f"{pid}:{port}")
    else:
        path.write_text(str(pid))


def read_pid(path: Path) -> int | None:
    """
    Read PID from file. Accepts both "<pid>" and "<pid>:<port>" formats.
    Returns pid (int) or None.
    """
    if not path.exists():
        return None
    try:
        text = path.read_text().strip()
        if ":" in text:
            pid_str, _ = text.split(":", 1)
            return int(pid_str)
        return int(text)
    except Exception as e:
        logger.error(f"{str(e)}")
        return None


def read_pid_and_port(path: Path) -> tuple[int | None, int | None]:
    """
    Return (pid, port) from pid file.
    - pid: int or None
    - port: int or None
    Accepts "<pid>" or "<pid>:<port>".
    """
    if not path.exists():
        return None, None
    try:
        text = path.read_text().strip()
        if ":" in text:
            pid_str, port_str = text.split(":", 1)
            return int(pid_str), int(port_str)
        return int(text), None
    except Exception as e:
        logger.error(f"{str(e)}")
        return None, None


def kill_pid(pid: int):
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError as e:
        logger.error(f"{str(e)}")
        return True
    time.sleep(3)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError as e:
        logger.error(f"{str(e)}")
        return True
    return True


# ---------------------------------------------------------------------
# SERVER HELPERS
# ---------------------------------------------------------------------
def run(
    th_port: int = int(os.getenv("TH_PORT", 1567)), background: bool = False
) -> None:
    ensure_runtime_dir()
    LOG_FILE = RUNTIME_DIR / "server.log"

    # rotate if >1 MB
    if LOG_FILE.exists() and LOG_FILE.stat().st_size > 1_000_000:
        LOG_FILE.unlink(missing_ok=True)

    # overwrite log each run
    LOG_FILE.write_text("")

    if background:
        logger.info(f"🚀 Starting Treehopper in background on port {th_port}")
        env = os.environ.copy()
        env["PROD"] = "1"
        # Inject PYTHONPATH only in dev mode
        env = maybe_inject_dev_pythonpath(env)

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
        print("🟢 Treehopper server is RUNNING")
        print("URL: http://localhost:1567")
        logger.info("🟢 Treehopper server is RUNNING")
        logger.info("URL: http://localhost:1567")
        logger.info(f"sys-executable path - {sys.executable}")
        logger.info(f"📌 PID: {proc.pid}")
        logger.info(f"📝 Logs: {LOG_FILE}")
        return

    # foreground mode
    write_pid(MAIN_PID_FILE, os.getpid())
    logger.info("🚀 Starting Treehopper in FOREGROUND")
    logger.info(
        f"🐍 Python Interpreter: {sys.executable}"
    )  # Adds transparency to the demo
    print("🚀 Starting Treehopper in FOREGROUND")
    print(f"🐍 Python Interpreter: {sys.executable}")  # Adds transparency to the demo
    uvicorn.run(
        "treehopper.treehopper:app",
        host="0.0.0.0",
        port=th_port,
        reload=not (PROD or bool(os.getenv("PYTEST_CURRENT_TEST"))),
    )


def restart(th_port: int = 1567) -> None:
    logger.info("🔄 Restarting Treehopper server...")

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
    # Inject PYTHONPATH only in dev mode
    env = maybe_inject_dev_pythonpath(env)

    subprocess.Popen(["treehopper", "run", "--bg"], env=env)

    # 4️⃣ Wait for server to pass health check
    for _ in range(40):
        time.sleep(0.25)
        try:
            r = requests.get(
                f"http://localhost:{th_port}/api/v1/sys/health", timeout=0.25
            )
            if r.status_code == 200:
                logger.info("🚀 Treehopper restarted")
                print("🚀 Treehopper restarted")
                return
        except Exception as e:
            logger.error(f"[treehopper_cli] {str(e)}")
            pass

    logger.info(
        "⚠️ Restart attempted, but health did not confirm — server may still be starting."
    )
    print(
        "⚠️ Restart attempted, but health did not confirm — server may still be starting."
    )


def status():
    pid = read_pid(MAIN_PID_FILE)
    if not pid:
        print("⛔ Treehopper is NOT running")
        logger.info("⛔ Treehopper is NOT running")
        return

    # confirm process exists
    try:
        os.kill(pid, 0)  # does nothing if process exists
        print(f"🟢 Treehopper server is RUNNING (PID {pid})")
        print("URL: http://localhost:1567")
        logger.info(f"🟢 Treehopper server is RUNNING (PID {pid})")
        logger.info("URL: http://localhost:1567")
    except ProcessLookupError:
        logger.error("⚠️ PID file exists but process is not running — cleaning...")
        print("⚠️ PID file exists but process is not running — cleaning...")
        MAIN_PID_FILE.unlink(missing_ok=True)


def ensure_server() -> None:
    from dotenv import load_dotenv

    load_dotenv()
    # 🚨 TEST MODE GUARD
    if os.getenv("TREEHOPPER_RUNTIME_MODE") == "1":
        print("Test Mode Enabled - Returning")
        logger.info("Test Mode Enabled - Returning")
        return
    print("Main Run Mode Enabled - continuing")
    logger.info("Main Run Mode Enabled - continuing")
    try:
        if (
            requests.get(f"{BASE_URL}/api/v1/sys/health", timeout=0.3).status_code
            == 200
        ):
            return
    except Exception as e:
        logger.error(f"[treehopper_cli] {str(e)}")
        pass

    logger.info("⚠️  API server not running — starting FastAPI now...")
    print(("⚠️  API server not running — starting FastAPI now..."))
    subprocess.Popen(["treehopper", "run"])

    for _ in range(15):
        time.sleep(0.25)
        try:
            if (
                requests.get(f"{BASE_URL}/api/v1/sys/health", timeout=0.20).status_code
                == 200
            ):
                return
        except Exception as e:
            logger.error(f"{str(e)}")
            continue

    logger.info("ℹ️  API may already be running — continuing")
    print("ℹ️  API may already be running — continuing")


def call(path: str, params: dict) -> None:
    if not path or path == "":
        logger.error("Agent name or API path is not provided")
        print("Agent name or API path is not provided")
        return
    if "/" not in path:
        print(f"Full Agent path is not provided for - {path}")
        print(
            f"Trying to create the full agent path like - \
             /api/v1/agents/{path}"
        )
        logger.warn(f"Full Agent path is not provided for - {path}")
        logger.warn(
            f"Trying to create the full agent path like - \
             /api/v1/dev/agents/{path}"
        )
        path = f"/api/v1/agents/{path}"

    ensure_server()
    r = requests.get(f"{BASE_URL}/api/v1/dev/agents", headers=API_KEY)
    r.raise_for_status()
    agents = r.json()

    method = next((a["method"] for a in agents if a["path"] == path), None)
    if not method:
        logger.info(f"❌ Agent not found: {path}")
        print(f"❌ Agent not found: {path}")
        return

    if method == "GET":
        response = requests.get(f"{BASE_URL}{path}", params=params, headers=API_KEY)
    else:
        response = requests.post(f"{BASE_URL}{path}", json=params, headers=API_KEY)

    logger.info(response.text)
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
    logger.info(
        tabulate(table_data, headers=["AGENT EP", "GOAL", "TAGS"], tablefmt="grid")
    )
    print(tabulate(table_data, headers=["AGENT EP", "GOAL", "TAGS"], tablefmt="grid"))


def format_agents_for_table(agents_list: list[dict]) -> str:
    """
    Converts the structured agents list (List[Dict[mode, List[agent_name]]])
    into a single string for table display.
    """
    display_parts = []

    # Iterate through each step dictionary in the list
    for step_dict in agents_list:
        for mode, agent_names in step_dict.items():
            if agent_names and isinstance(agent_names, list):
                # Use the recommended separator: >>
                step_display = f"{mode}: {', '.join(agent_names)}"
                display_parts.append(step_display)
            else:
                display_parts.append(f"{mode}: (None)")

    # --- CHANGE THIS LINE ---
    # Join all steps with the new double arrow separator
    return " >> ".join(display_parts)
    # -----------------------


def list_chains() -> None:
    ensure_server()
    r = requests.get(f"{BASE_URL}/api/v1/dev/chains", headers=API_KEY)
    r.raise_for_status()
    chains = r.json()

    # Check if 'chains' is a list and not empty before processing
    if not isinstance(chains, list) or not chains:
        logger.info("No chains found.")
        print("No chains found.")
        return

    table_data = []
    for chain in chains:
        # 1. Get the structured agents data (e.g., [{"SEQUENTIAL": [...]}, ...])
        structured_agents = chain.get("agents", [])

        # 2. Format it using the new helper function
        formatted_agents = format_agents_for_table(structured_agents)

        table_data.append(
            [
                chain["chain_name"],
                chain["chain_type"],
                chain["endpoint"],
                # Use the formatted string for the table
                formatted_agents,
                chain["created_at"],
            ]
        )

    headers = ["CHAIN NAME", "TYPE", "ENDPOINT", "AGENTS", "CREATED AT"]

    output = tabulate(
        table_data,
        headers=headers,
        tablefmt="grid",
    )

    logger.info(output)
    print(output)


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
        logger.info(f"❌ Agent '{agent_name}' already exists")
        sys.exit(1)

    target_dir = Path.cwd() / agent_name
    if target_dir.exists():
        print(f"❌ Directory '{agent_name}' already exists here.")
        logger.info(f"❌ Directory '{agent_name}' already exists here.")
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
from treehopper.treehopper import agent, get_agent_id
from .schema import {agent_name.capitalize()}Request
agent_name = '{agent_name}'
agent_id = get_agent_id(agent_name)
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
    logger.info(f"✨ Scaffold created at {target_dir}")
    logger.info(f"🆔 agent_id: {agent_id}")
    logger.info(f"🔑 subscription_id: {subscription_id}")


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
        logger.warn("❌ handler.py missing")
        sys.exit(1)

    tree = ast.parse(handler_path.read_text())

    found = False
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "handle"
        ):
            found = True

            # Extract parameter names
            params: List[ast.arg] = node.args.args
            param_names = [p.arg for p in params]

            valid_params = set(["file", "payload"])

            # 1. Check for unexpected parameters
            if not set(param_names).issubset(valid_params):
                logger.warn(
                    f"❌ Handler signature contains invalid parameters: \
                        {set(param_names) - valid_params}. Only 'file' and 'payload' are allowed."
                )
                print(
                    f"❌ Handler signature contains invalid parameters: \
                        {set(param_names) - valid_params}. Only 'file' and 'payload' are allowed."
                )
                sys.exit(1)

            # 2. Check for empty signature (must have at least one)
            if not param_names:
                logger.warn(
                    "❌ Handler must accept at least one argument: 'file' or 'payload'."
                )
                print(
                    "❌ Handler must accept at least one argument: 'file' or 'payload'."
                )
                sys.exit(1)

            # --- Annotation Validation Logic ---

            # Check 'file' parameter if present
            if "file" in param_names:
                file_param = next((p for p in params if p.arg == "file"), None)
                # We need to ensure it has some type annotation (e.g., UploadFile = File(...))
                if not file_param or not file_param.annotation:
                    logger.info(
                        "❌ The 'file' parameter must be present and typed (e.g., file: UploadFile = File(None))."
                    )
                    print(
                        "❌ The 'file' parameter must be present and typed (e.g., file: UploadFile = File(None))."
                    )
                    sys.exit(1)

            # Check 'payload' parameter if present
            if "payload" in param_names:
                payload_param = next((p for p in params if p.arg == "payload"), None)
                # We need to ensure it has some type annotation (e.g., payload: Schema = Form(...))
                if not payload_param or not payload_param.annotation:
                    logger.info(
                        "❌ The 'payload' parameter must be present and typed with\
                             a Schema and Form/Body (e.g., payload: Schema = Form())."
                    )
                    print(
                        "❌ The 'payload' parameter must be present and typed with\
                             a Schema and Form/Body (e.g., payload: Schema = Form())."
                    )
                    sys.exit(1)

            # Additional Check: If 'file' is absent, 'payload' must be present for a functional API
            if "file" not in param_names and "payload" not in param_names:
                # This should be caught by the empty signature check, but redundant for safety
                logger.info(
                    "❌ Handler must accept at least one argument: 'file' or 'payload'."
                )
                print(
                    "❌ Handler must accept at least one argument: 'file' or 'payload'."
                )
                sys.exit(1)

            # We assume successful validation if we reached here
            break

    if not found:
        logger.info("❌ No handle() function found")
        print("❌ No handle() function found")
        sys.exit(1)
    logger.info(f"🟢 Lint passed for {agent_ref}")
    print(f"🟢 Lint passed for {agent_ref}")


def build_agent(agent_ref: str) -> None:
    agent_dir = Path.cwd() / agent_ref
    if not agent_dir.exists() or not agent_dir.is_dir():
        logger.info(f"❌ Agent folder '{agent_ref}' does not exist")
        print(f"❌ Agent folder '{agent_ref}' does not exist")
        sys.exit(1)

    cfg = validate_agent_yaml(agent_dir)
    agent_name = validate_agent_name(cfg["agent_name"])
    agent_id = cfg["agent_id"]
    subscription_id = cfg["subscription_id"]
    description = cfg.get("description") or ""
    entrypoint = cfg["entrypoint"]
    tags = cfg.get("tags") or []
    # 🚨 enforce schema fields
    inputs = cfg.get("inputs")
    outputs = cfg.get("outputs")
    if not isinstance(inputs, list) or not isinstance(outputs, list):
        logger.info("❌ agent.yaml must include 'inputs' and 'outputs' list fields")
        print("❌ agent.yaml must include 'inputs' and 'outputs' list fields")
        sys.exit(1)

    ensure_registry_dirs()
    index = load_agents_index()

    # 🚫 Prevent duplicate agent names
    for agent in index:
        if agent["agent_name"] == agent_name and agent["agent_id"] != agent_id:
            logger.info(f"❌ Agent name '{agent_name}' already exists")
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
            "subscription_id": subscription_id,
            "entrypoint": entrypoint,
            "description": description,
            "routes": {
                "by_name": f"/api/v1/agents/{agent_name}",
                "by_id": f"/api/v1/agents/{agent_id}",
            },
            "inputs": inputs,
            "outputs": outputs,
            "tags": tags,
        }
    )
    save_agents_index(index)
    # ✅ NEW: Sync to SQLite
    try:
        sync_agents()
        print("✅ Agent synced to database")
        logger.info("✅ Agent synced to database")
    except Exception as e:
        print(f"⚠️  SQLite sync failed: {e}")
        logger.error(f"⚠️  SQLite sync failed: {e}")

    # ✅ NEW: Cache YAML in SQLite (Phase 2)
    try:
        sync_yaml(
            entity_type="agent",
            entity_name=agent_name,
            entity_id=agent_id,
            yaml_content=yaml.dump(cfg, default_flow_style=False, sort_keys=False),
        )
        logger.info("✅ Agent YAML cached in database")
        print("✅ Agent YAML cached in database")
    except Exception as e:
        logger.error(f"⚠️  Failed to cache YAML: {e}")
        print(f"⚠️  Failed to cache YAML: {e}")

    logger.info(f"✅ Built agent '{agent_name}' → {target_dir}")
    logger.info("📌 Call example:")
    print(f"✅ Built agent '{agent_name}' → {target_dir}")
    print("📌 Call example:")
    ex_key = inputs[0]["name"]
    logger.info(
        f'  treehopper call /api/v1/agents/{agent_name} \'{{"{ex_key}": "sample"}}\''
    )
    print(f'  treehopper call /api/v1/agents/{agent_name} \'{{"{ex_key}": "sample"}}\'')


def push_file(agent_name: str, src_path: str) -> None:
    """Copy a file into persistent shared storage for the agent."""
    ensure_registry_dirs()
    index = load_agents_index()

    match = next((a for a in index if a["agent_name"] == agent_name), None)
    if not match:
        print(f"❌ No agent found named '{agent_name}'. Did you build it first?")
        logger.info(f"❌ No agent found named '{agent_name}'. Did you build it first?")
        sys.exit(1)

    agent_id = match["agent_id"]
    dest_dir = REGISTRY_DIR / "shared" / agent_id / "files"
    dest_dir.mkdir(parents=True, exist_ok=True)

    src = Path(src_path)
    if not src.exists() or not src.is_file():
        logger.info(f"❌ File not found: {src_path}")
        print(f"❌ File not found: {src_path}")
        sys.exit(1)

    dst = dest_dir / src.name
    shutil.copy2(src, dst)

    # canonical path to be sent to formatter handler
    relative_path = f"shared/{agent_id}/files/{src.name}"

    print(f"📁 File stored persistently → {dst}")
    print("🔑 Use in payload:")
    print(f'    {{"file_path": "{relative_path}"}}')
    print("💡 This survives agent rebuilds.")

    logger.info(f"📁 File stored persistently → {dst}")
    logger.info("🔑 Use in payload:")
    logger.info(f'    {{"file_path": "{relative_path}"}}')
    logger.info("💡 This survives agent rebuilds.")


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
        logger.info(f"❌ No agent found matching '{ref}'")
        sys.exit(1)

    yaml_path = REGISTRY_AGENTS / match["agent_id"] / "agent.yaml"
    logger.info("📄 Agent metadata:\n")
    logger.info(yaml.safe_dump(yaml.safe_load(yaml_path.read_text()), sort_keys=False))
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
        logger.info(f"❌ No agent found matching '{ref}'")
        print(f"❌ No agent found matching '{ref}'")
        sys.exit(1)

    agent_name = match["agent_name"]
    agent_id = match["agent_id"]
    agent_path = REGISTRY_AGENTS / agent_id

    confirm = input(f"⚠️ Delete agent '{agent_name}' (ID {agent_id}) permanently? y/N: ")
    if confirm.lower() not in ("y", "yes"):
        logger.info("❎ Cancelled")
        print("❎ Cancelled")
        return

    # remove folder
    if agent_path.exists():
        shutil.rmtree(agent_path)

    # remove from index
    index = [a for a in index if a["agent_id"] != agent_id]
    save_agents_index(index)
    # ✅ NEW: Sync to SQLite
    try:
        sync_agents()
        logger.info("[sqlite_sync] completed")
    except Exception as e:
        print(f"⚠️  SQLite sync failed: {e}")
        logger.error(f"⚠️  SQLite sync failed: {e}")

    logger.info(f"🗑 Deleted agent '{agent_name}' ({agent_id})")
    logger.info("🔄 Restarting server to refresh agent registry...")

    print(f"🗑 Deleted agent '{agent_name}' ({agent_id})")
    print("🔄 Restarting server to refresh agent registry...")

    restart()


# ---------------------------------------------------------------------
# STOP MAIN SERVER
# ---------------------------------------------------------------------
def stop():
    pid = read_pid(MAIN_PID_FILE)
    if not pid:
        logger.info("ℹ️ No running Treehopper server found")
        print("ℹ️ No running Treehopper server found")
        return
    logger.info(f"🛑 Stopping Treehopper server (PID {pid}) ...")
    print(f"🛑 Stopping Treehopper server (PID {pid}) ...")
    kill_pid(pid)
    MAIN_PID_FILE.unlink(missing_ok=True)
    logger.info("✔ Stopped")
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
            logger.info(f"🛑 Stopping chain runtime {f.name} (PID {pid})")
            print(f"🛑 Stopping chain runtime {f.name} (PID {pid})")
            kill_pid(pid)
            f.unlink(missing_ok=True)
            stopped = True
    if not stopped:
        logger.info("ℹ️ No chain runtimes found")
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
        logger.info("Usage: treehopper chain <agent1> <agent2> ...")
        print("Usage: treehopper chain <agent1> <agent2> ...")
        sys.exit(1)

    agents = args
    chain_body = {"chain": [{"path": agent, "params": {}} for agent in agents]}

    ensure_server()
    r = requests.post(f"{BASE_URL}/api/v1/dev/chain", json=chain_body, headers=API_KEY)
    logger.info(r.text)
    print(r.text)


# inside some agents CLI module

AGENT_RUNTIME_PREFIX = "det_agent_"


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex(("127.0.0.1", port)) == 0


def derive_agent_port(agent_id: str) -> int:
    """
    Deterministic, non-overlapping-ish ports for agents:
    22000–23999 range based on agent_id hash.
    """
    h = abs(hash(agent_id))
    return 22000 + (h % 2000)


def resolve_agent_meta(agent_name_or_id: str) -> dict:
    index = load_agents_index()
    # try name first
    for a in index:
        if a["agent_name"] == agent_name_or_id or a["agent_id"] == agent_name_or_id:
            return a
    logger.info(f"❌ Agent not found: {agent_name_or_id}")
    print(f"❌ Agent not found: {agent_name_or_id}")
    sys.exit(1)


def agent_run_detached(
    ref: str, port_override: int | None = None, bg: bool = True
) -> None:
    """
    Start a detached agent runtime for the given agent.
    - If already running: print existing PID + correct port and return.
    - If explicit port provided and in-use: exit with error (Option A).
    - If bg is False: run once (start, execute when CLI calls /run, then stop).
      If bg is True: leave runtime running.
    """
    meta = resolve_agent_meta(ref)
    agent_id = meta["agent_id"]
    port = derive_agent_port(agent_id) if port_override is None else port_override
    # url = f"http://localhost:{port}"
    pid_file = RUNTIME_DIR / f"{AGENT_RUNTIME_PREFIX}{agent_id}.pid"

    # If explicit port requested and already in use -> strict error
    if port_override is not None and is_port_in_use(port):
        logger.info(f"❌ Port {port} is already in use. Choose a different port.")
        print(f"❌ Port {port} is already in use. Choose a different port.")
        sys.exit(1)

    # Check existing runtime and report its actual port (if any)
    existing_pid, existing_port = read_pid_and_port(pid_file)
    if existing_pid:
        try:
            os.kill(existing_pid, 0)  # check process still exists
            # If port was written earlier, use it; otherwise use derived port
            use_port = existing_port or port
            logger.info(
                f"ℹ️ Agent runtime already running for '{meta['agent_name']}' "
                f"(PID {existing_pid}) on http://localhost:{use_port}"
            )
            logger.info(
                f"📌 POST   http://localhost:{use_port}/api/v1/{meta['agent_name']}/run"
            )
            logger.info(
                f"🔍 Health http://localhost:{use_port}/api/v1/{meta['agent_name']}/health"
            )

            print(
                f"ℹ️ Agent runtime already running for '{meta['agent_name']}' "
                f"(PID {existing_pid}) on http://localhost:{use_port}"
            )
            print(
                f"📌 POST   http://localhost:{use_port}/api/v1/{meta['agent_name']}/run"
            )
            print(
                f"🔍 Health http://localhost:{use_port}/api/v1/{meta['agent_name']}/health"
            )
            return
        except ProcessLookupError:
            # stale PID file
            pid_file.unlink(missing_ok=True)
            existing_pid = None

    # Start runtime
    print(
        f"🚀 Starting detached agent runtime for '{meta['agent_name']}' on http://localhost:{port}"
    )
    logger.info(
        f"🚀 Starting detached agent runtime for '{meta['agent_name']}' on http://localhost:{port}"
    )
    env = os.environ.copy()
    env["PROD"] = "1"
    env["AGENT_NAME"] = meta["agent_name"]
    env = maybe_inject_dev_pythonpath(env)

    LOG_FILE = RUNTIME_DIR / f"agent_{meta['agent_name']}-{agent_id}.log"

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "treehopper.agent_runtime_app:app",
            "--host",
            "0.0.0.0",
            "--port",
            str(port),
        ],
        env=env,
        stdout=open(LOG_FILE, "w"),
        stderr=subprocess.STDOUT,
    )
    # persist pid + port so future starts can report correct port
    write_pid(pid_file, proc.pid, port)

    logger.info(f"📝 Agent runtime logs → {LOG_FILE}")
    logger.info(f"📌 POST   http://localhost:{port}/api/v1/{meta['agent_name']}/run")
    logger.info(f"🔍 Health http://localhost:{port}/api/v1/{meta['agent_name']}/health")

    print(f"📝 Agent runtime logs → {LOG_FILE}")
    print(f"📌 POST   http://localhost:{port}/api/v1/{meta['agent_name']}/run")
    print(f"🔍 Health http://localhost:{port}/api/v1/{meta['agent_name']}/health")

    # If caller wanted run-once (bg=False), do not keep runtime alive indefinitely.
    # The CLI caller should call /run; after that the caller may stop the runtime with `treehopper agent stop`.
    # If you want the CLI to automatically make one request and then stop, implement that at the caller side.
    # (We persist the PID+port and return; the test script will call the /run endpoint.)


def agent_stop(ref: str) -> None:
    meta = resolve_agent_meta(ref)
    print(f"This will stop detached agent '{meta['agent_name']}'")
    agent_id = meta["agent_id"]
    pid_file = RUNTIME_DIR / f"{AGENT_RUNTIME_PREFIX}{agent_id}.pid"
    print(pid_file)
    pid = read_pid(pid_file)

    if not pid:
        logger.info(f"ℹ️ No detached runtime for agent '{meta['agent_name']}'")
        print(f"ℹ️ No detached runtime for agent '{meta['agent_name']}'")
        return

    logger.info(f"🛑 Stopping agent runtime '{meta['agent_name']}' (PID {pid})")
    print(f"🛑 Stopping agent runtime '{meta['agent_name']}' (PID {pid})")
    kill_pid(pid)
    pid_file.unlink(missing_ok=True)
    logger.info("✔ Stopped")
    print("✔ Stopped")


def view_logs_cmd(args_list: list[str]) -> None:
    # 1. Update the parser to accept --level
    parser = argparse.ArgumentParser(description="View Treehopper logs", add_help=False)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--tail", type=int)
    parser.add_argument("--level", type=str)  # <--- Add this line

    try:
        args = parser.parse_args(args_list)
        # 2. Ensure the level is passed to the implementation function
        run_view_logs(tail=args.tail, show_all=args.all, level_filter=args.level)
    except Exception as e:
        # If argparse fails, it often prints its own error,
        # but we catch other exceptions here.
        print(f"❌ Error parsing log arguments: {e}")


def view_db_cmd(args_list: list[str]) -> None:
    parser = argparse.ArgumentParser(
        description="Inspect Treehopper database", add_help=False
    )
    parser.add_argument("--show-tables", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--table", type=str)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--search", "-s", type=str)
    parser.add_argument("--plain", action="store_true")
    parser.add_argument("--json", action="store_true")  # Added this

    try:
        args = parser.parse_args(args_list)
        run_view_db(
            show_tables=args.show_tables,
            table=args.table,
            limit=args.limit,
            search=args.search,
            show_all=args.all,
            as_tables=not args.plain and not args.json,
            as_json=args.json,
        )
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        print(f"❌ Error: {e}")


# ---------------------------------------------------------------------
# TREEHOPPER HELP
# ---------------------------------------------------------------------


def print_help():
    logger.info(help_string)
    print(help_string)


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------
def main() -> None:
    logger.info("[treehopper_cli] Initialising TreehopperAI setup")
    print("[treehopper_cli] Initialising TreehopperAI setup")
    # dbInit = DBInitializer()
    # dbInit.init_db()
    setup_treehopper()

    # ✅ SAFE, FAST, ONE-TIME
    if not os.getenv("TH_TEST_MODE"):
        logger.info("[treehopper_cli] Ensuring all directories exists")
        ensure_dirs()
        print("[treehopper_cli] Ensuring maintaince checks and actions")
        logger.info("[treehopper_cli] Ensuring maintaince checks and actions")
        startup_maintenance()

    if len(sys.argv) == 1:
        print_whatis()
        return
    if sys.argv[1] in ("whatis", "about"):
        print_whatis()
        return
    logger.info("Starting treehopper")
    if len(sys.argv) < 2:
        print_help()
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd == "help":
        logger.info("help command")
        print_help()
    elif cmd == "run" or cmd == "start":
        logger.info("run command")
        bg = "--bg" in sys.argv
        run(background=bg)

    elif cmd == "stop":
        logger.info("stop command")
        if len(sys.argv) > 2 and sys.argv[2] == "ui":
            stop_ui()
        else:
            stop()

    elif cmd == "restart":
        logger.info("restart command")
        restart()
    elif cmd == "list_agents":
        logger.info("agent list command")
        list_agents()
    elif cmd == "list_chains":
        logger.info("chains list command")
        list_chains()

    elif cmd == "call":
        logger.info("call command")
        parser = argparse.ArgumentParser(
            description="Call an agent endpoint.", add_help=False
        )
        # We need to know where the path is and where the data is
        parser.add_argument(
            "path", help="The API endpoint path, e.g., /api/v1/agents/my_agent"
        )
        # Optional file argument
        parser.add_argument(
            "--payload-file", help="Path to a JSON file containing the request payload."
        )
        # Optional inline JSON argument (old way)
        parser.add_argument(
            "json_payload", nargs="?", default=None, help="Inline JSON payload string."
        )

        # Parse arguments starting from sys.argv[2]
        try:
            args = parser.parse_args(sys.argv[2:])
        except SystemExit:
            # Handle case where only 'th call' is given or help is requested
            return

        json_data = None

        if args.payload_file:
            # Case 1: Load from file
            if not os.path.exists(args.payload_file):
                print(f"❌ Error: Payload file not found at {args.payload_file}")
                return
            with open(args.payload_file, "r") as f:
                try:
                    json_data = json.load(f)
                except json.JSONDecodeError:
                    print(f"❌ Error: Invalid JSON format in file {args.payload_file}")
                    return

        elif args.json_payload:
            # Case 2: Load from inline string (original way)
            try:
                json_data = json.loads(args.json_payload)
            except json.JSONDecodeError:
                print("❌ Error: Invalid JSON string provided.")
                return

        else:
            print(
                "❌ Error: Must provide a JSON payload (inline string or --payload-file)."
            )
            return

        # Call the agent
        call(args.path, json_data)
    elif cmd == "init":
        logger.info("initialising agent command")
        if len(sys.argv) != 3:
            print("❌ Usage: treehopper init <agent_name>")
            sys.exit(1)
        agent_name = validate_agent_name(sys.argv[2])
        init_agent(agent_name)
    elif cmd == "lint":
        logger.info("lint command")
        lint_agent(sys.argv[2])
    elif cmd == "build":
        logger.info("build command")
        build_agent(sys.argv[2])
    elif cmd == "chains" or cmd == "agents":
        logger.info(f"{cmd} command handler")

        # Check for minimum arguments: th <command> <action>
        if len(sys.argv) < 3:
            print(f"❌ Usage: treehopper {cmd} <action> [arg]")
            sys.exit(1)

        sub = cmd  # This is the top-level command, e.g., "chains" or "agents"
        action = sys.argv[2].lower()
        arg = sys.argv[3] if len(sys.argv) > 3 else None
        print(f"Args - {arg}")
        # This resolves the F821 errors for 'sub', 'action', and 'arg'
        if sub == "chains":
            if action == "status":
                chains_status()
            # elif action == "restart":
            #     chains_restart(arg if arg != "--all" else None)
            else:
                print(f"Unknown chains subcommand: {action}")
                sys.exit(1)

        elif sub == "agents":
            if action == "status":
                agents_status()
            # elif action == "restart":
            #     agents_restart(arg if arg != "--all" else None)
            else:
                print(f"Unknown agents subcommand: {action}")
                sys.exit(1)
    elif cmd == "chain" and len(sys.argv) > 2 and sys.argv[2] == "stop":
        logger.info("chain with stop command")
        stop_chain()
    elif cmd == "chain":
        logger.info("chain command")
        from .treehopper_chains import chain_entry

        chain_entry(sys.argv[2:])
    elif cmd == "status":
        logger.info("status command")
        status()
    elif cmd == "agent":
        logger.info("agent command")

        if len(sys.argv) < 3:
            print("Usage: treehopper agent <subcommand>")
            print("\nSubcommands:")
            print("  create <n> --from-template <t>  Create agent from template")
            print("  build <n>                       Build and deploy agent")
            print("  lint <n>                        Lint agent code")
            print("  templates                       List available templates")
            print("  start <n> --detached            Start detached runtime")
            print("  stop <n>                        Stop detached runtime")
            print("  info <n>                        Show agent metadata")
            print("  delete <n>                      Delete agent")
            sys.exit(1)

        sub = sys.argv[2].lower()

        # NEW: th agent create --from-template
        if sub == "create":
            logger.info("agent create command")

            if len(sys.argv) < 5 or "--from-template" not in sys.argv:
                print(
                    "Usage: th agent create <agent_name> --from-template <template_name>"
                )
                print("\nExample:")
                print(
                    "  th agent create my_email_listener --from-template email_listener"
                )
                print("\nList templates:")
                print("  th agent templates")
                sys.exit(1)

            agent_name = sys.argv[3]
            template_idx = sys.argv.index("--from-template")

            if template_idx + 1 >= len(sys.argv):
                print("❌ Missing template name after --from-template")
                sys.exit(1)

            template_name = sys.argv[template_idx + 1]
            agent_create_from_template(agent_name, template_name)

        # NEW: th agent build (alias)
        elif sub == "build":
            logger.info("agent build command (alias)")
            if len(sys.argv) < 4:
                print("Usage: th agent build <agent_name>")
                sys.exit(1)
            build_agent(sys.argv[3])

        # NEW: th agent lint (alias)
        elif sub == "lint":
            logger.info("agent lint command (alias)")
            if len(sys.argv) < 4:
                print("Usage: th agent lint <agent_name>")
                sys.exit(1)
            lint_agent(sys.argv[3])

        # NEW: th agent templates
        elif sub == "templates":
            logger.info("agent templates command")
            list_templates()

        # EXISTING: th agent start --detached
        elif sub == "start" and "--detached" in sys.argv:
            logger.info("agent start detached command")
            if len(sys.argv) < 4:
                print("Usage: treehopper agent start <n> --detached [--port <port>]")
                sys.exit(1)

            ref = sys.argv[3]
            port_override = None

            if "--port" in sys.argv:
                logger.info("agent port command")
                idx = sys.argv.index("--port")
                if idx + 1 >= len(sys.argv):
                    print("❌ Missing value for --port")
                    logger.info("❌ Missing value for --port")
                    sys.exit(1)
                try:
                    port_override = int(sys.argv[idx + 1])
                except ValueError:
                    logger.error("❌ Invalid value for --port (must be integer)")
                    print("❌ Invalid value for --port (must be integer)")
                    sys.exit(1)

            agent_run_detached(ref, port_override)

        # EXISTING: th agent stop
        elif sub == "stop":
            logger.info("agent stop command")
            if len(sys.argv) < 4:
                print("Usage: treehopper agent stop <name|id>")
                sys.exit(1)
            agent_stop(sys.argv[3])

        # EXISTING: th agent info
        elif sub == "info":
            logger.info("agent info command")
            if len(sys.argv) < 4:
                print("Usage: treehopper agent info <ref>")
                sys.exit(1)
            agent_info(sys.argv[3])

        # EXISTING: th agent delete
        elif sub == "delete":
            logger.info("agent delete command")
            if len(sys.argv) < 4:
                print("Usage: treehopper agent delete <ref>")
                sys.exit(1)
            delete_agent(sys.argv[3])

        else:
            print(f"Unknown agent subcommand: {sub}")
            logger.info(f"Unknown agent subcommand: {sub}")
            print("\nAvailable subcommands:")
            print("  create, build, lint, templates, start, stop, info, delete")
            sys.exit(1)

    elif cmd == "push-file":
        if len(sys.argv) != 4:
            logger.info("Usage: treehopper push-file <agent_name> <path>")
            print("Usage: treehopper push-file <agent_name> <path>")
            sys.exit(1)
        push_file(sys.argv[2], sys.argv[3])
    elif cmd == "clean":
        logger.info("agent clean command")
        clean_main()
    elif cmd == "launch":
        if len(sys.argv) < 3:
            print("Usage: treehopper launch ui")
            sys.exit(1)

        target = sys.argv[2].lower()

        if target == "ui":
            launch_ui()
        else:
            print(f"Unknown launch target: {target}")
            sys.exit(1)
    elif cmd == "admin":
        logger.info("admin command")
        if len(sys.argv) < 3:
            print("Usage: treehopper admin <action>")
            sys.exit(1)
        admin_entry(sys.argv[2:])

    elif cmd == "setup":
        logger.info("setup command")
        success = setup_treehopper()
        sys.exit(0 if success else 1)

    elif cmd == "workspace":
        if len(sys.argv) < 3:
            print("Usage: th workspace <subcommand>")
            print("  create <n>  - Create empty directory")
            print("  info        - Show current directory info")
            sys.exit(1)

        sub = sys.argv[2]

        if sub == "create":
            if len(sys.argv) < 4:
                print("Usage: th workspace create <n>")
                sys.exit(1)
            workspace_create(sys.argv[3])

        elif sub == "info":
            workspace_info()

        else:
            print(f"Unknown: {sub}")
            sys.exit(1)

    elif cmd == "view":
        logger.info("view command")
        if len(sys.argv) < 3:
            print("Usage: treehopper view db [--show-tables] [--table <name>]")
            sys.exit(1)

        target = sys.argv[2].lower()
        if target == "db":
            # Pass everything after 'th view db' to the handler
            view_db_cmd(sys.argv[3:])
        elif target == "logs":
            view_logs_cmd(sys.argv[3:])  # Added this
        else:
            print(f"Unknown view target: {target}")

    elif cmd == "show":
        if len(sys.argv) < 3:
            print("Usage: th show [root|pids]")
            sys.exit(1)

        target = sys.argv[2].lower()

        if target == "root":
            show_root_tree()
        elif target == "pids":
            show_pids()
        else:
            print(f"Unknown show target: {target}")

    else:
        logger.info(f"Unknown command: {cmd}")
        print(f"Unknown command: {cmd}")
        print_help()
        sys.exit(1)
