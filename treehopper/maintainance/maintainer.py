# treehopper/maintainance/maintainer.py

"""
Treehopper Maintenance & Retention Manager
=========================================

This module handles:
1. Runtime file rotation & archival (.log, .json, .jsonl, .cancel)
2. SQLite analytics DB pruning, vacuum, archival
3. Storage metrics for admin UI
4. Safe startup hooks
5. Admin CLI commands

Retention Defaults:
- Analytics DB max: 2 GB
- Soft prune at: 80%
- Live DB retain: 7 days
- Archive retain: 90 days
"""

from __future__ import annotations
import os
import time
import shutil
import zipfile
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict
from collections import Counter
from treehopper.logging import get_logger
from treehopper.th_config import (
    TH_ROOT,
    DB_MAX_MB,
    DB_WARN_PCT,
    DB_CRIT_PCT,
    LIVE_DB_RETAIN_DAYS,
    ARCHIVE_RETAIN_DAYS,
    ARCHIVE_DIR,
)
from treehopper.visualizer.db_util import db

logger = get_logger()

# ============================================================
# GLOBAL CONFIG
# ============================================================


def get_archive_dir() -> Path:
    """
    Resolve archive directory dynamically from current TH_ROOT.
    This is critical for test isolation.
    """
    # return Path(TH_ROOT) / "archive"
    return ARCHIVE_DIR


# get_archive_dir().mkdir(parents=True, exist_ok=True)


# ============================================================
# UTILITIES
# ============================================================


def _now_ts() -> float:
    return time.time()


def folder_size_mb(path: Path) -> float:
    if not path.exists():
        return 0.0
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            total += p.stat().st_size
    return total / (1024 * 1024)


def safe_unlink(p: Path):
    try:
        p.unlink()
    except Exception:
        pass


# ============================================================
# 1️⃣ RUNTIME FILE ROTATION / ARCHIVAL
# ============================================================


class RuntimeFileRotator:
    """
    Threshold-aware runtime file rotation.
    """

    ROTATABLE_SUFFIXES = {
        ".log",
        ".json",
        ".jsonl",
        ".cancel",
        ".pid",
    }

    def __init__(
        self,
        root: Path,
        max_dir_mb: int = 512,
        max_file_age_days: int = 1,
        max_files_per_type: int = 1000,
    ):
        self.root = root
        self.max_dir_mb = max_dir_mb
        self.max_file_age_sec = max_file_age_days * 86400
        self.max_files_per_type = max_files_per_type

    def rotate(self):
        logger.info("[maintainer] Runtime rotation check")
        print("[maintainer] Runtime rotation check")

        # --- 1️⃣ Check directory size threshold
        total_bytes = sum(p.stat().st_size for p in self.root.rglob("*") if p.is_file())
        total_mb = total_bytes / (1024 * 1024)

        # --- 2️⃣ Collect eligible files
        now = time.time()
        candidates: list[Path] = []
        suffix_counter = Counter()

        for p in self.root.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix not in self.ROTATABLE_SUFFIXES:
                continue

            age_ok = (now - p.stat().st_mtime) > self.max_file_age_sec
            suffix_counter[p.suffix] += 1

            if age_ok:
                candidates.append(p)

        # --- 3️⃣ Decide whether to rotate
        should_rotate = (
            total_mb >= self.max_dir_mb
            or any(v > self.max_files_per_type for v in suffix_counter.values())
            or bool(candidates)
        )

        if not should_rotate:
            logger.info("[maintainer] Runtime rotation skipped (within limits)")
            print("[maintainer] Runtime rotation skipped (within limits)")
            return

        # --- 4️⃣ Archive eligible files
        today = datetime.utcnow().strftime("%Y-%m-%d")
        archive_dir = get_archive_dir()
        # archive_dir.mkdir(parents=True, exist_ok=True)
        archive = archive_dir / f"runtime-{today}.zip"

        with zipfile.ZipFile(archive, "a", zipfile.ZIP_DEFLATED) as z:
            for f in candidates:
                try:
                    arcname = f.relative_to(self.root)
                    z.write(f, arcname=str(arcname))
                    safe_unlink(f)
                except Exception as e:
                    print("Failed to rotate %s: %s", f, e)
                    logger.warning("Failed to rotate %s: %s", f, e)
        print(f"[maintainer] Rotated {len(candidates)} files → {archive.name}")
        logger.info(f"[maintainer] Rotated {len(candidates)} files → {archive.name}")


# ============================================================
# 2️⃣ DB RETENTION / PRUNING / ARCHIVAL
# ============================================================


