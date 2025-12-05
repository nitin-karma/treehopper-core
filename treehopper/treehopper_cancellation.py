# treehopper/treehopper_cancellation.py
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

from treehopper.th_config import (
    CANCEL_DIR,
    # TH_ROOT,
    # RUNTIME_DIR,
    # CHAIN_PID_PREFIX
)

# ensure cancel dir exists
CANCEL_DIR.mkdir(parents=True, exist_ok=True)

# In-memory helpers (non-authoritative caches for local process speed)
_REG_LOCK = asyncio.Lock()
ACTIVE_TASKS: Dict[str, asyncio.Task] = {}
ACTIVE_CHAIN_TASKS: Dict[str, Set[str]] = {}
ACTIVE_BATCH_TASKS: Dict[str, Set[str]] = {}
CANCEL_FLAGS: Dict[str, bool] = {}


# ---------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------
def _cancel_path_for(run_id: str) -> Path:
    safe = f"{run_id}.cancel"
    return CANCEL_DIR / safe


def _atomic_write(path: Path, data: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(data, encoding="utf-8")
    tmp.replace(path)


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        t = path.read_text(encoding="utf-8")
        return json.loads(t)
    except Exception:
        return None


# ---------------------------------------------------------------------
# Marker creation / update
# ---------------------------------------------------------------------
def create_cancel_marker(
    run_id: str, source: str = "cli", modifier: Optional[str] = None
) -> Path:
    """
    Create or update the cancel marker for run_id.
    Returns the Path to the marker file.
    """
    p = _cancel_path_for(run_id)
    now = time.time()
    # load existing if present
    existing = _read_json(p) if p.exists() else None

    if existing:
        # keep earliest cancelled_at
        cancelled_at = existing.get("cancelled_at", now) or now
        cancelled_at = (
            float(cancelled_at) if isinstance(cancelled_at, (int, float)) else now
        )
        if cancelled_at > now:
            cancelled_at = now
        source_final = existing.get("source") or source
        modified_by = list(existing.get("modified_by", []))
    else:
        cancelled_at = now
        source_final = source
        modified_by = []

    # modifier label
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

    try:
        _atomic_write(p, json.dumps(payload))
    except Exception:
        # best-effort
        p.write_text(json.dumps(payload), encoding="utf-8")

    # set quick in-memory flag for local processes
    async def _set_local_flag():
        async with _REG_LOCK:
            CANCEL_FLAGS[run_id] = True

    try:
        # fire-and-forget safe
        asyncio.get_running_loop().create_task(_set_local_flag())
    except Exception:
        # not inside loop - ignore
        pass

    return p


def update_cancel_marker_with_runtime(
    run_id: str, runtime_tag: Optional[str] = None
) -> Optional[Path]:
    """
    Runtime-side update when receiving notify: append runtime tag to modified_by.
    Creates file if missing (so CLI or API can create later).
    """
    p = _cancel_path_for(run_id)
    modifier = runtime_tag or f"runtime:{os.getpid()}"
    try:
        if p.exists():
            obj = _read_json(p) or {}
        else:
            obj = {
                "run_id": run_id,
                "cancelled_at": time.time(),
                "source": "runtime",
                "modified_by": [],
            }
        if "modified_by" not in obj or not isinstance(obj["modified_by"], list):
            obj["modified_by"] = list(obj.get("modified_by") or [])
        if modifier not in obj["modified_by"]:
            obj["modified_by"].append(modifier)
        # keep cancelled_at (if absent set now)
        if "cancelled_at" not in obj:
            obj["cancelled_at"] = time.time()
        if "source" not in obj:
            obj["source"] = "runtime"
        _atomic_write(p, json.dumps(obj))
        # update local cache
        try:
            asyncio.get_running_loop().create_task(
                _set_local_flag_for(run_id=True, run_id_arg=run_id)
            )
        except Exception:
            pass
        return p
    except Exception:
        return None


async def _set_local_flag_for(run_id: bool = False, run_id_arg: Optional[str] = None):
    async with _REG_LOCK:
        if run_id_arg:
            CANCEL_FLAGS[run_id_arg] = True


# ---------------------------------------------------------------------
# Read / Query
# ---------------------------------------------------------------------
async def is_run_cancelled(run_id: str) -> bool:
    """
    Returns True if a cancel marker exists for run_id.
    Fast path: uses in-memory flag; otherwise reads CANCEL_DIR file.
    """
    # quick in-memory check
    async with _REG_LOCK:
        if CANCEL_FLAGS.get(run_id, False):
            return True

    # check filesystem (in threadpool)
    def _sync_check():
        p = _cancel_path_for(run_id)
        if not p.exists():
            return False
        try:
            obj = _read_json(p)
            if not obj:
                return False
            # presence of cancelled_at is sufficient
            if obj.get("cancelled_at"):
                return True
            return False
        except Exception:
            return False

    try:
        return await asyncio.to_thread(_sync_check)
    except Exception:
        return False


# ---------------------------------------------------------------------
# Register / unregister tasks (for runtime-local cancellation of in-process tasks)
# ---------------------------------------------------------------------
async def register_task(run_id: str, chain_id: str, batch_id: Optional[str] = None):
    async with _REG_LOCK:
        task = asyncio.current_task()
        if task is None:
            raise RuntimeError("No current asyncio task to register")
        ACTIVE_TASKS[run_id] = task
        if chain_id:
            ACTIVE_CHAIN_TASKS.setdefault(chain_id, set()).add(run_id)
        if batch_id:
            ACTIVE_BATCH_TASKS.setdefault(batch_id, set()).add(run_id)


async def unregister_task(
    run_id: str, chain_id: Optional[str] = None, batch_id: Optional[str] = None
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
    count = 0
    for rid in run_ids:
        create_cancel_marker(rid, source="cli")
        count += 1
    return count


async def cancel_batch(batch_id: str) -> int:
    async with _REG_LOCK:
        run_ids = list(ACTIVE_BATCH_TASKS.get(batch_id, set()))
    count = 0
    for rid in run_ids:
        create_cancel_marker(rid, source="cli")
        count += 1
    return count


# ---------------------------------------------------------------------
# run_with_cancellation: lightweight wrapper kept for compatibility
# ---------------------------------------------------------------------
async def run_with_cancellation(
    run_id: str, chain_id: str, batch_id: Optional[str], coro
):
    """
    Wrap caller coroutine to ensure registration and cleanup.
    Actual cancellation detection is provided by is_run_cancelled() / cancellation_guard.
    """
    try:
        await register_task(run_id, chain_id, batch_id)
        # PRE-check
        if await is_run_cancelled(run_id):
            return {"cancelled": True, "results": []}

        # execute the coroutine (caller should be cancellation-aware)
        result = await coro

        # POST-check
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
