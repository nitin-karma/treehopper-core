# treehopper/visualizer/db_init.py
# import os
# import time
from datetime import datetime, timezone
import bcrypt
from pathlib import Path
from treehopper.th_config import TH_ROOT, ROLES, PERM
from treehopper.logging import get_logger
from treehopper.visualizer.db_util import db
from treehopper.sync_to_sqlite import (
    init_registry_tables,
    init_subscription_table,
    get_subscription,
    sync_subscription,
    cleanup_duplicate_subscriptions,
    init_yaml_table,
)

logger = get_logger()


class DBInitializer:
    def __init__(self):
        self.db = db

    def init_db(self):
        is_new_db = not self.db.db_path.exists()
        logger.info(f"Initialising DB at {self.db.db_path} (new={is_new_db})")

        self.db.db_path.parent.mkdir(parents=True, exist_ok=True)

        # 0. Meta Table
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT)"
        )

        # 1. Schema Tables
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS roles (id INTEGER PRIMARY KEY, name TEXT UNIQUE)"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS permissions (id INTEGER PRIMARY KEY, name TEXT UNIQUE)"
        )
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS role_permissions (
                role_id INTEGER,
                permission_id INTEGER,
                FOREIGN KEY(role_id) REFERENCES roles(id),
                FOREIGN KEY(permission_id) REFERENCES permissions(id),
                UNIQUE(role_id, permission_id)
            )
        """
        )
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role_id INTEGER,
                subscription_id TEXT,
                needs_password_change BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(role_id) REFERENCES roles(id)
            )
        """
        )
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS analytics_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                event_type TEXT NOT NULL,
                run_id TEXT,
                chain_name TEXT,
                agent_name TEXT,
                step_id TEXT,
                subscription_id TEXT NOT NULL
            )
        """
        )

        # 2. Indexes
        self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_analytics_ts ON analytics_events(ts)"
        )
        self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_analytics_event_type ON analytics_events(event_type)"
        )
        self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_analytics_chain ON analytics_events(chain_name)"
        )
        self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_analytics_agent ON analytics_events(agent_name)"
        )

        # 3. ✅ Registry Tables (agents, chains, runs) + Phase 1: Subscription
        self._init_registry_tables()

        # 4. Seeding Logic
        if self._should_seed():
            logger.info("Seed data not present, Seeding.")
            self._seed_data()
            self._mark_seeded()
        else:
            logger.info("Seed data already present, skipping.")

    def _init_registry_tables(self):
        """
        Initialize all registry tables:
        - Phase 1: agents, chains, runs, subscription
        - Phase 2: yaml_content
        """
        try:
            # Core registry tables
            init_registry_tables()
            logger.info("✅ Registry tables initialized")

            # Phase 1: Subscription table
            init_subscription_table()
            logger.info("✅ Subscription table initialized")

            # Phase 2: YAML content cache table
            init_yaml_table()
            logger.info("✅ YAML content table initialized")

            # Seed subscription from file
            self._seed_subscription()

        except Exception as e:
            logger.error(f"Failed to init registry tables: {e}")

    def _seed_subscription(self):
        """
        Phase 1: Seed subscription table from subscription_id.txt (if exists)

        CRITICAL FIX: Cleans up duplicates first
        """
        try:
            # ✅ STEP 1: Clean up any duplicate subscriptions
            duplicates_removed = cleanup_duplicate_subscriptions()
            if duplicates_removed > 0:
                logger.warning(
                    f"Cleaned up {duplicates_removed} duplicate subscriptions"
                )

            # ✅ STEP 2: Check if subscription exists
            existing = get_subscription()
            if existing:
                logger.info(
                    f"Subscription already exists: {existing['subscription_id']}"
                )

                # Restore file if missing
                sub_file = Path(TH_ROOT) / "subscription_id.txt"
                if not sub_file.exists():
                    sub_file.write_text(existing["subscription_id"])
                    logger.info("Restored subscription_id.txt from database")

                return

            # ✅ STEP 3: No subscription in DB - check file
            sub_file = Path(TH_ROOT) / "subscription_id.txt"
            if sub_file.exists():
                sub_id = sub_file.read_text().strip()

                # Get file creation time

                # created_timestamp = os.path.getctime(sub_file)
                # created_at = datetime.fromtimestamp(created_timestamp).isoformat() + "Z"
                created_at = (
                    datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                )

                # Sync to database
                sync_subscription(
                    subscription_id=sub_id,
                    created_at=created_at,
                    status="active",
                    plan="trial",
                )
                logger.info(f"✅ Seeded subscription: {sub_id}")
            else:
                logger.info(
                    "No subscription_id.txt found, will be created on first use"
                )

        except Exception as e:
            logger.error(f"Failed to seed subscription: {e}")

    def _should_seed(self) -> bool:
        row = self.db.fetch_one("SELECT value FROM schema_meta WHERE key = 'seeded'")
        if row and row["value"] == "true":
            return False
        admin = self.db.fetch_one("SELECT id FROM users WHERE username = 'admin'")
        return admin is None

    def _mark_seeded(self):
        self.db.execute(
            "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
            ("seeded", "true"),
        )

    def _seed_data(self):
        for role in ROLES:
            self.db.execute("INSERT OR IGNORE INTO roles (name) VALUES (?)", (role,))
        for p in PERM:
            self.db.execute("INSERT OR IGNORE INTO permissions (name) VALUES (?)", (p,))

        admin_role = self.db.fetch_one("SELECT id FROM roles WHERE name = 'admin'")
        if admin_role:
            all_perms = self.db.fetch_all("SELECT id FROM permissions")
            for p in all_perms:
                self.db.execute(
                    "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                    (admin_role["id"], p["id"]),
                )

            if not self.db.fetch_one(
                "SELECT id FROM users WHERE username = ?", ("admin",)
            ):
                sub_id_path = Path(TH_ROOT) / "subscription_id.txt"
                sub_id = (
                    sub_id_path.read_text().strip()
                    if sub_id_path.exists()
                    else "trial_mode"
                )
                pwd_hash = bcrypt.hashpw(
                    "admin".encode("utf-8"), bcrypt.gensalt()
                ).decode("utf-8")

                self.db.execute(
                    "INSERT INTO users (username, password_hash, role_id, subscription_id, needs_password_change) VALUES (?, ?, ?, ?, ?)",
                    ("admin", pwd_hash, admin_role["id"], sub_id, 1),
                )
                logger.info("Default admin user created.")
