# treehopper/visualiser/inspect_db.py

import sqlite3
import click
from pathlib import Path
from tabulate import tabulate
from treehopper.th_config import TH_ROOT, DB_DIR, DASHBOARD_DB_NAME


def run_view_db(show_tables=False, table=None, limit=20, search=None, show_all=False):
    """Core logic extracted from Click so it can be called by argparse or Click."""
    db_path = Path(TH_ROOT) / DB_DIR / DASHBOARD_DB_NAME

    if not db_path.exists():
        print(f"❌ Database not found at {db_path}")
        return

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get all table names for use in 'show_tables' or 'show_all'
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        )
        all_tables = [t["name"] for t in cursor.fetchall()]

        if show_tables:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
            )
            tables = cursor.fetchall()
            table_data = []
            for t in tables:
                t_name = t["name"]
                cursor.execute(f"SELECT COUNT(*) FROM {t_name}")
                count = cursor.fetchone()[0]
                table_data.append([t_name, count])
            print(
                tabulate(
                    table_data,
                    headers=["Table Name", "Total Rows"],
                    tablefmt="rounded_grid",
                )
            )

        # --- MODE 2: SHOW ALL TABLES (LATEST RECORDS) ---
        elif show_all:
            print(f"\n🚀 Full Database Inspection (Latest {limit} records per table)")
            for t_name in all_tables:
                print(f"\n📂 TABLE: {t_name}")
                # We attempt to sort by 'id' or 'created_at' if they exist, otherwise just limit
                cursor.execute(f"PRAGMA table_info({t_name})")
                cols = [c["name"] for c in cursor.fetchall()]

                order_by = ""
                if "id" in cols:
                    order_by = " ORDER BY id DESC"
                elif "created_at" in cols:
                    order_by = " ORDER BY created_at DESC"

                cursor.execute(f"SELECT * FROM {t_name}{order_by} LIMIT {limit}")
                rows = cursor.fetchall()

                if not rows:
                    print("  (Empty)")
                    continue

                formatted = []
                for r in rows:
                    d = dict(r)
                    if "password_hash" in d:
                        d["password_hash"] = "********"
                    formatted.append(list(d.values()))

                print(tabulate(formatted, headers=cols, tablefmt="rounded_grid"))

        elif table:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [c["name"] for c in cursor.fetchall()]
            if not columns:
                print(f"❌ Error: Table '{table}' does not exist.")
                return

            query = f"SELECT * FROM {table}"
            params = []
            if search:
                search_conditions = [f"CAST({col} AS TEXT) LIKE ?" for col in columns]
                query += " WHERE " + " OR ".join(search_conditions)
                params = [f"%{search}%"] * len(columns)

            query += f" LIMIT {limit}"
            cursor.execute(query, params)
            rows = cursor.fetchall()

            if not rows:
                print(
                    f"ℹ️  No results found in '{table}'"
                    + (f" matching '{search}'" if search else "")
                )
                return

            formatted_rows = []
            for row in rows:
                dict_row = dict(row)
                if "password_hash" in dict_row:
                    dict_row["password_hash"] = "********"
                formatted_rows.append(list(dict_row.values()))

            print(tabulate(formatted_rows, headers=columns, tablefmt="rounded_grid"))
    finally:
        if conn:
            conn.close()


# The Click wrapper (keep this if you still want to use Click elsewhere)
@click.command(name="db")
@click.option("--show-tables", is_flag=True)
@click.option("--table", type=str)
@click.option("--limit", default=20, type=int)
@click.option("--search", "-s", type=str)
def view_db_click(show_tables, table, limit, search):
    run_view_db(show_tables, table, limit, search)
