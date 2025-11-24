#!/usr/bin/env python3
import sys
import subprocess
from pathlib import Path

SCRIPT_NAME = "th_tools/th_clean.sh"


def find_script() -> Path | None:
    """
    Look for th_clean.sh in a predictable fixed order:
      1) Parent directory of this file (treehopper-core/)
      2) Current working directory (in case user runs from root)
      3) ~/.treehopper/tools/th_clean.sh (override)
    """

    # 1) parent of this file  → treehopper-core/
    parent = Path(__file__).resolve().parent.parent / SCRIPT_NAME

    if parent.exists():
        return parent

    # 2) current directory
    cwd = Path.cwd() / SCRIPT_NAME
    if cwd.exists():
        return cwd

    # 3) optional user tools folder
    fallback = Path.home() / ".treehopper" / "tools" / SCRIPT_NAME
    if fallback.exists():
        return fallback

    return None


def main():
    auto_yes = "-y" in sys.argv or "--yes" in sys.argv

    script = find_script()
    print(f"Cleanup Script path - {script}")
    if not script:
        print("❌ th_clean.sh not found")
        print("Expected one of:")
        print("  • treehopper-core/scripts/th_clean.sh")
        print("  • current working directory")
        # print("  • ~/.treehopper/tools/th_clean.sh")
        sys.exit(1)

    if not auto_yes:
        print("⚠️ Cleanup will delete:")
        print("   • server / agents / chains logs")
        print("   • installed agents")
        print("   • chains registry")
        print("   • shared uploads")
        print("   • chroma DB memory")
        print("   • runtime PID files")
        print("🚫 subscription_id.txt will NOT be deleted")
        ans = input("Proceed? (y/N): ")
        if ans.lower() not in ("y", "yes"):
            print("❎ Cancelled")
            sys.exit(0)

    print(f"🧹 Running cleanup via {script} ...")
    cmd = ["bash", str(script)]
    if auto_yes:
        cmd.append("-y")

    subprocess.run(cmd)
    print("✨ Cleanup finished successfully")


if __name__ == "__main__":
    main()
