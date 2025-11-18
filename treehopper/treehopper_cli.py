import json
import os
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


# ---------------------------------------------------------------------
# SERVER HELPERS
# ---------------------------------------------------------------------
def run(th_port: int = int(os.getenv("TH_PORT", 1560))) -> None:
    is_test = bool(os.getenv("PYTEST_CURRENT_TEST") or os.getenv("TH_TEST_MODE"))
    uvicorn.run(
        "treehopper.treehopper:app",
        host="0.0.0.0",
        port=th_port,
        reload=not (PROD or is_test),  # 🔥 prevent reload in PROD and TEST
    )


def restart(th_port: int = 1560) -> None:
    print("🔄 Restarting Treehopper server...")

    # kill uvicorn running on 1560
    subprocess.run(["pkill", "-f", f"uvicorn.*{th_port}"], stderr=subprocess.DEVNULL)

    env = os.environ.copy()
    env["PROD"] = "1"  # disable reload

    # start fresh server
    subprocess.Popen(["treehopper", "run"], env=env)

    # wait for health
    for _ in range(40):
        time.sleep(0.25)
        try:
            r = requests.get(
                f"http://localhost:{th_port}/api/v1/sys/health", timeout=0.2
            )
            if r.status_code == 200:
                print("🚀 Treehopper restarted")
                return
        except Exception:
            continue

    print("⚠️ Warning: server restart did not confirm health but continuing anyway")


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
    if (PACKAGE_AGENTS_DIR / f"{agent_name}.py").exists():
        return True
    ensure_registry_dirs()
    index = load_agents_index()
    return any(a["agent_name"] == agent_name for a in index)


def init_agent(agent_name: str) -> None:
    target_dir = Path.cwd() / agent_name
    if target_dir.exists():
        print(f"❌ Directory '{agent_name}' already exists here.")
        sys.exit(1)
    if agent_name_exists(agent_name):
        print(f"❌ Agent '{agent_name}' already exists. Choose another name.")
        sys.exit(1)

    ensure_registry_dirs()
    subscription_id = get_or_create_subscription_id()
    agent_id = f"{agent_name}-{uuid.uuid4().hex[:8]}"

    target_dir.mkdir(parents=True, exist_ok=False)

    (target_dir / "agent.yaml").write_text(
        yaml.safe_dump(
            {
                "agent_name": agent_name,
                "agent_id": agent_id,
                "subscription_id": subscription_id,
                "entrypoint": f"/{agent_name}",
                "chain_ids": [],
                "description": f"{agent_name} agent",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    (target_dir / "schema.py").write_text(
        f"""from pydantic import BaseModel

class {agent_name.capitalize()}Request(BaseModel):
    name: str
""",
        encoding="utf-8",
    )

    # 🔥 FINAL — primitive signature for compatibility with chain + Swagger JSON body
    (target_dir / "handler.py").write_text(
        f"""from fastapi import Body
from fastapi.responses import JSONResponse
from treehopper.treehopper import agent
from .schema import {agent_name.capitalize()}Request

class {agent_name.capitalize()}Agent:
    async def run(self, name: str, short: bool = False) -> dict:
        if short:
            return {{"message": f"{{name}}!"}}
        return {{"message": f"Hello {{name}} from {agent_name} agent!"}}

@agent("{agent_name}", method="POST", goal="Example agent created via `treehopper init`")
async def handle(request: {agent_name.capitalize()}Request = Body(None), name: str | None = None, short: bool = False):
    ag = {agent_name.capitalize()}Agent()
    if name:
        return JSONResponse(await ag.run(name, short))
    if request and request.name:
        return JSONResponse(await ag.run(request.name, short))
    return JSONResponse({{"error": "Missing name"}}, status_code=400)
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
    validate_agent_yaml(agent_dir)

    handler_path = agent_dir / "handler.py"
    if not handler_path.exists():
        print("❌ handler.py missing")
        sys.exit(1)

    tree = ast.parse(handler_path.read_text())

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "handle":
            params = [p.arg for p in node.args.args]
            if "request" in params:
                print("❌ Remove `request:` param. Use primitive args (name: str).")
                sys.exit(1)
            if "name" not in params:
                print("❌ Handler must accept: name: str")
                sys.exit(1)

    print(f"✅ Lint passed for {agent_ref}")


def build_agent(agent_ref: str) -> None:
    agent_dir = Path.cwd() / agent_ref
    if not agent_dir.exists() or not agent_dir.is_dir():
        print(f"❌ Agent folder '{agent_ref}' does not exist")
        sys.exit(1)

    cfg = validate_agent_yaml(agent_dir)
    agent_name = cfg["agent_name"]
    agent_id = cfg["agent_id"]
    entrypoint = cfg["entrypoint"]

    ensure_registry_dirs()
    index = load_agents_index()

    target_dir = REGISTRY_AGENTS / agent_id
    if target_dir.exists():
        shutil.rmtree(target_dir)
    shutil.copytree(agent_dir, target_dir)

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
        }
    )
    save_agents_index(index)

    print(f"✅ Built agent '{agent_name}' → {target_dir}")
    print("📌 Call via:")
    print(f'  treehopper call /api/v1/agents/{agent_name} \'{{"name": "Nitin"}}\'')


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


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------
def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage:\n"
            "  treehopper run\n"
            "  treehopper call <path> '<json>'\n"
            "  treehopper list\n"
            "  treehopper init <agent_name>\n"
            "  treehopper build <agent_folder>\n"
            "  treehopper lint <agent_folder>\n"
            "  treehopper agent info <agent_name | agent_id>\n"
        )
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "run":
        run()
    elif cmd == "restart":
        restart()
    elif cmd == "call":
        call(sys.argv[2], json.loads(sys.argv[3]))
    elif cmd == "list":
        list_agents()
    elif cmd == "init":
        init_agent(sys.argv[2])
    elif cmd == "lint":
        lint_agent(sys.argv[2])
    elif cmd == "build":
        build_agent(sys.argv[2])
    elif cmd == "agent" and sys.argv[2] == "info":
        agent_info(sys.argv[3])
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
