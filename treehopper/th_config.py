# treehopper/th_config.py
import os
from pathlib import Path
from typing import Literal


HOME = Path.home()

# Allow runtime environment overrides (critical for cancellation correctness)
# TH_ROOT = Path(os.getenv("TREEHOPPER_TH_ROOT", str(HOME / ".treehopper")))
# Pick up env vars if set, otherwise default

TH_ROOT = Path(os.getenv("TH_ROOT", str(HOME / ".treehopper")))

# TH_ROOT = Path(
#     os.getenv(
#         "TREEHOPPER_HOME",        # ✅ canonical
#         os.getenv(
#             "TREEHOPPER_TH_ROOT", # backward compatible
#             os.getenv(
#                 "TH_ROOT",        # legacy
#                 str(HOME / ".treehopper")
#             )
#         )
#     )
# ).resolve()

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
# CANCEL_DIR.mkdir(parents=True, exist_ok=True)
MAIN_PID_FILE = RUNTIME_DIR / "main_server.pid"

# Chain runtime PID prefix
CHAIN_PID_PREFIX = "det_chain_"

# HTTP defaults
DEFAULT_API_KEY = "demo-key-123"
API_KEY = {"x-api-key": DEFAULT_API_KEY}
MAIN_PORT = int(os.getenv("TH_PORT", "1567"))
BASE_URL = f"http://localhost:{MAIN_PORT}"

# Version
VERSION = "0.1.0"

# Cancellation request timeout seconds
CANCEL_TIMEOUT = 30  # safe but configurable

# Subscription path
SUBSCRIPTION_FILE = TH_ROOT / "subscription_id.txt"

# Ensure directories exist on import
# for _d in (TH_ROOT, REGISTRY_DIR, REGISTRY_AGENTS, CHAINS_DIR, RUNTIME_DIR, CANCEL_DIR):
#     try:
#         _d.mkdir(parents=True, exist_ok=True)
#     except Exception:
#         pass

ARCHIVE_DIR = Path(TH_ROOT) / "archive"


def ensure_dirs():
    for _d in (
        TH_ROOT,
        REGISTRY_DIR,
        REGISTRY_AGENTS,
        CHAINS_DIR,
        RUNTIME_DIR,
        CANCEL_DIR,
        ARCHIVE_DIR,
    ):
        _d.mkdir(parents=True, exist_ok=True)


# -------------------------------------------------------------------
# Log Constants
# -------------------------------------------------------------------

DEFAULT_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
DEFAULT_BACKUP_COUNT = 10  # Keep last 10 files
DEFAULT_LOG_NAME = "treehopper"


# Multi-step chain defaults
DEFAULT_MAX_STEPS_PER_CHAIN = int(os.getenv("DEFAULT_MAX_STEPS_PER_CHAIN", 8))
DEFAULT_MAX_PARALLEL_PER_STEP = int(os.getenv("DEFAULT_MAX_PARALLEL_PER_STEP", 5))

# Backward compatibility aliases
MAX_STEPS_PER_CHAIN = DEFAULT_MAX_STEPS_PER_CHAIN
MAX_PARALLEL_PER_STEP = DEFAULT_MAX_PARALLEL_PER_STEP

# ======================================================================
# BUILTIN MERGE STRATEGIES (NOT AGENTS)
# ======================================================================

BUILTIN_MERGE_AGENTS = {
    "smart_data_aggregator": "builtin_merge_parallel",
    "default": "builtin_merge_parallel",
}

BUILTIN_AGENTS = {"language_detector"}


# =========================================================================
# BUILTIN Event Types for websockets mainly used in detached chain runtime
# =========================================================================

EventType = Literal[
    "run_start",
    "run_completed",
    "run_cancelled",
    "step_start",
    "step_complete",
    "agent_start",
    "agent_complete",
    "parallel_complete",
    "merge_complete",
    "route_taken",
]


# treehopper/websockets/schema_guard.py

ALLOWED_EVENT_TYPES = {
    "step_start",
    "step_complete",
    "agent_start",
    "agent_complete",
    "parallel_complete",
    "merge_complete",
    "route_taken",
    "run_completed",
    "run_cancelled",
}

REQUIRED_FIELDS = {
    "step_start": ["step_id"],
    "step_complete": ["step_id"],
    "agent_start": ["step_id", "agent"],
    "agent_complete": ["step_id", "agent"],
    "parallel_complete": ["step_id", "agents"],
    "merge_complete": ["step_id", "merge_agent"],
    "route_taken": ["from_step", "to_step"],
    "run_completed": ["status"],
    "run_cancelled": [],
}


ASCII_BANNER = r"""
████████╗██████╗ ███████╗███████╗██╗  ██╗ ██████╗ ██████╗ ██████╗ ███████╗██████╗  █████╗ ██╗
╚══██╔══╝██╔══██╗██╔════╝██╔════╝██║  ██║██╔═══██╗██╔══██╗██╔══██╗██╔════╝██╔══██╗██╔══██╗██║
   ██║   ██████╔╝█████╗  █████╗  ███████║██║   ██║██████╔╝██████╔╝█████╗  ██████╔╝███████║██║
   ██║   ██╔══██╗██╔══╝  ██╔══╝  ██╔══██║██║   ██║██╔═══╝ ██╔═══╝ ██╔══╝  ██╔══██╗██╔══██║██║
   ██║   ██║  ██║███████╗███████╗██║  ██║╚██████╔╝██║     ██║     ███████╗██║  ██║██║  ██║██║
   ╚═╝   ╚═╝  ╚═╝╚══════╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝     ╚═╝     ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝

                        TreehopperAI v{version}
            Think Globally. Compute Locally. Execute Intelligently.
"""


# ==================
# BUILTIN UI Tool
# ==================
DEFAULT_UI_PORT = 8090
LOG_RENDER_LIMIT = 500
DASHBOARD_DB_NAME = "dashboard_config.db"
DB_DIR = "dashboard_db"
ROLES = ["admin", "developer"]
PERM = ["manage_users", "view_dashboard", "execute_chains"]
DASHBOARD_HEADER = "TreehopperDash"
ACCESS_TOKEN_EXPIRE_MINUTES = 600
LOG_SCHEDULE = ["1h", "24h", "7d"]


# =====================
# Maintainanace config
# =====================
DB_MAX_MB = 2048
DB_WARN_PCT = 80
DB_CRIT_PCT = 95

LIVE_DB_RETAIN_DAYS = 7
ARCHIVE_RETAIN_DAYS = 90

FILE_ROTATE_MAX_MB = 512
FILE_ROTATE_MAX_COUNT = 1000
