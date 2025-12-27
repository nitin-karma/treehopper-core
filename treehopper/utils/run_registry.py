# treehopper/utils/run_registry.py
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from treehopper.th_config import (
    #     RUNTIME_DIR,
    CANCEL_DIR,
)

# Add after existing imports
from treehopper.sync_to_sqlite import record_run as sqlite_record_run
from treehopper.logging import get_logger

logger = get_logger()

# Ensure cancel dir exists
print(f"[run_registry] creating or checking Cancel Directory - {CANCEL_DIR}")
logger.info(f"[run_registry] creating or checking Cancel Directory - {CANCEL_DIR}")
# CANCEL_DIR.mkdir(parents=True, exist_ok=True)

MAX_RUNS_PER_CHAIN = 50


def _ensure_runs_dir(chain_dir: Path) -> Path:
    print(
        "[_ensure_runs_dir] i am called here in run_registry.py, cancels dir {CANCEL_DIR}"
    )
    logger.info(
        "[_ensure_runs_dir] i am called here in run_registry.py, cancels dir {CANCEL_DIR}"
    )
    runs_dir = chain_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    return runs_dir


def _now_iso() -> str:
    print("[_now_iso] i am called here in run_registry.py, cancels dir {CANCEL_DIR}")
    logger.info(
        "[_now_iso] i am called here in run_registry.py, cancels dir {CANCEL_DIR}"
    )
    return datetime.utcnow().isoformat() + "Z"


# def make_run_id(chain_name: str) -> str:
#     # public helper: time-based ID
#     return f"{chain_name}-{int(time.time() * 1000)}"
def make_run_id(chain_name: str) -> str:
    """
    Generate a globally unique run_id.

    Format:
      <chain_name>-<epoch_ms>-<short_uuid>

    Example:
      demo-1765805542341-a3f9c2
    """
    print("[make_run_id] i am called here in run_registry.py, cancels dir {CANCEL_DIR}")
    logger.info(
        "[make_run_id] i am called here in run_registry.py, cancels dir {CANCEL_DIR}"
    )
    ts = int(time.time() * 1000)
    suffix = uuid.uuid4().hex[:6]
    return f"{chain_name}-{ts}-{suffix}"


def _make_run_filename(run_id: str) -> str:
    # safe filename: exec_summ-1732523456123.json
    print(
        "[_make_run_filename] i am called here in run_registry.py, cancels dir {CANCEL_DIR}"
    )
    logger.info(
        "[_make_run_filename] i am called here in run_registry.py, cancels dir {CANCEL_DIR}"
    )
    return f"{run_id}.json"


def record_chain_run(
    *,
    chain_name: str,
    chain_id: Optional[str],
    chain_dir: Optional[Path],
    payload: Dict[str, Any],
    results: List[Any],
    detached: bool,
    success: bool,
    run_id: Optional[str] = None,
    cancelled: bool = False,
    status: Optional[
        str
    ] = None,  # new optional status (pending/running/completed/failed/cancelled)
    current_step_index: Optional[int] = None,  # new checkpoint index
) -> Dict[str, Any]:
    """
    Create or update a run record and write:
      - <chain_dir>/last_run.json
      - <chain_dir>/runs/<run_id>.json
    """
    print(
        "[record_chain_run] i am called here in run_registry.py, cancels dir {CANCEL_DIR}"
    )
    logger.info(
        "[record_chain_run] i am called here in run_registry.py, cancels dir {CANCEL_DIR}"
    )
    executed_at = _now_iso()
    run_id = run_id or make_run_id(chain_name)

    # default status if not provided
    if status is None:
        status = "completed" if success else "failed"

    history: Dict[str, Any] = {
        "chain_name": chain_name,
        "chain_id": chain_id,
        "run_id": run_id,
        "executed_at": executed_at,
        "input": payload or {},
        "results": results,
        "detached": detached,
        "success": success,
        "status": status,
    }

    if cancelled:
        history["cancelled"] = True

    if current_step_index is not None:
        history["current_step_index"] = current_step_index

    if chain_dir is not None:
        runs_dir = _ensure_runs_dir(chain_dir)

        # last_run.json
        last_run_path = chain_dir / "last_run.json"
        print(f"[run_registry] Writing last_run.json → {last_run_path}")
        logger.info(f"[run_registry] Writing last_run.json → {last_run_path}")
        last_run_path.write_text(json.dumps(history, indent=2), encoding="utf-8")

        # individual run file
        run_file = runs_dir / _make_run_filename(run_id)
        print(f"[run_registry] Writing run file → {run_file}")
        logger.info(f"[run_registry] Writing run file → {run_file}")
        run_file.write_text(json.dumps(history, indent=2), encoding="utf-8")

        # prune old runs
        _prune_runs(runs_dir)
    else:
        # fallback: write to runtime/cancels? Not for run data, so just log
        print(f"[run_registry] Warning: chain_dir is None, not persisting run {run_id}")
        logger.info(
            f"[run_registry] Warning: chain_dir is None, not persisting run {run_id}"
        )

    # ✅ NEW: Add before `return history`
    # Dual write to SQLite
    try:
        sqlite_record_run(
            {
                "run_id": run_id,
                "chain_name": chain_name,
                "chain_id": chain_id,
                "chain_dir": str(chain_dir) if chain_dir else "",
                "payload": payload,
                "results": results,
                "detached": detached,
                "success": success,
                "status": status,
                "cancelled": cancelled,
                "current_step_index": current_step_index,
                "created_at": executed_at,
                "completed_at": (
                    executed_at
                    if status in ["completed", "failed", "cancelled"]
                    else None
                ),
            }
        )
    except Exception as e:
        print(f"[run_registry] Warning: SQLite sync failed: {e}")
        logger.error(f"[run_registry] Warning: SQLite sync failed: {e}")

    return history


