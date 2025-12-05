"""
Filesystem-only cancellation module.

Writes/reads JSON cancel markers to CANCEL_DIR/<run_id>.cancel

Marker shape:
{
  "run_id": "chain-123456",
  "cancelled_at": 1700000000.123,
  "source": "cli" | "api" | "runtime",
  "modified_by": ["cli:PID", "runtime:PID"]
}
"""

import os
import json
import time
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, Set

from treehopper.th_config import CANCEL_DIR

# Ensure cancel dir exists
CANCEL_DIR.mkdir(parents=True, exist_ok=True)

# -----------------------------------------------------------------------------
# In-memory soft cache (not authoritative, but speeds local queries)
# -----------------------------------------------------------------------------
_REG_LOCK = asyncio.Lock()
ACTIVE_TASKS: Dict[str, asyncio.Task] = {}
ACTIVE_CHAIN_TASKS: Dict[str, Set[str]] = {}
ACTIVE_BATCH_TASKS: Dict[str, Set[str]] = {}

# “True” means marker exists; deletion is never expected, so no False values.
CANCEL_FLAGS: Dict[str, bool] = {}


# -----------------------------------------------------------------------------
# Helper paths & IO
# -----------------------------------------------------------------------------
def _cancel_path_for(run_id: str) -> Path:
    return CANCEL_DIR / f"{run_id}.cancel"


def _atomic_write(path: Path, data: str) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(data, encoding="utf-8")
    tmp.replace(path)  # atomic on POSIX


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        txt = path.read_text(encoding="utf-8")
        return json.loads(txt)
    except Exception:
        return None


# -----------------------------------------------------------------------------
# Local cache setter (safe from both inside/outside loop)
# -----------------------------------------------------------------------------
def _set_local_flag_sync(run_id: str):
    CANCEL_FLAGS[run_id] = True


async def _set_local_flag_async(run_id: str):
    async with _REG_LOCK:
        CANCEL_FLAGS[run_id] = True


