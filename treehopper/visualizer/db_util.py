import sqlite3
import bcrypt
from pathlib import Path
from treehopper.th_config import TH_ROOT, DB_DIR, DASHBOARD_DB_NAME, ROLES, PERM
from treehopper.logging import get_logger

logger = get_logger()


class DBManager:
    def __init__(self):
        self.db_path = Path(TH_ROOT) / DB_DIR / DASHBOARD_DB_NAME

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def execute(self, query, params=()):
        logger.debug(f"Executing Query: {query} | Params: {params}")
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def fetch_one(self, query, params=()):
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            return cursor.fetchone()
        finally:
            conn.close()

    def fetch_all(self, query, params=()):
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            return cursor.fetchall()
        finally:
            conn.close()

    def _should_seed(self) -> bool:
        # Check schema_meta first
        row = self.fetch_one("SELECT value FROM schema_meta WHERE key = 'seeded'")
        if row and row["value"] == "true":
            return False

        # Fallback: admin user presence
        admin = self.fetch_one("SELECT id FROM users WHERE username = 'admin'")
        return admin is None

    def _mark_seeded(self):
        self.execute(
            "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
            ("seeded", "true"),
        )

    def init_db(self):
        is_new_db = not self.db_path.exists()
        logger.info(f"Initialising DB at {self.db_path} (new={is_new_db})")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )
        # 1. Roles Table
        self.execute(
            "CREATE TABLE IF NOT EXISTS roles (id INTEGER PRIMARY KEY, name TEXT UNIQUE)"
        )

        # 2. Permissions Table
        self.execute(
            "CREATE TABLE IF NOT EXISTS permissions (id INTEGER PRIMARY KEY, name TEXT UNIQUE)"
        )

        # 3. Role-Permissions Join Table (Added UNIQUE constraint to prevent duplicates)
        self.execute(
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

        # 4. Users Table
        self.execute(
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
            );
        """
        )

        # 5. Analytics Events Table
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS analytics_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,                  -- epoch seconds
                event_type TEXT NOT NULL,          -- step_start, agent_start, etc
                run_id TEXT,
                chain_name TEXT,
                agent_name TEXT,
                step_id TEXT,
                subscription_id TEXT NOT NULL
            );
            """
        )

        # Helpful indexes
        self.execute(
            "CREATE INDEX IF NOT EXISTS idx_analytics_ts ON analytics_events(ts)"
        )
        self.execute(
            "CREATE INDEX IF NOT EXISTS idx_analytics_event_type ON analytics_events(event_type)"
        )
        self.execute(
            "CREATE INDEX IF NOT EXISTS idx_analytics_chain ON analytics_events(chain_name)"
        )
        self.execute(
            "CREATE INDEX IF NOT EXISTS idx_analytics_agent ON analytics_events(agent_name)"
        )

        if self._should_seed():
            logger.info("Seed data not present, Seeding.")
            self._seed_data()
            self._mark_seeded()
        else:
            logger.info("Seed data already present, skipping.")

    def _seed_data(self):
        logger.info("Seeding roles and permissions...")

        # Insert Roles from config
        for role in ROLES:
            self.execute("INSERT OR IGNORE INTO roles (name) VALUES (?)", (role,))

        # Insert Permissions from config
        for p in PERM:
            self.execute("INSERT OR IGNORE INTO permissions (name) VALUES (?)", (p,))

        # Assign all permissions to 'admin'
        admin_role = self.fetch_one("SELECT id FROM roles WHERE name = 'admin'")
        if admin_role:
            all_perms = self.fetch_all("SELECT id FROM permissions")
            for p in all_perms:
                # INSERT OR IGNORE works here because of the UNIQUE constraint added above
                self.execute(
                    "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                    (admin_role["id"], p["id"]),
                )

        # Default Admin User
        if not self.fetch_one("SELECT id FROM users WHERE username = ?", ("admin",)):
            sub_id_path = Path(TH_ROOT) / "subscription_id.txt"
            sub_id = (
                sub_id_path.read_text().strip()
                if sub_id_path.exists()
                else "trial_mode"
            )

            # Default hash for "admin"
            pwd_hash = bcrypt.hashpw("admin".encode("utf-8"), bcrypt.gensalt()).decode(
                "utf-8"
            )

            if admin_role:
                self.execute(
                    """INSERT INTO users
                       (username, password_hash, role_id, subscription_id, needs_password_change)
                       VALUES (?, ?, ?, ?, ?)""",
                    ("admin", pwd_hash, admin_role["id"], sub_id, 1),
                )
                logger.info("Default admin user created.")


db = DBManager()
