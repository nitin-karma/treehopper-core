import sqlite3
from pathlib import Path
from treehopper.th_config import TH_ROOT, DB_DIR, DASHBOARD_DB_NAME


def inspect():
    db_path = Path(TH_ROOT) / DB_DIR / DASHBOARD_DB_NAME
    if not db_path.exists():
        print(f"[-] Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    # Using Row factory allows us to access data by column name
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print(f"\n[!] FULL DATABASE INSPECTION: {db_path}")
    print("=" * 60)

    # Get list of all tables in the database
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
    )
    tables = [row["name"] for row in cursor.fetchall()]

    for table in tables:
        print(f"\n>>> TABLE: {table}")
        print("-" * 30)

        # 1. Show Schema/Columns
        cursor.execute(f"PRAGMA table_info({table})")
        cols = cursor.fetchall()
        col_names = [c["name"] for c in cols]
        print(f"Columns: {', '.join(col_names)}")

        # 2. Show All Data
        cursor.execute(f"SELECT * FROM {table}")
        rows = cursor.fetchall()

        if not rows:
            print("  (Table is empty)")
        else:
            for row in rows:
                # Convert row to dict to print keys and values clearly
                row_data = {k: row[k] for k in row.keys()}
                # Mask password hashes for security in console output
                if "password_hash" in row_data:
                    row_data["password_hash"] = "********"
                print(f"  {row_data}")

    conn.close()


if __name__ == "__main__":
    inspect()
