# treehopper/visualizer/log_tail.py
import json
from pathlib import Path
from typing import List
from treehopper.th_config import LOG_RENDER_LIMIT


# def read_logs(log_dir: Path, limit: int = 200) -> List[dict]:
#     curr_logs: List[dict] = []
#     if not log_dir.exists():
#         print(f"[ui_read_logs] log dir not found- {log_dir}")
#         return curr_logs

#     for f in sorted(log_dir.glob("*.log")):
#         try:
#             lines = f.read_text().splitlines()[-limit:]
#             for line in lines:
#                 curr_logs.append(json.loads(line))
#         except Exception as e:
#             print(f"[ui_read_logs] - {str(e)}")
#             continue

#     return curr_logs[-limit:]

# def read_logs(log_dir: Path, limit: int = 200) -> List[dict]:
#     curr_logs: List[dict] = []
#     if not log_dir.exists():
#         print(f"[ui_read_logs] log dir not found- {log_dir}")
#         return curr_logs

#     for f in sorted(log_dir.glob("*.log")):
#         try:
#             lines = f.read_text().splitlines()[-limit:]
#             for line in lines:
#                 curr_logs.append(json.loads(line))
#         except Exception as e:
#             print(f"[ui_read_logs] - {str(e)}")
#             continue

#     # REVERSE the list before returning so latest logs are at index 0
#     return curr_logs[::-1][:limit]


def read_logs(log_dir: Path, limit: int = LOG_RENDER_LIMIT) -> List[dict]:
    curr_logs: List[dict] = []
    if not log_dir.exists():
        return curr_logs

    # Get all log files, sorted by name (usually timestamped)
    log_files = sorted(log_dir.glob("*.log"))

    # Iterate through files to collect enough lines
    for f in reversed(log_files):  # Start from the newest file
        if len(curr_logs) >= limit:
            break
        try:
            lines = f.read_text().splitlines()
            for line in reversed(lines):  # Start from the bottom of the file
                if len(curr_logs) >= limit:
                    break
                try:
                    curr_logs.append(json.loads(line))
                except Exception as e:
                    print(str(e))
                    continue
        except Exception as e:
            print(str(e))
            continue

    return curr_logs  # Already latest first due to reversed() logic