class DBRetentionManager:
    """
    Controls analytics DB growth and lifecycle.
    """

    def __init__(self, db_path: Path, archive_dir: Path | None = None):
        self.db_path = db_path
        self.archive_dir = archive_dir or get_archive_dir()

    def size_mb(self) -> float:
        if not self.db_path.exists():
            return 0.0
        return self.db_path.stat().st_size / (1024 * 1024)

    def usage_pct(self) -> float:
        return (self.size_mb() / DB_MAX_MB) * 100

    def prune(self, retain_days: int = LIVE_DB_RETAIN_DAYS):
        cutoff = _now_ts() - (retain_days * 86400)

        print(f"[maintainer] Pruning analytics_events older than {retain_days} days")

        logger.warning(
            f"[maintainer] Pruning analytics_events older than {retain_days} days"
        )

        db.execute(
            "DELETE FROM analytics_events WHERE ts < ?",
            (cutoff,),
        )
        db.execute("VACUUM")

    def snapshot(self):
        if not self.db_path.exists():
            return

        today = datetime.utcnow().strftime("%Y-%m-%d")
        archive_dir = get_archive_dir()
        # archive_dir.mkdir(parents=True, exist_ok=True)
        dest = archive_dir / f"dashboard-{today}.db"

        if dest.exists():
            return

        shutil.copy2(self.db_path, dest)

        print(f"[maintainer] DB snapshot created → {dest.name}")
        logger.info(f"[maintainer] DB snapshot created → {dest.name}")

    def archive_and_cleanup(self):
        print("[maintainer] archive_and_cleanup started")
        logger.info("[maintainer] archive_and_cleanup started")

        cutoff = datetime.utcnow() - timedelta(days=ARCHIVE_RETAIN_DAYS)
        archive_dir = get_archive_dir()

        for p in archive_dir.glob("*.db"):
            try:
                parts = p.stem.split("-")
                if len(parts) < 4:
                    continue

                date_str = "-".join(parts[-3:])  # YYYY-MM-DD
                dt = datetime.strptime(date_str, "%Y-%m-%d")

                if dt < cutoff:
                    safe_unlink(p)
            except Exception:
                continue

        print("[maintainer] archive_and_cleanup completed")
        logger.info("[maintainer] archive_and_cleanup completed")

    def health_check(self) -> str:
        pct = self.usage_pct()

        if pct >= DB_CRIT_PCT:
            print(f"[maintainer] 🚨 DB CRITICAL {pct}")
            logger.error(f"[maintainer] 🚨 DB CRITICAL {pct}")
            self.prune(retain_days=3)
            return "critical"

        if pct >= DB_WARN_PCT:
            print("[maintainer] ⚠️ DB WARNING {pct} %")
            logger.warning("[maintainer] ⚠️ DB WARNING {pct} %")
            return "warning"

        return "ok"


# ============================================================
# 3️⃣ STORAGE METRICS (ADMIN API)
# ============================================================


def storage_metrics() -> Dict:
    db_mgr = DBRetentionManager(db.db_path)
    res = {
        "db": {
            "path": str(db.db_path),
            "size_mb": round(db_mgr.size_mb(), 2),
            "limit_mb": DB_MAX_MB,
            "usage_pct": round(db_mgr.usage_pct(), 1),
        },
        "files": {
            "runtime_mb": round(folder_size_mb(TH_ROOT / "runtime"), 2),
            "events_mb": round(folder_size_mb(TH_ROOT / "registry"), 2),
            "archive_mb": round(folder_size_mb(get_archive_dir()), 2),
            "treehopper_mb": round(folder_size_mb(Path(TH_ROOT)), 2),
        },
        "thresholds": {
            "warning_pct": DB_WARN_PCT,
            "critical_pct": DB_CRIT_PCT,
        },
    }
    print(res)
    logger.info(res)
    return res


# ============================================================
# 4️⃣ STARTUP HOOK (SAFE)
# ============================================================


def startup_maintenance():
    # 🚫 NEVER run maintenance during tests or bootstrap
    if os.getenv("TH_TEST_MODE") == "1":
        print(
            f"[startup_maintenance] Skipping startup maintenance {os.getenv('TH_TEST_MODE')}"
        )
        logger.info(
            f"[startup_maintenance] Skipping startup maintenance {os.getenv('TH_TEST_MODE')}"
        )
        return
    logger.info("[maintainer] Startup maintenance begin")

    # DB Init
    # db.init_db()

    # Runtime File Rotation and maintainance
    RuntimeFileRotator(
        root=Path(TH_ROOT / "runtime"),
        max_dir_mb=512,
        max_file_age_days=1,
    ).rotate()

    # Dashboard DB retention manager
    DBRetentionManager(db.db_path).health_check()

    logger.info("[maintainer] Startup maintenance complete")


# ============================================================
# 5️⃣ ADMIN CLI COMMANDS
# ============================================================


def admin_snapshot_db():
    DBRetentionManager(db.db_path).snapshot()


def admin_prune_db():
    DBRetentionManager(db.db_path).prune()


def admin_cleanup_archives():
    DBRetentionManager(db.db_path).archive_and_cleanup()


def admin_rotate_files():
    RuntimeFileRotator(Path(TH_ROOT) / "runtime").rotate()


# ============================================================
# 6️⃣ maintenance.sh (REFERENCE)
# ============================================================

MAINTENANCE_SH = """#!/bin/bash
# Treehopper Daily Maintenance

treehopper admin snapshot-db
treehopper admin prune-db
treehopper admin rotate-files
treehopper admin cleanup-archives
"""
