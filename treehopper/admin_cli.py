# treehopper/admin_cli.py

from treehopper.maintainance.maintainer import (
    admin_snapshot_db,
    admin_prune_db,
    admin_rotate_files,
    admin_cleanup_archives,
    storage_metrics,
)


def admin_entry(argv: list[str]):
    if len(argv) < 1:
        print_admin_help()
        return

    sub = argv[0]

    if sub == "snapshot-db":
        admin_snapshot_db()
    elif sub == "prune-db":
        admin_prune_db()
    elif sub == "rotate-files":
        admin_rotate_files()
    elif sub == "cleanup-archives":
        admin_cleanup_archives()
    elif sub == "storage":
        metrics = storage_metrics()
        print_storage(metrics)
    else:
        print(f"❌ Unknown admin command: {sub}")
        print_admin_help()


def print_admin_help():
    print(
        """
treehopper admin <command>

Commands:
  snapshot-db        Snapshot analytics DB
  prune-db           Prune analytics DB (retention policy)
  rotate-files       Rotate runtime files (.log, .jsonl, .cancel, etc)
  cleanup-archives   Remove expired archives
  storage            Show storage metrics
"""
    )


def print_storage(m):
    print("\n📦 Treehopper Storage Metrics\n")
    for k, v in m.items():
        print(f"{k:25} : {v}")
