# treehopper/utils/run_registry.py
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

MAX_RUNS_PER_CHAIN = 50


def _ensure_runs_dir(chain_dir: Path) -> Path:
    runs_dir = chain_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    return runs_dir


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def make_run_id(chain_name: str) -> str:
    # public helper: time-based ID
    return f"{chain_name}-{int(time.time() * 1000)}"


def _make_run_filename(run_id: str) -> str:
    # safe filename: exec_summ-1732523456123.json
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
    cancelled: bool = False,  # <-- NEW OPTIONAL FIELD
) -> Dict[str, Any]:
    """
    Create a run record and write history files.
    """
    executed_at = _now_iso()
    run_id = run_id or make_run_id(chain_name)

    history: Dict[str, Any] = {
        "chain_name": chain_name,
        "chain_id": chain_id,
        "run_id": run_id,
        "executed_at": executed_at,
        "input": payload or {},
        "results": results,
        "detached": detached,
        "success": success,
    }

    # NEW: Mark cancellation here
    if cancelled:
        history["cancelled"] = True

    if chain_dir is not None:
        runs_dir = _ensure_runs_dir(chain_dir)

        # last_run.json
        (chain_dir / "last_run.json").write_text(
            json.dumps(history, indent=2), encoding="utf-8"
        )

        # run file
        run_file = runs_dir / _make_run_filename(run_id)
        run_file.write_text(json.dumps(history, indent=2), encoding="utf-8")

        _prune_runs(runs_dir)

    return history


def _prune_runs(runs_dir: Path) -> None:
    """
    Keep only the newest MAX_RUNS_PER_CHAIN run files.
    """
    files = sorted(
        [p for p in runs_dir.glob("*.json") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in files[MAX_RUNS_PER_CHAIN:]:
        old.unlink(missing_ok=True)


def list_chain_runs(chain_dir: Path, limit: int = 50) -> List[Dict[str, Any]]:
    """
    List recent runs for a chain (up to `limit`).
    """
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
