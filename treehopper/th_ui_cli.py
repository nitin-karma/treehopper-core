import os
import time
import sys
import subprocess
import signal
import socket
from pathlib import Path
from treehopper.th_config import DEFAULT_UI_PORT, RUNTIME_DIR
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


def _get_runtime_dir() -> Path:
    runtime = RUNTIME_DIR
    return runtime


def launch_ui():
    """
    Launch TreehopperAI local visualizer UI
    """
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

    runtime = _get_runtime_dir()
    pid_file = runtime / "ui.pid"
    log_file = runtime / "ui.log"  # 1. Define log file path

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "treehopper.visualizer.app:app",
        "--port",
        str(port),
        "--log-level",
        "info",  # Changed to 'info' so you actually see startup in logs
    ]

    print("🌿 TreehopperAI UI Launcher")
    print("────────────────────────")
    print(f"📁 TH_ROOT: {runtime.parent}")

    if fg:
        print(f"▶️ Running UI in foreground on http://localhost:{port}")
        subprocess.run(cmd)
        return

    # 2. Open log file in append mode ('a')
    # This ensures logs aren't wiped every time you restart
    log_f = open(log_file, "a", encoding="utf-8")

    proc = subprocess.Popen(
        cmd,
        stdout=log_f,  # Redirect standard output to file
        stderr=subprocess.STDOUT,  # Redirect errors to the same file
        env=os.environ.copy(),
        start_new_session=True,  # <--- ADD THIS
    )

    pid_file.write_text(str(proc.pid))

    print(f"🚀 UI started on http://localhost:{port}")
    print(f"📌 PID: {proc.pid}")
    print(f"📝 Log: {log_file}")  # 3. Inform the user where logs are going
    print(f"🧭 Open in browser: http://localhost:{port}")


def stop_ui():
    runtime = _get_runtime_dir()
    pid_file = runtime / "ui.pid"

    # Using your read_pid helper style
    pid = read_ui_pid(pid_file)

    if not pid:
        print("⚠️ Treehopper UI is not running")
        return

    print(f"🛑 Stopping Treehopper UI (PID {pid})")

    try:
        # Instead of just kill_pid(pid), we kill the Group
        # This is the "Magic Sauce" for Uvicorn on macOS
        kill_ui_pid(pid)
        pid_file.unlink(missing_ok=True)
        print("✔ Stopped")
    except ProcessLookupError:
        print("⚠️ UI process already stopped")
        pid_file.unlink(missing_ok=True)
    except Exception as e:
        # Fallback to your standard agent kill if group kill fails
        logger.error(str(e))
        kill_ui_pid(pid)
        pid_file.unlink(missing_ok=True)
