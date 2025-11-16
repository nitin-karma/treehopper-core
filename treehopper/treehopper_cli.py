import json
import os
import sys
import uvicorn
import requests
import subprocess
import time
from dotenv import load_dotenv
from tabulate import tabulate

load_dotenv()

API_KEY = {"x-api-key": "demo-key-123"}
BASE_URL = "http://localhost:1560"


def run(th_port=1560):
    """Start the Treehopper API server"""
    reload_flag = not os.getenv("PROD") == "1"
    uvicorn.run(
        "treehopper.treehopper:app",
        host="0.0.0.0",
        port=th_port,
        reload=reload_flag,
    )


def ensure_server():
    """Start the server if not already running"""
    try:
        requests.get(f"{BASE_URL}/api/v1/dev/agents", headers=API_KEY, timeout=1)
    except Exception:
        print("⚠️ API server not running. Starting it now...")
        subprocess.Popen(["treehopper", "run"])
        time.sleep(2)


def discover_method(path: str) -> str | None:
    """Ask API server what HTTP method the given agent expects"""
    r = requests.get(f"{BASE_URL}/api/v1/dev/agents", headers=API_KEY)
    r.raise_for_status()
    for agent in r.json():
        if agent["path"] == path:
            return agent["method"]
    return None


def call(path, params):
    """Invoke an agent remotely via API"""
    ensure_server()
    method = discover_method(path)
    if not method:
        print(f"❌ Agent not found: {path}")
        return

    if method.upper() == "GET":
        response = requests.get(f"{BASE_URL}{path}", params=params, headers=API_KEY)
    else:
        response = requests.post(f"{BASE_URL}{path}", json=params, headers=API_KEY)

    print(response.text)


def list_agents():
    """List all auto-discovered agents"""
    r = requests.get(f"{BASE_URL}/api/v1/dev/agents", headers=API_KEY)
    agents = r.json()
    table_data = [
        [a["path"], a["method"], ", ".join(a["tags"]), a["goal"]] for a in agents
    ]
    print(
        tabulate(
            table_data,
            headers=["AGENT PATH", "METHOD", "TAGS", "GOAL"],
            tablefmt="grid",
        )
    )


def main():
    """CLI entrypoint"""
    if len(sys.argv) < 2:
        print("Usage: treehopper [run | call | list]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "run":
        run()

    elif cmd == "call":
        if len(sys.argv) < 4:
            print('Usage: treehopper call "/api/v1/agents/greet" \'{"name": "Nitin"}\'')
            sys.exit(1)
        path = sys.argv[2]
        params = json.loads(sys.argv[3])
        call(path, params)

    elif cmd == "list":
        list_agents()
