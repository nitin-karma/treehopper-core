# treehopper/visualizer/log_tail.py

import json
from pathlib import Path
from typing import List
from tabulate import tabulate
from treehopper.th_config import TH_ROOT
from treehopper.th_config import LOG_RENDER_LIMIT
from datetime import datetime

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


def format_timestamp(ts_val):
    """Converts ISO strings or Unix integers to local time string."""
    try:
        if isinstance(ts_val, (int, float)):
            dt = datetime.fromtimestamp(ts_val)
        else:
            # Handles ISO format: 2023-10-27T10:00:00Z
            dt = datetime.fromisoformat(ts_val.replace("Z", "+00:00"))

        # .astimezone() with no args converts to local system time
        return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        print(str(e))
        return str(ts_val)


# To view the logs on shell
def run_view_logs(tail=None, show_all=False, level_filter="INFO"):
    # Adjust this path to your actual logs directory
    log_dir = Path(TH_ROOT) / "logs"

    if not log_dir.exists():
        print(f"❌ Log directory not found at {log_dir}")
        return

    # Collect all .log files (assuming timestamped names)
    log_files = sorted(log_dir.glob("*.log"), reverse=True)

    if not log_files:
        print("ℹ️ No log files found.")
        return

    all_parsed_logs = []
    # If tail is None and show_all is False, default to something sensible
    limit = tail if tail else (999999 if show_all else 50)

    for log_file in log_files:
        if len(all_parsed_logs) >= limit:
            break

        try:
            with open(log_file, "r") as f:
                # Read lines and reverse to get latest first
                lines = f.readlines()
                for line in reversed(lines):
                    if len(all_parsed_logs) >= limit:
                        break
                    try:
                        data = json.loads(line.strip())
                        log_level = data.get("level", "INFO").upper()
                        if level_filter:
                            if level_filter.upper() != log_level:
                                continue  # This line skips the append below
                        # Flatten or simplify for table view
                        all_parsed_logs.append(
                            [
                                format_timestamp(data.get("ts")),
                                log_level,
                                data.get("msg", "")[:100],  # Truncate long messages
                            ]
                        )
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"Error reading {log_file.name}: {e}")

    if not all_parsed_logs:
        print("ℹ️ No valid JSON logs found.")
        return

    headers = ["Timestamp", "Level", "Message"]
    title = f"Latest {len(all_parsed_logs)} Logs" if not show_all else "All Logs"
    print(f"\n📄 {title}:")
    print(tabulate(all_parsed_logs, headers=headers, tablefmt="rounded_grid"))
