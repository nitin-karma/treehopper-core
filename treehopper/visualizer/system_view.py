# treehopper/visualizer/system_view.py
# import os
# import re
import platform
import subprocess
from pathlib import Path
from rich.console import Console
from rich.tree import Tree
from treehopper.th_config import TH_ROOT, RUNTIME_DIR


console = Console()


def show_root_tree():
    """Displays the TH_ROOT directory structure as a visual tree."""
    root_path = Path(TH_ROOT).expanduser().resolve()

    if not root_path.exists():
        console.print(f"[bold red]❌ TH_ROOT does not exist at:[/bold red] {root_path}")
        return

    console.print(
        f"\n[bold cyan]📂 Treehopper Root Directory:[/bold cyan] [green]{root_path}[/green]\n"
    )

    # Create the Rich Tree
    tree = Tree(f"🏠 [bold blue]{root_path.name}[/bold blue]")

    def add_path(current_path: Path, current_tree: Tree):
        # Sort to show directories first, then files
        paths = sorted(current_path.iterdir(), key=lambda p: (p.is_file(), p.name))

        for path in paths:
            # Skip hidden files and common ignore folders if you prefer
            if path.name.startswith(".") or path.name == "__pycache__":
                continue

            if path.is_dir():
                branch = current_tree.add(f"📁 [bold yellow]{path.name}[/bold yellow]")
                add_path(path, branch)
            else:
                current_tree.add(f"📄 {path.name}")

    add_path(root_path, tree)
    console.print(tree)
    print("")


def get_live_port(pid):
    """Detects port for a PID across macOS, Linux, and Windows."""
    current_os = platform.system().lower()
    pid_str = str(pid).strip()

    try:
        if current_os in ["darwin", "linux"]:
            # Robust lsof check
            result = subprocess.check_output(
                ["lsof", "-nP", "-i", "-a", "-p", pid_str],
                stderr=subprocess.DEVNULL,
                text=True,
            )

            for line in result.splitlines():
                if "LISTEN" in line or "(LISTEN)" in line:
                    parts = line.split()
                    # Address is typically the last column
                    name_col = parts[-1] if "(LISTEN)" not in line else parts[-2]
                    if ":" in name_col:
                        return name_col.split(":")[-1]

        elif current_os == "windows":
            result = subprocess.check_output(
                ["netstat", "-ano"], stderr=subprocess.DEVNULL, text=True
            )
            for line in result.splitlines():
                if "LISTENING" in line and line.strip().endswith(pid_str):
                    parts = line.split()
                    return parts[1].split(":")[-1]
    except Exception:
        pass

    return "N/A"


def show_pids():
    """Lists active PID files, supporting comma or colon separators."""
    runtime_path = Path(RUNTIME_DIR).expanduser().resolve()

    console.print(
        f"\n[bold cyan]🆔 Active Runtimes (PIDs):[/bold cyan] [dim]{runtime_path}[/dim]\n"
    )

    pid_files = list(runtime_path.glob("*.pid"))
    if not pid_files:
        console.print("  [italic yellow]No active PIDs found.[/italic yellow]\n")
        return

    print(f"{'FILENAME':<40} | {'PID':<10} | {'PORT (File)':<12} | {'LIVE PORT'}")
    print("-" * 80)

    for pf in pid_files:
        try:
            raw_content = pf.read_text().strip()

            # --- IMPROVED PARSING LOGIC ---
            # Handles '47717:20158', '47717,20158', or just '47717'
            if ":" in raw_content:
                pid, file_port = raw_content.split(":", 1)
            elif "," in raw_content:
                pid, file_port = raw_content.split(",", 1)
            else:
                pid, file_port = raw_content, "N/A"

            # Clean up whitespace
            pid = pid.strip()
            file_port = file_port.strip()

            # 2. Cross-verify with live system data
            live_port = get_live_port(pid)

            # Visual Logic
            is_active = live_port != "N/A"
            port_display = (
                f"[green]{live_port}[/green]" if is_active else "[red]CLOSED[/red]"
            )

            console.print(
                f"{pf.name:<40} | {pid:<10} | {file_port:<12} | {port_display}"
            )

        except Exception as e:
            console.print(f"{pf.name:<40} | [red]Error: {e}[/red]")
    print("")
