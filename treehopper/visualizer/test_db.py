import bcrypt
import traceback
from pathlib import Path

# 1. REDIRECT DB PATH BEFORE IMPORTS
from treehopper.visualizer.db_util import db

# Now import the rest
from treehopper.visualizer.db_init import DBInitializer
from treehopper.th_config import TH_ROOT


TEST_DB_FILE = "test_dashboard_init.db"
TEST_DB_PATH = Path(TEST_DB_FILE)
db.db_path = TEST_DB_PATH


def setup_test_environment():
    """Ensures a clean starting point using the test database path."""
    print(f"🛠️  Setting up test environment: {TEST_DB_FILE}")

    # Ensure root path exists for subscription_id.txt (required by DBInitializer)
    root_path = Path(TH_ROOT)
    root_path.mkdir(parents=True, exist_ok=True)

    sub_file = root_path / "subscription_id.txt"
    if not sub_file.exists():
        sub_file.write_text("TEST-123-SUBSCRIPTION")

    # Force delete existing test DB if it exists from a crashed previous run
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


def test_initialization():
    print("\n--- 1. Testing Initialization ---")
    dbInit = DBInitializer()
    dbInit.init_db()

    query = """
        SELECT u.*, r.name as role_name
        FROM users u
        JOIN roles r ON u.role_id = r.id
        WHERE u.username = ?
    """
    admin = db.fetch_one(query, ("admin",))

    if admin:
        print(f"✅ SUCCESS: Admin found with role: {admin['role_name']}")
        print(f"✅ SUCCESS: Subscription ID: {admin['subscription_id']}")
        if admin["password_hash"].startswith("$2b$"):
            print("✅ SUCCESS: Password hashed correctly.")
    else:
        raise Exception("FAILED: Admin user was not created.")


def test_crud_operations():
    print("\n--- 2. Testing CRUD Operations ---")

    # 1. Fetch Role IDs
    dev_role = db.fetch_one("SELECT id FROM roles WHERE name = 'developer'")
    admin_role = db.fetch_one("SELECT id FROM roles WHERE name = 'admin'")

    # 2. CREATE
    username = "tester_user"
    # Note: Using a strong password to satisfy potential backend logic
    pwd_hash = bcrypt.hashpw("SecurePass123!".encode("utf-8"), bcrypt.gensalt()).decode(
        "utf-8"
    )

    db.execute(
        "INSERT INTO users (username, password_hash, role_id) VALUES (?, ?, ?)",
        (username, pwd_hash, dev_role["id"]),
    )
    print(f"✅ SUCCESS: Inserted user '{username}' as developer")

    # 3. READ
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
            f"✅ SUCCESS: Fetched user '{user['username']}' with role '{user['role_name']}'"
        )

    # 4. UPDATE
    db.execute(
        "UPDATE users SET role_id = ? WHERE username = ?", (admin_role["id"], username)
    )
    updated = db.fetch_one(
        "SELECT r.name FROM roles r JOIN users u ON u.role_id = r.id WHERE u.username = ?",
        (username,),
    )
    if updated["name"] == "admin":
        print(f"✅ SUCCESS: Updated role to 'admin' for {username}")

    # 5. DELETE
    db.execute("DELETE FROM users WHERE username = ?", (username,))
    deleted_user = db.fetch_one("SELECT * FROM users WHERE username = ?", (username,))
    if not deleted_user:
        print(f"✅ SUCCESS: Deleted user '{username}'")


def test_rbac_links():
    print("\n--- 3. Testing RBAC Relational Links ---")
    from treehopper.th_config import PERM

    target_perm = PERM[0]
    query = """
        SELECT p.name FROM permissions p
        JOIN role_permissions rp ON p.id = rp.permission_id
        JOIN roles r ON rp.role_id = r.id
        WHERE r.name = 'admin' AND p.name = ?
    """
    perm = db.fetch_one(query, (target_perm,))
    if perm:
        print(f"✅ SUCCESS: Admin role linked to '{target_perm}' permission.")
    else:
        raise Exception(f"FAILED: RBAC mapping for '{target_perm}' missing.")


if __name__ == "__main__":
    try:
        setup_test_environment()
        test_initialization()
        test_crud_operations()
        test_rbac_links()
        print("\n✨ All Database Integration Tests Passed.")

    except Exception as e:
        print(f"\n❌ Test Failed: {e}")
        traceback.print_exc()

    finally:
        # CLEANUP: Delete the test database file
        if TEST_DB_PATH.exists():
            try:
                TEST_DB_PATH.unlink()
                print(f"\n🗑️  Cleanup: Deleted test database {TEST_DB_FILE}")
            except Exception as cleanup_error:
                print(f"\n⚠️  Cleanup failed: {cleanup_error}")
