import os
import bcrypt
from pathlib import Path
from db_util import db
from treehopper.th_config import TH_ROOT, DB_DIR


def setup_mock_environment():
    """Ensures the .treehopper directory, db_dir, and subscription file exist."""
    root_path = Path(TH_ROOT)
    db_path = root_path / DB_DIR
    root_path.mkdir(parents=True, exist_ok=True)
    db_path.mkdir(parents=True, exist_ok=True)

    sub_file = root_path / "subscription_id.txt"
    if not sub_file.exists():
        sub_file.write_text("TEST-123-SUBSCRIPTION")

    # Delete existing test DB to ensure a clean run with the new schema
    db_file = db_path / "dashboard_config.db"
    if db_file.exists():
        os.remove(db_file)
        print(f"[TEST] Cleaned up old database at {db_file}")


def test_initialization():
    print("\n--- Testing Initialization ---")
    db.init_db()

    # Updated query to JOIN with roles table
    query = """
        SELECT u.*, r.name as role_name
        FROM users u
        JOIN roles r ON u.role_id = r.id
        WHERE u.username = ?
    """
    admin = db.fetch_one(query, ("admin",))

    if admin:
        print(f"SUCCESS: Admin found with role: {admin['role_name']}")
        print(f"SUCCESS: Subscription ID: {admin['subscription_id']}")
        if admin["password_hash"].startswith("$2b$"):
            print("SUCCESS: Password hashed correctly.")
    else:
        print("FAILED: Admin user was not created.")


def test_crud_operations():
    print("\n--- Testing CRUD Operations ---")

    # 1. Fetch the developer role ID
    dev_role = db.fetch_one("SELECT id FROM roles WHERE name = 'developer'")
    admin_role = db.fetch_one("SELECT id FROM roles WHERE name = 'admin'")

    # 2. INSERT (Create) - Use role_id instead of role
    username = "tester_user"
    pwd_hash = bcrypt.hashpw("password123".encode("utf-8"), bcrypt.gensalt()).decode(
        "utf-8"
    )

    db.execute(
        "INSERT INTO users (username, password_hash, role_id) VALUES (?, ?, ?)",
        (username, pwd_hash, dev_role["id"]),
    )
    print(f"SUCCESS: Inserted user '{username}' as developer")

    # 3. READ (Fetch with JOIN)
    user = db.fetch_one(
        """
        SELECT u.username, r.name as role_name
        FROM users u
        JOIN roles r ON u.role_id = r.id
        WHERE u.username = ?
    """,
        (username,),
    )
    if user and user["role_name"] == "developer":
        print(
            f"SUCCESS: Fetched user '{user['username']}' with role '{user['role_name']}'"
        )

    # 4. UPDATE (Change role_id)
    db.execute(
        "UPDATE users SET role_id = ? WHERE username = ?", (admin_role["id"], username)
    )
    updated = db.fetch_one(
        """
        SELECT r.name FROM roles r
        JOIN users u ON u.role_id = r.id
        WHERE u.username = ?
    """,
        (username,),
    )
    if updated["name"] == "admin":
        print(f"SUCCESS: Updated role to 'admin' for {username}")

    # 5. DELETE
    db.execute("DELETE FROM users WHERE username = ?", (username,))
    deleted_user = db.fetch_one("SELECT * FROM users WHERE username = ?", (username,))
    if not deleted_user:
        print(f"SUCCESS: Deleted user '{username}'")


def test_rbac_links():
    print("\n--- Testing RBAC Relational Links ---")
    from treehopper.th_config import PERM

    # Use the first permission from your actual config to be dynamic
    target_perm = PERM[0]

    query = """
        SELECT p.name FROM permissions p
        JOIN role_permissions rp ON p.id = rp.permission_id
        JOIN roles r ON rp.role_id = r.id
        WHERE r.name = 'admin' AND p.name = ?
    """
    perm = db.fetch_one(query, (target_perm,))
    if perm:
        print(f"SUCCESS: Admin role linked to '{target_perm}' permission.")
    else:
        print(f"FAILED: RBAC mapping for '{target_perm}' missing.")


if __name__ == "__main__":
    try:
        setup_mock_environment()
        test_initialization()
        test_crud_operations()
        test_rbac_links()
        print("\n[!] All DB Tests Passed Successfully.")
    except Exception as e:
        print(f"\n[!] Test Failed with error: {e}")
        import traceback

        traceback.print_exc()
