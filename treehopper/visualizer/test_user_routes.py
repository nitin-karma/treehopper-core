import pytest

# import os
from fastapi.testclient import TestClient
from treehopper.visualizer.app import app
from treehopper.visualizer.db_util import db
from treehopper.th_config import DASHBOARD_HEADER

# Initialize the TestClient with the required UI security header
client = TestClient(app, headers={"x-requested-with": DASHBOARD_HEADER})


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    """Initializes the database and ensures a clean state for the test module."""
    db.init_db()

    try:
        token = get_admin_token()
        headers = {"Authorization": f"Bearer {token}"}
        # List of usernames used throughout the test to clean up
        test_users = ["dev_user", "dev1", "hacker", "bye"]
        for user in test_users:
            client.delete(f"/api/v1/users/{user}", headers=headers)
    except Exception as e:
        print(str(e))
        # If admin login fails during setup, it's likely the first run
        # or DB is empty; we can proceed as the tests will catch specific errors.
        pass


def get_admin_token():
    """Helper to get a valid JWT for the root admin user."""
    response = client.post(
        "/api/v1/users/login", json={"username": "admin", "password": "admin"}
    )
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
    assert data["token_type"] == "bearer"


def test_login_invalid_credentials():
    """Verify that wrong passwords return 401 Unauthorized."""
    response = client.post(
        "/api/v1/users/login", json={"username": "admin", "password": "wrongpassword"}
    )
    assert response.status_code == 401


# -------------------------------------------------------------------
# 2. RBAC (Role-Based Access Control)
# -------------------------------------------------------------------


def test_add_user_as_admin():
    """Verify admin can create a developer."""
    token = get_admin_token()
    headers = {"Authorization": f"Bearer {token}"}

    new_user = {"username": "dev_user", "password": "password123", "role": "developer"}

    response = client.post("/api/v1/users/add", json=new_user, headers=headers)
    assert response.status_code == 200
    assert "created successfully" in response.json()["message"]


def test_developer_permission_denied():
    """Verify 'developer' role cannot manage users (Permission-level check)."""
    # 1. Create a dev user
    admin_token = get_admin_token()
    client.post(
        "/api/v1/users/add",
        json={"username": "dev1", "password": "password", "role": "developer"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # 2. Login as the newly created developer
    res = client.post(
        "/api/v1/users/login", json={"username": "dev1", "password": "password"}
    )
    dev_token = res.json()["access_token"]

    # 3. Attempt to add another user using developer token (Should fail 403)
    res = client.post(
        "/api/v1/users/add",
        json={"username": "hacker", "password": "123"},
        headers={"Authorization": f"Bearer {dev_token}"},
    )

    assert res.status_code == 403
    assert "Permission denied" in res.json()["detail"]


def test_add_user_unauthorized_missing_token():
    """Verify that endpoints fail without the Authorization header."""
    response = client.post(
        "/api/v1/users/add", json={"username": "fail", "password": "p"}
    )
    assert response.status_code == 401


# -------------------------------------------------------------------
# 3. User Deletion & Protection
# -------------------------------------------------------------------


def test_delete_user_as_admin():
    """Verify admin can delete a user."""
    token = get_admin_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Create a dummy user
    client.post(
        "/api/v1/users/add", json={"username": "bye", "password": "p"}, headers=headers
    )

    # Delete the user
    response = client.delete("/api/v1/users/bye", headers=headers)
    assert response.status_code == 200
    assert "deleted" in response.json()["message"]


def test_admin_cannot_delete_self():
    """Verify that the system prevents deleting the 'admin' account."""
    token = get_admin_token()
    headers = {"Authorization": f"Bearer {token}"}

    response = client.delete("/api/v1/users/admin", headers=headers)
    assert response.status_code == 400
    assert "Cannot delete root admin" in response.json()["detail"]
