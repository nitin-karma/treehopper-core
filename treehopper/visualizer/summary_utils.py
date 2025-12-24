import time
from treehopper.th_config import REGISTRY_DIR
from collections import Counter, defaultdict
from typing import Counter as CounterType, Dict


def _build_summary(rows, window: str):
    runs = set()
    runs_success = 0
    runs_failed = 0

    chain_counts: CounterType[str] = Counter()
    agent_counts: CounterType[str] = Counter()
    event_counts: CounterType[str] = Counter()
    timeline: Dict[str, int] = defaultdict(int)

    for r in rows:
        event_counts[r["event_type"]] += 1

        if r["chain_name"]:
            chain_counts[r["chain_name"]] += 1

        if r["agent_name"]:
            agent_counts[r["agent_name"]] += 1

        if r["run_id"]:
            runs.add(r["run_id"])

        if r["event_type"] == "run_completed":
            runs_success += 1

        if r["event_type"] == "run_failed":
            runs_failed += 1

        hour = time.strftime("%H:%M", time.localtime(r["ts"]))
        timeline[hour] += 1

    return {
        "time_window": window,
        "runs": {
            "total": len(runs),
            "success": runs_success,
            "failed": runs_failed,
        },
        "chains": {"by_chain": dict(chain_counts)},
        "agents": {"invocations": dict(agent_counts)},
        "files": {"count": 0, "total_size_mb": 0.0, "by_extension": {}},  # filled below
        "events": {"by_type": dict(event_counts)},
        "timeline": {
            "runs_per_hour": [
                {"hour": h, "count": c} for h, c in sorted(timeline.items())
            ]
        },
    }


def _file_stats():
    shared_dir = REGISTRY_DIR / "shared"
    # Adding the type annotation here
    ext_counts: CounterType[str] = Counter()

    total_size: int = 0
    count: int = 0

    if shared_dir.exists():
        for p in shared_dir.rglob("*"):
            if p.is_file():
                count += 1
                total_size += p.stat().st_size
                ext = p.suffix.lstrip(".") or "unknown"
                ext_counts[ext] += 1

    return {
        "count": count,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "by_extension": dict(ext_counts),
    }
