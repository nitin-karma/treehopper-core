import sys, json, requests
from tabulate import tabulate
import os
from dotenv import load_dotenv
load_dotenv()

API_KEY = {"x-api-key": "demo-key-123"}
BASE_URL = "http://localhost:1560"


def run(th_port=1560):
    import uvicorn
    if os.getenv("PROD") == "1":
        uvicorn.run("treehopper.treehopper:app", host="0.0.0.0", port=th_port, reload=False)
    else:
        uvicorn.run("treehopper.treehopper:app", host="0.0.0.0", port=th_port, reload=True)


def ensure_server():
    try:
        requests.get(f"{BASE_URL}/agents", headers=API_KEY, timeout=1)
    except Exception:
        print("⚠️ API server not running. Starting it now...")
        import subprocess, time
        subprocess.Popen(["treehopper", "run"])
        time.sleep(2)


def call(path, params):
    ensure_server()

    r = requests.get(f"{BASE_URL}/agents", headers=API_KEY)
    r.raise_for_status()
    agent_list = r.json()

    method = next((a["method"] for a in agent_list if a["path"] == path), None)
    if not method:
        print(f"❌ Agent not found: {path}")
        return

    if method == "GET":
        response = requests.get(f"{BASE_URL}{path}", params=params, headers=API_KEY)
    else:
        response = requests.post(f"{BASE_URL}{path}", json=params, headers=API_KEY)

    print(response.text)


def list_agents():
    r = requests.get(f"{BASE_URL}/agents", headers=API_KEY)
    agents = r.json()
    table_data = [[agent["path"], agent["goal"]] for agent in agents]
    print(tabulate(table_data, headers=["AGENT PATH", "GOAL"], tablefmt="grid"))


def main():
    cmd = sys.argv[1]

    if cmd == "run":
        run()

    elif cmd == "call":
        if len(sys.argv) < 4:
            print('Usage: treehopper call "/greet" \'{"name": "Nitin"}\'')
            sys.exit(1)
        path = sys.argv[2]
        params = json.loads(sys.argv[3])
        call(path, params)

    elif cmd == "list":
        list_agents()
