# treehopper/th_config.py
import os
from pathlib import Path

# Resolve HOME
HOME = Path.home()

# Allow runtime environment overrides (critical for cancellation correctness)
# TH_ROOT = Path(os.getenv("TREEHOPPER_TH_ROOT", str(HOME / ".treehopper")))
# Pick up env vars if set, otherwise default
TH_ROOT = Path(os.getenv("TH_ROOT", str(HOME / ".treehopper")))
# TH_ROOT = Path.home() / ".treehopper"
# Registry layout
REGISTRY_DIR = TH_ROOT / "registry"
REGISTRY_AGENTS = REGISTRY_DIR / "agents"
REGISTRY_AGENTS_INDEX = REGISTRY_DIR / "agents.json"
CHAINS_DIR = REGISTRY_DIR / "chains"
CHAINS_INDEX = REGISTRY_DIR / "chains.json"

# Runtime layout — ALSO override-able
# RUNTIME_DIR = TH_ROOT / "runtime"
RUNTIME_DIR = Path(os.getenv("RUNTIME_DIR", str(TH_ROOT / "runtime")))
CANCEL_DIR = RUNTIME_DIR / "cancels"
CANCEL_DIR.mkdir(parents=True, exist_ok=True)
MAIN_PID_FILE = RUNTIME_DIR / "main_server.pid"

# Chain runtime PID prefix
CHAIN_PID_PREFIX = "det_chain_"

# HTTP defaults
API_KEY = {"x-api-key": "demo-key-123"}
MAIN_PORT = int(os.getenv("TH_PORT", "1567"))
BASE_URL = f"http://localhost:{MAIN_PORT}"

# Version
VERSION = "0.1.0"

# Cancellation request timeout seconds
CANCEL_TIMEOUT = 10  # safe but configurable

# Subscription path
SUBSCRIPTION_FILE = TH_ROOT / "subscription_id.txt"

# Ensure directories exist on import
for _d in (TH_ROOT, REGISTRY_DIR, REGISTRY_AGENTS, CHAINS_DIR, RUNTIME_DIR, CANCEL_DIR):
    try:
        _d.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


# -------------------------------------------------------------------
# Log Constants
# -------------------------------------------------------------------

DEFAULT_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
DEFAULT_BACKUP_COUNT = 10  # Keep last 10 files
DEFAULT_LOG_NAME = "treehopper"
