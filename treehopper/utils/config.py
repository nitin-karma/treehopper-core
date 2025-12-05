import json
from pathlib import Path
from typing import Optional

CONFIG_PATH = Path.home() / ".treehopper" / "config.json"
DEFAULTS = {"auto_resume": False}


def read_config() -> dict:
    try:
        if CONFIG_PATH.exists():
            return json.loads(CONFIG_PATH.read_text())
    except Exception:
        pass
    return DEFAULTS.copy()


def write_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))


def read_pid_and_port(path: Path) -> tuple[Optional[int], Optional[int]]:
    print(f"treehopper.utils.config.read_pid_and_port - Path exists - {path}")
    if not path.exists():
        return None, None
    try:
        text = path.read_text().strip()
        if ":" in text:
            pid_str, port_str = text.split(":", 1)
            print(
                f"treehopper.utils.config.read_pid_and_port - pid - {pid_str} and port - {port_str}"
            )
            return int(pid_str), int(port_str)
        return int(text), None
    except Exception as e:
        print(f"from treehopper.utils.config.read_pid_and_port - {str(e)}")
        return None, None
