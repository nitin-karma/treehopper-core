import time
from treehopper.visualizer.db_util import db
from pathlib import Path
from treehopper.th_config import TH_ROOT, DB_DIR


def analytics_db_available() -> bool:
    db_dir = Path(TH_ROOT) / DB_DIR
    return db_dir.exists()


def get_subscription_id() -> str:
    path = Path(TH_ROOT) / "subscription_id.txt"
    return path.read_text().strip() if path.exists() else "unknown"


def record_analytics_event(run_id: str, chain_name: str, event: dict):
    """
    Persist a normalized analytics event.
    """
    ts = time.time()
    sub_id = get_subscription_id()

    db.execute(
        """
        INSERT INTO analytics_events
        (ts, event_type, run_id, chain_name, agent_name, step_id, subscription_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ts,
            event.get("type"),
            run_id,
            chain_name,
            event.get("agent"),
            event.get("step_id"),
            sub_id,
        ),
    )