def _schedule_local_flag(run_id: str):
    """Attempt async set; fall back to sync if no running loop."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_set_local_flag_async(run_id))
    except RuntimeError:
        _set_local_flag_sync(run_id)


# -----------------------------------------------------------------------------
# Marker creation/update
# -----------------------------------------------------------------------------
def create_cancel_marker(
    run_id: str,
    source: str = "cli",
    modifier: Optional[str] = None,
) -> Path:
    """
    Create or update the cancel marker for run_id.
    - Ensures earliest cancelled_at wins.
    - Maintains a stable 'modified_by' list without duplicates.
    """
    p = _cancel_path_for(run_id)
    now = time.time()

    existing = _read_json(p) if p.exists() else None

    # Determine cancelled_at
    if existing and "cancelled_at" in existing:
        try:
            old = float(existing["cancelled_at"])
            cancelled_at = min(old, now)
        except Exception:
            cancelled_at = now
    else:
        cancelled_at = now

    # Determine source
    source_final = existing.get("source") if existing else source
    if not source_final:
        source_final = source

    # Determine modified_by list
    modified_by = []
    if existing:
        mb = existing.get("modified_by")
        if isinstance(mb, list):
            modified_by = list(mb)

    # Apply modifier tag
    if not modifier:
        modifier = f"{source}:{os.getpid()}"
    if modifier not in modified_by:
        modified_by.append(modifier)

    payload = {
        "run_id": run_id,
        "cancelled_at": cancelled_at,
        "source": source_final,
        "modified_by": modified_by,
    }

    # Atomic write
    try:
        _atomic_write(p, json.dumps(payload))
    except Exception:
        p.write_text(json.dumps(payload), encoding="utf-8")

    # Update local cache
    _schedule_local_flag(run_id)

    return p


def update_cancel_marker_with_runtime(
    run_id: str,
    runtime_tag: Optional[str] = None,
) -> Optional[Path]:
    """
    Runtime receives a cancel notification:
    - Appends its runtime tag
    - Creates a marker if missing
    """
    p = _cancel_path_for(run_id)
    now = time.time()

    obj = _read_json(p) if p.exists() else None
    modifier = runtime_tag or f"runtime:{os.getpid()}"

    if not obj:
        # Fresh marker by runtime
        obj = {
            "run_id": run_id,
            "cancelled_at": now,
            "source": "runtime",
            "modified_by": [],
        }

    # Clean & append modifier
    mb = obj.get("modified_by")
    if not isinstance(mb, list):
        mb = []
    if modifier not in mb:
        mb.append(modifier)
    obj["modified_by"] = mb

    if "cancelled_at" not in obj:
        obj["cancelled_at"] = now
    if "source" not in obj:
        obj["source"] = "runtime"

    try:
        _atomic_write(p, json.dumps(obj))
    except Exception:
        try:
            p.write_text(json.dumps(obj), encoding="utf-8")
        except Exception:
            return None

    _schedule_local_flag(run_id)
    return p


# -----------------------------------------------------------------------------
# Query
# -----------------------------------------------------------------------------
async def is_run_cancelled(run_id: str) -> bool:
    """
    Deterministic check:
    - First check in-memory cache
    - Fallback to FS
    """
    # Fast in-memory path
    async with _REG_LOCK:
        if CANCEL_FLAGS.get(run_id):
            return True

    # FS path
    def _fs_check() -> bool:
        p = _cancel_path_for(run_id)
        if not p.exists():
            return False
        obj = _read_json(p)
        if not obj:
            return False
        return bool(obj.get("cancelled_at"))

    try:
        return await asyncio.to_thread(_fs_check)
    except Exception:
        return False


# -----------------------------------------------------------------------------
# Runtime task registry (local process only)
# -----------------------------------------------------------------------------
async def register_task(run_id: str, chain_id: str, batch_id: Optional[str] = None):
    async with _REG_LOCK:
        task = asyncio.current_task()
        if not task:
            raise RuntimeError("No current asyncio task to register")
        ACTIVE_TASKS[run_id] = task

        ACTIVE_CHAIN_TASKS.setdefault(chain_id, set()).add(run_id)
        if batch_id:
            ACTIVE_BATCH_TASKS.setdefault(batch_id, set()).add(run_id)


async def unregister_task(
    run_id: str, chain_id: Optional[str], batch_id: Optional[str]
):
    async with _REG_LOCK:
        ACTIVE_TASKS.pop(run_id, None)
        CANCEL_FLAGS.pop(run_id, None)
        if chain_id:
            ACTIVE_CHAIN_TASKS.get(chain_id, set()).discard(run_id)
        if batch_id:
            ACTIVE_BATCH_TASKS.get(batch_id, set()).discard(run_id)


async def cancel_chain_id(chain_id: str) -> int:
    async with _REG_LOCK:
        run_ids = list(ACTIVE_CHAIN_TASKS.get(chain_id, set()))
    for rid in run_ids:
        create_cancel_marker(rid, source="cli")
    return len(run_ids)


async def cancel_batch(batch_id: str) -> int:
    async with _REG_LOCK:
        run_ids = list(ACTIVE_BATCH_TASKS.get(batch_id, set()))
    for rid in run_ids:
        create_cancel_marker(rid, source="cli")
    return len(run_ids)


# -----------------------------------------------------------------------------
# run_with_cancellation — compatibility wrapper
# -----------------------------------------------------------------------------
async def run_with_cancellation(
    run_id: str, chain_id: str, batch_id: Optional[str], coro
):
    """
    Lightweight wrapper.
    Cancellation is enforced via: is_run_cancelled() + cancellation_guard.
    """
    try:
        await register_task(run_id, chain_id, batch_id)

        # Pre-cancel
        if await is_run_cancelled(run_id):
            return {"cancelled": True, "results": []}

        result = await coro

        # Post-cancel
        if await is_run_cancelled(run_id):
            return {"cancelled": True, "results": []}

        return result

    except asyncio.CancelledError:
        return {
            "run_id": run_id,
            "chain_id": chain_id,
            "cancelled": True,
            "results": [{"error": "execution cancelled"}],
            "success": False,
        }

    finally:
        await unregister_task(run_id, chain_id, batch_id)
