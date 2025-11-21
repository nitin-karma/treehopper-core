#!/usr/bin/env python3
import sys
import subprocess
from pathlib import Path

SCRIPT_NAME = "th_clean.sh"


def find_script() -> Path | None:
    """
    Search for th_clean.sh in:
      • current working directory
      • root of project (where treehopper_cli lives)
      • ~/.treehopper/tools
    """
    cwd = Path.cwd() / SCRIPT_NAME
    if cwd.exists():
        return cwd

    project = Path(__file__).resolve().parent / SCRIPT_NAME
    if project.exists():
        return project

    tools = Path.home() / ".treehopper" / "tools" / SCRIPT_NAME
    if tools.exists():
        return tools

    return None


def main():
    auto_yes = "-y" in sys.argv or "--yes" in sys.argv

    script = find_script()
    if not script:
        print(f"❌ Could not locate {SCRIPT_NAME}")
        print("Ensure it exists in project root or ~/.treehopper/tools/")
        sys.exit(1)

    if not auto_yes:
        print("⚠️ Cleanup will delete:")
        print("   • server logs")
        print("   • installed agents")
        print("   • chain registry")
        print("   • shared files")
        print("   • chroma memory")
        print("   • runtime PIDs")
        print("🚫 subscription_id.txt will be preserved")
        ans = input("Proceed? (y/N): ")
        if ans.lower() not in ("y", "yes"):
            print("❎ Cancelled")
            sys.exit(0)

    print(f"🚀 Running cleanup via {script} ...")
    subprocess.run(["bash", str(script)] + (["-y"] if auto_yes else []))
    print("✨ Cleanup finished")


if __name__ == "__main__":
    main()
