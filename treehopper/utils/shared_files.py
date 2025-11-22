from pathlib import Path

# import json
# import os

HOME = Path.home()
TH_ROOT = HOME / ".treehopper"
REGISTRY_DIR = TH_ROOT / "registry"
SHARED_DIR = REGISTRY_DIR / "shared"


def has_only_one_shared_file(agent_id: str) -> bool:
    """
    Returns True if this agent has exactly 1 uploaded file
    in ~/.treehopper/registry/shared/<agent_id>/files/
    """
    folder = SHARED_DIR / agent_id / "files"
    if not folder.is_dir():
        return False
    files = [f for f in folder.iterdir() if f.is_file()]
    return len(files) == 1


def get_the_only_shared_file(agent_id: str) -> str:
    """
    Returns the *relative* file_path string used by payload:
       shared/<agent_id>/files/<filename>
    Assumes exactly 1 file exists (call has_only_one_shared_file first).
    """
    folder = SHARED_DIR / agent_id / "files"
    for f in folder.iterdir():
        if f.is_file():
            return f"shared/{agent_id}/files/{f.name}"
    raise FileNotFoundError(f"No shared file found for agent {agent_id}")
