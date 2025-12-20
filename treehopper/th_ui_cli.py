import os
import sys
import subprocess
import signal
from pathlib import Path
from treehopper.th_config import DEFAULT_UI_PORT, RUNTIME_DIR


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
    )

    pid_file.write_text(str(proc.pid))

    print(f"🚀 UI started on http://localhost:{port}")
    print(f"📌 PID: {proc.pid}")
    print(f"📝 Log: {log_file}")  # 3. Inform the user where logs are going
    print(f"🧭 Open in browser: http://localhost:{port}")


def stop_ui():
    """
    Stop Treehopper UI
    """
    runtime = _get_runtime_dir()
    pid_file = runtime / "ui.pid"

    if not pid_file.exists():
        print("⚠️ Treehopper UI is not running")
        return

    pid = int(pid_file.read_text())

    try:
        os.kill(pid, signal.SIGTERM)
        pid_file.unlink()
        print(f"🛑 Treehopper UI stopped (PID {pid})")
    except ProcessLookupError:
        print("⚠️ UI process already stopped")
        pid_file.unlink()
    except Exception as e:
        print(f"❌ Failed to stop UI: {e}")
