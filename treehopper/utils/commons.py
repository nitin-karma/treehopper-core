# treehopper/utils/commons.py
import re
import json
import uuid

# import time
from datetime import datetime, timezone
from typing import Dict, List, Any
from treehopper.th_config import (
    REGISTRY_AGENTS_INDEX,
    CHAINS_INDEX,
    REGISTRY_DIR,
    CHAINS_DIR,
    RUNTIME_DIR,
    SUBSCRIPTION_FILE,
)
from treehopper.sync_to_sqlite import get_subscription, sync_subscription
from treehopper.logging import get_logger

logger = get_logger()


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


# def get_or_create_subscription_id() -> str:
#     ensure_registry_dirs()
#     if SUBSCRIPTION_FILE.exists():
#         return SUBSCRIPTION_FILE.read_text().strip()
#     sid = str(uuid.uuid4())
#     SUBSCRIPTION_FILE.write_text(sid)
#     return sid


# def get_or_create_subscription_id() -> str:
#     """
#     Get or create subscription ID
#     Phase 1: Now syncs to SQLite subscription table
#     """
#     ensure_registry_dirs()

#     # Check if file exists
#     if SUBSCRIPTION_FILE.exists():
#         sub_id = SUBSCRIPTION_FILE.read_text().strip()
#         logger.info(f"[get_or_create_subscription_id] subscription exists {sub_id}")
#         print(f"[get_or_create_subscription_id] subscription exists {sub_id}")

#     else:
#         # Create new subscription ID
#         sub_id = str(uuid.uuid4())
#         SUBSCRIPTION_FILE.write_text(sub_id)
#         logger.info(f"[get_or_create_subscription_id] Created new subscription {sub_id}")
#         print(f"[get_or_create_subscription_id] Created new subscription {sub_id}")

#     # ✅ Phase 1: Sync to SQLite
#     try:
#         # Get file creation time
#         created_timestamp = os.path.getctime(SUBSCRIPTION_FILE)
#         #created_at = datetime.fromtimestamp(created_timestamp).isoformat() + "Z"
#         created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

#         # Sync to database
#         sync_subscription(
#             subscription_id=sub_id, created_at=created_at, status="active", plan="trial"
#         )
#     except Exception as e:
#         # Don't fail if sync fails - file is source of truth
#         logger.error(f"[commons] Warning: Failed to sync subscription to SQLite: {e}")
#         print(f"[commons] Warning: Failed to sync subscription to SQLite: {e}")


#     return sub_id


def get_or_create_subscription_id() -> str:
    """
    Get or create subscription ID

    CRITICAL: Database is source of truth, not file!

    Logic:
    1. Check database first (source of truth)
    2. If DB has subscription:
       - Use it
       - Restore file if missing
    3. If DB is empty:
       - Check file
       - Or create new ID
       - Sync to database
    """
    ensure_registry_dirs()

    # ✅ STEP 1: Check DATABASE first (source of truth)
    try:
        existing_sub = get_subscription()
        if existing_sub:
            sub_id = existing_sub["subscription_id"]

            # Restore file if missing (file is cache of DB)
            if not SUBSCRIPTION_FILE.exists():
                SUBSCRIPTION_FILE.write_text(sub_id)
                print(f"[commons] Restored subscription_id.txt from database: {sub_id}")

            return sub_id
    except Exception as e:
        print(f"[commons] Warning: Could not query subscription from DB: {e}")

    # ✅ STEP 2: DB is empty - check file or create new
    if SUBSCRIPTION_FILE.exists():
        sub_id = SUBSCRIPTION_FILE.read_text().strip()
    else:
        # Create new subscription ID
        sub_id = str(uuid.uuid4())
        SUBSCRIPTION_FILE.write_text(sub_id)
        print(f"[commons] Created new subscription ID: {sub_id}")

    # ✅ STEP 3: Sync to database
    try:
        # Get file creation time
        # created_timestamp = os.path.getctime(SUBSCRIPTION_FILE)
        created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # Sync to database
        sync_subscription(
            subscription_id=sub_id, created_at=created_at, status="active", plan="trial"
        )
        print(f"[commons] Synced subscription to database: {sub_id}")
    except Exception as e:
        # Don't fail if sync fails
        print(f"[commons] Warning: Failed to sync subscription to SQLite: {e}")

    return sub_id


def save_agents_index(index: list[dict]) -> None:
    ensure_registry_dirs()
    REGISTRY_AGENTS_INDEX.write_text(json.dumps(index, indent=2))


# ---------------------------------------------------------------------
# REGISTRY / SUBSCRIPTION HELPERS
# ---------------------------------------------------------------------


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
