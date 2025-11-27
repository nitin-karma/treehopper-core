# treehopper/treehopper_cancellation.py
"""
Phase 3.3 — Cancellation API for Treehopper-core

Provides:
 - ACTIVE_TASKS / ACTIVE_CHAIN_TASKS / ACTIVE_BATCH_TASKS registries
 - register_task / unregister_task
 - cancel_run_id / cancel_chain_id / cancel_batch
 - run_with_cancellation wrapper
 - FastAPI APIRouter (optional) for HTTP cancellation endpoints

Usage:
 - Import register_task / run_with_cancellation in places where async run is created.
 - Use cancel_* functions from CLI or HTTP endpoints.
"""

import asyncio
import time
from typing import Dict, Optional, Set
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/v1/cancel", tags=["cancellation"])

# run_id -> asyncio.Task
ACTIVE_TASKS: Dict[str, asyncio.Task] = {}

# chain_id -> set(run_id)
ACTIVE_CHAIN_TASKS: Dict[str, Set[str]] = {}

# batch_id -> set(run_id)
ACTIVE_BATCH_TASKS: Dict[str, Set[str]] = {}

# lock to protect registry updates
_REG_LOCK = asyncio.Lock()

# --- NEW: explicit cancellation flags (critical for PRE-STEP checks) ---
CANCEL_FLAGS: Dict[str, bool] = {}


async def register_task(run_id: str, chain_id: str, batch_id: Optional[str] = None):
    """
    Register the *current* asyncio task under run_id.
    Call this from inside the async context that's executing the run.
    """
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

        # cleanup flags
        CANCEL_FLAGS.pop(run_id, None)

        if chain_id and chain_id in ACTIVE_CHAIN_TASKS:
            ACTIVE_CHAIN_TASKS[chain_id].discard(run_id)
            if not ACTIVE_CHAIN_TASKS[chain_id]:
                ACTIVE_CHAIN_TASKS.pop(chain_id, None)
        if batch_id and batch_id in ACTIVE_BATCH_TASKS:
            ACTIVE_BATCH_TASKS[batch_id].discard(run_id)
            if not ACTIVE_BATCH_TASKS[batch_id]:
                ACTIVE_BATCH_TASKS.pop(batch_id, None)


async def cancel_run_id(run_id: str) -> bool:
    async with _REG_LOCK:
        task = ACTIVE_TASKS.get(run_id)
        if not task:
            return False
        CANCEL_FLAGS[run_id] = True  # <-- mark cancelled
        task.cancel()  # <-- attempt to stop execution
        return True


async def cancel_chain_id(chain_id: str) -> int:
    """
    Cancel all active runs for a chain_id. Returns number of attempted cancellations.
    """
    async with _REG_LOCK:
        run_ids = list(ACTIVE_CHAIN_TASKS.get(chain_id, set()))
    cancelled = 0
    for rid in run_ids:
        ok = await cancel_run_id(rid)
        if ok:
            cancelled += 1
    return cancelled


async def cancel_batch(batch_id: str) -> int:
    async with _REG_LOCK:
        run_ids = list(ACTIVE_BATCH_TASKS.get(batch_id, set()))
    cancelled = 0
    for rid in run_ids:
        ok = await cancel_run_id(rid)
        if ok:
            cancelled += 1
    return cancelled


async def run_with_cancellation(
    run_id: str, chain_id: str, batch_id: Optional[str], coro
):
    """
    Wrapper to run coroutine `coro` with cancellation support and automatic
    registration/unregistration.
    - `coro` may be an awaitable or coroutine function (callable).
    Returns the wrapped coroutine result. If cancelled, returns a cancellation dict.
    """
    try:
        # register current task
        await register_task(run_id, chain_id, batch_id)

        # accept either coroutine object or awaitable (callables are executed)
        if asyncio.iscoroutine(coro):
            return await coro
        elif callable(coro):
            return await coro()
        else:
            # assume awaitable
            return await coro

    except asyncio.CancelledError:
        # return standardized cancellation result (higher-level code should record it)
        return {
            "run_id": run_id,
            "chain_id": chain_id,
            "cancelled": True,
            "executed_at": time.time(),
            "results": [{"error": "execution cancelled"}],
            "success": False,
        }

    finally:
        # always unregister
        await unregister_task(run_id, chain_id=chain_id, batch_id=batch_id)


async def is_run_cancelled(run_id: str) -> bool:
    async with _REG_LOCK:
        return CANCEL_FLAGS.get(run_id, False)


# -------------------------
# Optional HTTP endpoints
# -------------------------


@router.post("/run/{run_id}")
async def http_cancel_run(run_id: str):
    ok = await cancel_run_id(run_id)
    if not ok:
        raise HTTPException(
            status_code=404, detail=f"Run {run_id} not found or already finished"
        )
    return {"cancelled": True, "run_id": run_id}


@router.post("/chain/{chain_id}")
async def http_cancel_chain(chain_id: str):
    n = await cancel_chain_id(chain_id)
    return {"cancelled_runs": n, "chain_id": chain_id}


@router.post("/batch/{batch_id}")
async def http_cancel_batch(batch_id: str):
    n = await cancel_batch(batch_id)
    return {"cancelled_runs": n, "batch_id": batch_id}


def list_active_runs():
    """Debug helper"""
    return {
        "total_active": len(ACTIVE_TASKS),
        "by_chain": {k: len(v) for k, v in ACTIVE_CHAIN_TASKS.items()},
        "by_batch": {k: len(v) for k, v in ACTIVE_BATCH_TASKS.items()},
    }
