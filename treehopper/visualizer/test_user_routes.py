import pytest
from pathlib import Path
from fastapi.testclient import TestClient

# 1. DATABASE ISOLATION
# Force the global DB instance to use a temporary test file
from treehopper.visualizer.db_util import db

# Import app and initializer after the path override
from treehopper.visualizer.app import app
from treehopper.visualizer.db_init import DBInitializer
from treehopper.th_config import DASHBOARD_HEADER

TEST_DB_FILE = "test_dashboard.db"
TEST_DB_PATH = Path(TEST_DB_FILE)
db.db_path = TEST_DB_PATH


# Standard valid password for tests to satisfy backend validation
VALID_PWD = "SecurePassword123!"

# Initialize client with the custom security header required by TreehopperAI
client = TestClient(app, headers={"x-requested-with": DASHBOARD_HEADER})


@pytest.fixture(scope="module", autouse=True)
def manage_test_db():
    """
    Handles the lifecycle of the test database.
    Ensures a clean slate before tests and deletes the file after.
    """
    # Cleanup any leftover DB from previous runs
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

    try:
        # Initialize and seed the fresh test database
        db_init = DBInitializer()
        db_init.init_db()

        yield  # Execute tests

    finally:
        # ALWAYS delete the test database after the module is done
        if TEST_DB_PATH.exists():
            try:
                TEST_DB_PATH.unlink()
                print(f"\n🗑️  Successfully deleted {TEST_DB_FILE}")
            except Exception as e:
                print(f"\n⚠️  Cleanup warning: Could not delete {TEST_DB_FILE}: {e}")


def get_admin_token():
    """Helper to get a valid JWT for the seeded admin user."""
    # Note: If your seeding uses 'admin' as the default password, it must meet
    # the criteria or be handled specifically in your seeding logic.
    response = client.post(
        "/api/v1/users/login", json={"username": "admin", "password": "admin"}
    )
    if response.status_code != 200:
        pytest.fail(f"Setup Error: Admin login failed. {response.json()}")
    return response.json()["access_token"]


# -------------------------------------------------------------------
# 1. Authentication & Identity
# -------------------------------------------------------------------


def test_login_success_returns_jwt():
    """Verify that valid credentials return a JWT and correct role."""
    response = client.post(
        "/api/v1/users/login", json={"username": "admin", "password": "admin"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["role"] == "admin"


def test_login_invalid_credentials():
    """Verify that wrong passwords return 401."""
    response = client.post(
        "/api/v1/users/login",
        json={"username": "admin", "password": "WrongPassword123!"},
    )
    assert response.status_code == 401


# -------------------------------------------------------------------
# 2. RBAC & User Creation (Validating Security Rules)
# -------------------------------------------------------------------


def test_add_user_as_admin():
    """Verify admin can create a developer with a valid strong password."""
    token = get_admin_token()
    headers = {"Authorization": f"Bearer {token}"}

    new_user = {"username": "dev_user", "password": VALID_PWD, "role": "developer"}

    response = client.post("/api/v1/users/add", json=new_user, headers=headers)
    assert response.status_code == 200, f"Failed with: {response.json()}"
    assert "created successfully" in response.json()["message"]


def test_add_user_weak_password_fails():
    """Verify that weak passwords return 400 Bad Request."""
    token = get_admin_token()
    headers = {"Authorization": f"Bearer {token}"}

    weak_user = {"username": "weakling", "password": "123", "role": "developer"}
    response = client.post("/api/v1/users/add", json=weak_user, headers=headers)

    assert response.status_code == 400
    assert "Password must contain" in response.json()["detail"]


def test_developer_permission_denied():
    """Verify 'developer' role cannot create other users."""
    admin_token = get_admin_token()

    # Create the developer
    client.post(
        "/api/v1/users/add",
        json={"username": "dev_block", "password": VALID_PWD, "role": "developer"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # Login as dev
    res = client.post(
        "/api/v1/users/login", json={"username": "dev_block", "password": VALID_PWD}
    )
    dev_token = res.json()["access_token"]

    # Attempt unauthorized action
    res = client.post(
        "/api/v1/users/add",
        json={"username": "hacker", "password": VALID_PWD, "role": "admin"},
        headers={"Authorization": f"Bearer {dev_token}"},
    )
    assert res.status_code == 403


# -------------------------------------------------------------------
# 3. Data Integrity & Deletion
# -------------------------------------------------------------------


def test_admin_cannot_delete_self():
    """Verify safety check prevents deleting the main admin account."""
    token = get_admin_token()
    headers = {"Authorization": f"Bearer {token}"}

    response = client.delete("/api/v1/users/admin", headers=headers)
    assert response.status_code == 400
    assert "Cannot delete root admin" in response.json()["detail"]


def test_delete_user_flow():
    """Verify creation and subsequent deletion of a user."""
    token = get_admin_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Add
    client.post(
        "/api/v1/users/add",
        json={"username": "temp", "password": VALID_PWD, "role": "developer"},
        headers=headers,
    )

    # Delete
    response = client.delete("/api/v1/users/temp", headers=headers)
    assert response.status_code == 200

    # Verify gone from list
    res_verify = client.get("/api/v1/users/list", headers=headers)
    usernames = [u["username"] for u in res_verify.json()]
    assert "temp" not in usernames
