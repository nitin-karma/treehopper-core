# treehopper/th_ui_cli.py
# UPDATED VERSION - Uses UI_PID, UI_LOG from th_config properly
# Also ensures CANCEL_DIR exists (for run_registry.py compatibility)

import os
import time
import sys
import subprocess
import signal
import socket
from pathlib import Path
from treehopper.th_config import DEFAULT_UI_PORT, UI_PID, UI_LOG, CANCEL_DIR
from treehopper.logging import get_logger

logger = get_logger()


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


def kill_ui_pid(pid: int):
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError as e:
        logger.error(f"{str(e)}")
        return True
    time.sleep(3)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError as e:
        logger.error(f"{str(e)}")
        return True
    return True


def read_ui_pid(path: Path) -> int | None:
    """
    Read PID from file. Accepts both "<pid>" and "<pid>:<port>" formats.
    Returns pid (int) or None.
    """
    if not path.exists():
        return None
    try:
        text = path.read_text().strip()
        if ":" in text:
            pid_str, _ = text.split(":", 1)
            return int(pid_str)
        return int(text)
    except Exception as e:
        logger.error(f"{str(e)}")
        return None


def _ensure_ui_files():
    """
    Ensure UI-specific files and directories exist.
    Called before launching UI to prevent errors.

    This is critical because:
    1. UI_LOG must exist before opening for append
    2. UI_PID parent directory must exist before writing PID
    3. CANCEL_DIR must exist (run_registry.py checks this)
    """
    # Ensure parent directory exists
    UI_PID.parent.mkdir(parents=True, exist_ok=True)

    # Create log file if it doesn't exist
    if not UI_LOG.exists():
        UI_LOG.touch()
        logger.info(f"Created UI log file: {UI_LOG}")

    # Ensure CANCEL_DIR exists (critical for run_registry.py)
    CANCEL_DIR.mkdir(parents=True, exist_ok=True)


def launch_ui():
    """
    Launch TreehopperAI local visualizer UI
    """
    # ✅ CRITICAL: Ensure all required files/dirs exist FIRST
    _ensure_ui_files()

    args = sys.argv[2:]

    port = DEFAULT_UI_PORT
    fg = False

    if "--port" in args:
        idx = args.index("--port")
        try:
            port = int(args[idx + 1])
        except Exception:
            print("❌ Invalid value for --port")
            sys.exit(1)

    if "--fg" in args:
        fg = True

    if is_port_in_use(port):
        print(f"❌ Port {port} is already in use. Please run 'th stop ui' first.")
        return

    # ✅ Use imported constants from th_config (NOT manual paths)
    pid_file = UI_PID
    log_file = UI_LOG

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "treehopper.visualizer.app:app",
        "--port",
        str(port),
        "--log-level",
        "info",
    ]

    print("🌿 TreehopperAI UI Launcher")
    print("────────────────────────")
    print(f"📁 Runtime dir: {UI_PID.parent}")

    if fg:
        print(f"▶️ Running UI in foreground on http://localhost:{port}")
        subprocess.run(cmd)
        return

    # ✅ Open log file in append mode
    log_f = open(log_file, "a", encoding="utf-8")

    proc = subprocess.Popen(
        cmd,
        stdout=log_f,
        stderr=subprocess.STDOUT,
        env=os.environ.copy(),
        start_new_session=True,
    )

    pid_file.write_text(str(proc.pid))

    print(f"🚀 UI started on http://localhost:{port}")
    print(f"📌 PID: {proc.pid}")
    print(f"📝 Log: {log_file}")
    print(f"🧭 Open in browser: http://localhost:{port}")


def stop_ui():
    """
    Stop the TreehopperAI UI server
    """
    # ✅ Use imported constant from th_config
    pid_file = UI_PID

    pid = read_ui_pid(pid_file)

    if not pid:
        print("⚠️ Treehopper UI is not running")
        return

    print(f"🛑 Stopping Treehopper UI (PID {pid})")

    try:
        kill_ui_pid(pid)
        pid_file.unlink(missing_ok=True)
        print("✔ Stopped")
    except ProcessLookupError:
        print("⚠️ UI process already stopped")
        pid_file.unlink(missing_ok=True)
    except Exception as e:
        logger.error(str(e))
        kill_ui_pid(pid)
        pid_file.unlink(missing_ok=True)
