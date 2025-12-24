# tests/integration/test_maintainer.py

import os
import time
import sqlite3
import zipfile
from pathlib import Path

import pytest

# IMPORTANT: import module, not symbols
import treehopper.maintainance.maintainer as maintainer


@pytest.fixture()
def dummy_th_root(tmp_path, monkeypatch):
    root = tmp_path / ".treehopper"
    root.mkdir()

    (root / "runtime").mkdir()
    (root / "registry").mkdir()
    (root / "archive").mkdir()

    monkeypatch.setattr(maintainer, "TH_ROOT", root)
    monkeypatch.setattr(maintainer, "get_archive_dir", lambda: root / "archive")

    return root


@pytest.fixture()
def dummy_db(dummy_th_root, monkeypatch):
    db_path = dummy_th_root / "dashboard.db"

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE analytics_events (
            id INTEGER PRIMARY KEY,
            ts REAL,
            event_type TEXT
        )
        """
    )

    now = time.time()
    cur.executemany(
        "INSERT INTO analytics_events (ts, event_type) VALUES (?, ?)",
        [
            (now - 10 * 86400, "old_event"),
            (now - 100, "new_event"),
        ],
    )

    conn.commit()
    conn.close()

    monkeypatch.setattr(maintainer.db, "db_path", db_path)

    return db_path


def test_runtime_file_rotation(dummy_th_root):
    runtime = dummy_th_root / "runtime"

    f1 = runtime / "a.log"
    f2 = runtime / "b.jsonl"

    f1.write_text("log data")
    f2.write_text("event data")

    old = time.time() - (2 * 86400)
    os.utime(f1, (old, old))
    os.utime(f2, (old, old))

    rotator = maintainer.RuntimeFileRotator(
        root=dummy_th_root,
        max_dir_mb=0,
        max_file_age_days=1,
    )
    rotator.rotate()

    archives = list((dummy_th_root / "archive").glob("runtime-*.zip"))
    assert len(archives) == 1

    with zipfile.ZipFile(archives[0]) as z:
        names = z.namelist()
        assert "runtime/a.log" in names
        assert "runtime/b.jsonl" in names

    assert not f1.exists()
    assert not f2.exists()


def test_db_prune(dummy_db):
    mgr = maintainer.DBRetentionManager(dummy_db)
    mgr.prune(retain_days=5)

    conn = sqlite3.connect(dummy_db)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM analytics_events")
    count = cur.fetchone()[0]
    conn.close()

    assert count == 1


def test_db_snapshot(dummy_db, dummy_th_root):
    mgr = maintainer.DBRetentionManager(dummy_db)
    mgr.snapshot()

    snapshots = list((dummy_th_root / "archive").glob("dashboard-*.db"))
    assert len(snapshots) == 1


def test_archive_cleanup(dummy_th_root):
    archive = dummy_th_root / "archive"

    old = archive / "dashboard-2000-01-01.db"
    new = archive / f"dashboard-{time.strftime('%Y-%m-%d')}.db"

    old.write_text("old")
    new.write_text("new")

    mgr = maintainer.DBRetentionManager(Path("unused"))
    mgr.archive_and_cleanup()

    assert not old.exists()
    assert new.exists()


def test_storage_metrics(dummy_db, dummy_th_root):
    res = maintainer.storage_metrics()

    assert "db" in res
    assert "files" in res
    assert res["db"]["size_mb"] >= 0
    assert res["files"]["treehopper_mb"] >= 0


def test_startup_maintenance(dummy_db, dummy_th_root):
    maintainer.startup_maintenance()
    maintainer.startup_maintenance()


def test_admin_commands(dummy_db, dummy_th_root):
    maintainer.admin_snapshot_db()
    maintainer.admin_prune_db()
    maintainer.admin_rotate_files()
    maintainer.admin_cleanup_archives()