def _prune_runs(runs_dir: Path) -> None:
    """
    Keep only the newest MAX_RUNS_PER_CHAIN run files.
    """
    print("[_prune_runs] i am called here in run_registry.py, cancels dir {CANCEL_DIR}")
    logger.info(
        "[_prune_runs] i am called here in run_registry.py, cancels dir {CANCEL_DIR}"
    )
    files = sorted(
        [p for p in runs_dir.glob("*.json") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in files[MAX_RUNS_PER_CHAIN:]:
        try:
            old.unlink(missing_ok=True)
            print(f"[run_registry] Pruned old run file → {old}")
            logger.info(f"[run_registry] Pruned old run file → {old}")
        except Exception:
            pass


def list_chain_runs(chain_dir: Path, limit: int = 50) -> List[Dict[str, Any]]:
    """
    List recent runs for a chain (up to `limit`).
    """
    print(
        "[list_chain_runs] i am called here in run_registry.py, cancels dir {CANCEL_DIR}"
    )
    logger.info(
        "[list_chain_runs] i am called here in run_registry.py, cancels dir {CANCEL_DIR}"
    )
    runs_dir = chain_dir / "runs"
    if not runs_dir.exists():
        return []

    files = sorted(
        [p for p in runs_dir.glob("*.json") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:limit]

    runs: List[Dict[str, Any]] = []
    for f in files:
        try:
            data = json.loads(f.read_text())
            # small summary
            runs.append(
                {
                    "run_id": data.get("run_id"),
                    "executed_at": data.get("executed_at"),
                    "success": data.get("success"),
                    "detached": data.get("detached"),
                    "chain_name": data.get("chain_name"),
                    "chain_id": data.get("chain_id"),
                }
            )
        except Exception:
            continue
    return runs


def get_chain_run(chain_dir: Path, run_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch a single run by run_id (linear scan, bounded by MAX_RUNS_PER_CHAIN).
    """
    print(
        "[get_chain_run] i am called here in run_registry.py, cancels dir {CANCEL_DIR}"
    )
    logger.info(
        "[get_chain_run] i am called here in run_registry.py, cancels dir {CANCEL_DIR}"
    )
    runs_dir = chain_dir / "runs"
    if not runs_dir.exists():
        return None

    for f in runs_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text())
        except Exception:
            continue
        if data.get("run_id") == run_id:
            return data
    return None


def update_run_partial(
    chain_dir: Path, run_id: str, **updates
) -> Optional[Dict[str, Any]]:
    """
    Load an existing run record and update fields, then write.
    Returns updated dict or None if file missing.
    """
    print(
        "[update_run_partial] i am called here in run_registry.py, cancels dir {CANCEL_DIR}"
    )
    runs_dir = chain_dir / "runs"
    run_file = runs_dir / _make_run_filename(run_id)
    if not run_file.exists():
        return None
    try:
        data = json.loads(run_file.read_text())
    except Exception as e:
        logger.error(f"[update_run_partial] Error {e}")
        return None

    data.update(updates)
    # update last_run.json as well
    last_run_path = chain_dir / "last_run.json"
    print(f"[run_registry] Updating last_run.json → {last_run_path}")
    logger.info(f"[run_registry] Updating last_run.json → {last_run_path}")
    last_run_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    run_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # ✅ NEW: Update SQLite too
    try:
        sqlite_record_run(data)
    except Exception as e:
        print(f"[run_registry] Warning: SQLite sync failed: {e}")
        logger.error(f"[run_registry] Warning: SQLite sync failed: {e}")
    return data


print("i am called here in  end of run_registry.py, cancels dir {CANCEL_DIR}")
logger.info("i am called here in  end of run_registry.py, cancels dir {CANCEL_DIR}")
