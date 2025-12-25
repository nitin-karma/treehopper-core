# treehopper/utils/commons.py
import json
import uuid
from typing import Dict, List, Any
from treehopper.th_config import (
    REGISTRY_AGENTS_INDEX,
    CHAINS_INDEX,
    REGISTRY_DIR,
    CHAINS_DIR,
    RUNTIME_DIR,
    SUBSCRIPTION_FILE,
)


# def load_chains_index() -> list[dict]:
#     if not CHAINS_INDEX.exists():
#         return []
#     try:
#         return json.loads(CHAINS_INDEX.read_text())
#     except Exception:
#         return []


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


def ensure_registry_dirs() -> None:
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    CHAINS_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


# def ensure_registry_dirs() -> None:
#     REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
#     REGISTRY_AGENTS.mkdir(parents=True, exist_ok=True)


def get_or_create_subscription_id() -> str:
    ensure_registry_dirs()
    if SUBSCRIPTION_FILE.exists():
        return SUBSCRIPTION_FILE.read_text().strip()
    sid = str(uuid.uuid4())
    SUBSCRIPTION_FILE.write_text(sid)
    return sid


# def load_agents_index() -> list[dict]:
#     ensure_registry_dirs()
#     if not REGISTRY_AGENTS_INDEX.exists():
#         return []
#     try:
#         return json.loads(REGISTRY_AGENTS_INDEX.read_text())
#     except json.JSONDecodeError as e:
#         logger.error(f"{str(e)}")
#         return []


def save_agents_index(index: list[dict]) -> None:
    ensure_registry_dirs()
    REGISTRY_AGENTS_INDEX.write_text(json.dumps(index, indent=2))
