import sqlite3
import json
from pathlib import Path
from tabulate import tabulate
from treehopper.th_config import TH_ROOT, DB_DIR, DASHBOARD_DB_NAME


def print_records(data, headers):
    """Prints data in a key-value format."""
    for i, row in enumerate(data, 1):
        print(f"\n--- Record {i} ---")
        for header, value in zip(headers, row):
            print(f"{header:<20}: {value}")
    print("-" * 30)


def run_view_db(
    show_tables=False,
    table=None,
    limit=20,
    search=None,
    show_all=False,
    as_tables=True,
    as_json=False,
):
    db_path = Path(TH_ROOT) / DB_DIR / DASHBOARD_DB_NAME

    if not db_path.exists():
        print(f"❌ Database not found at {db_path}")
        return

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        )
        all_tables = [t["name"] for t in cursor.fetchall()]

        # --- MODE 1: SHOW TABLES ---
        if show_tables:
            table_data = []
            for t_name in all_tables:
                cursor.execute(f"SELECT COUNT(*) FROM {t_name}")
                count = cursor.fetchone()[0]
                table_data.append({"table": t_name, "count": count})

            if as_json:
                print(json.dumps(table_data, indent=4))
            elif as_tables:
                print(
                    tabulate(
                        [list(d.values()) for d in table_data],
                        headers=["Table Name", "Total Rows"],
                        tablefmt="rounded_grid",
                    )
                )
            else:
                for item in table_data:
                    print(f"Table: {item['table']:<20} | Rows: {item['count']}")

        # --- MODE 2 & 3: DATA RETRIEVAL (Table or All) ---
        elif table or show_all:
            target_tables = all_tables if show_all else [table]
            results_map = {}

            for t_name in target_tables:
                cursor.execute(f"PRAGMA table_info({t_name})")
                cols = [c["name"] for c in cursor.fetchall()]

                order_by = ""
                if "id" in cols:
                    order_by = " ORDER BY id DESC"
                elif "created_at" in cols:
                    order_by = " ORDER BY created_at DESC"

                query = f"SELECT * FROM {t_name}{order_by}"
                params = []
                if search:
                    search_conditions = [f"CAST({col} AS TEXT) LIKE ?" for col in cols]
                    query += " WHERE " + " OR ".join(search_conditions)
                    params = [f"%{search}%"] * len(cols)

                query += f" LIMIT {limit}"
                cursor.execute(query, params)
                rows = cursor.fetchall()

                # Process rows into dicts
                processed_data = []
                for r in rows:
                    d = dict(r)
                    if "password_hash" in d:
                        d["password_hash"] = "********"
                    processed_data.append(d)

                results_map[t_name] = processed_data

            # Output rendering
            if as_json:
                print(
                    json.dumps(
                        results_map if show_all else list(results_map.values())[0],
                        indent=4,
                    )
                )
            else:
                for t_name, data in results_map.items():
                    if show_all:
                        print(f"\n📂 TABLE: {t_name}")
                    if not data:
                        print("  (Empty)")
                        continue

                    headers = list(data[0].keys())
                    rows = [list(d.values()) for d in data]

                    if as_tables:
                        print(tabulate(rows, headers=headers, tablefmt="rounded_grid"))
                    else:
                        print_records(rows, headers)
    finally:
        if conn:
            conn.close()
