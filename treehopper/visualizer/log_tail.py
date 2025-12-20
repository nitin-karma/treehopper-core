# treehopper/visualizer/log_tail.py
import json
from pathlib import Path
from typing import List


def read_logs(log_dir: Path, limit: int = 200) -> List[dict]:
    curr_logs: List[dict] = []
    if not log_dir.exists():
        print(f"[ui_read_logs] log dir not found- {log_dir}")
        return curr_logs

    for f in sorted(log_dir.glob("*.log")):
        try:
            lines = f.read_text().splitlines()[-limit:]
            for line in lines:
                curr_logs.append(json.loads(line))
        except Exception as e:
            print(f"[ui_read_logs] - {str(e)}")
            continue

    return curr_logs[-limit:]
