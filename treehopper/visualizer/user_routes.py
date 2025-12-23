from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
import bcrypt
import re
from datetime import datetime, timedelta
from jose import JWTError, jwt
from treehopper.visualizer.db_util import db
from treehopper.th_config import DEFAULT_API_KEY, ACCESS_TOKEN_EXPIRE_MINUTES

# Configuration
SECRET_KEY = DEFAULT_API_KEY
ALGORITHM = "HS256"

router = APIRouter(prefix="/api/v1/users", tags=["Users"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/users/login")


# Pydantic Models
class UserLogin(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "developer"  # Can be "admin" or "developer"


class UserUpdate(BaseModel):
    role: str
    password: str


class PasswordChange(BaseModel):
    username: str
    new_password: str


class PasswordReset(BaseModel):
    username: str
    new_password: str


class ValidateReset(BaseModel):
    username: str


# --- Password Validation ---
def validate_password_strength(password: str) -> tuple[bool, list[str]]:
    """
    Validate password meets requirements:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one number
    - At least one special character (@$!%*?&)
    """
    errors = []

    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")

    if not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter")

    if not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter")

    if not re.search(r"[0-9]", password):
        errors.append("Password must contain at least one number")

    if not re.search(r"[@$!%*?&]", password):
        errors.append("Password must contain at least one special character (@$!%*?&)")

    return (len(errors) == 0, errors)


# --- JWT Helpers ---
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception

        query = """
            SELECT u.username, r.name as role
            FROM users u
            JOIN roles r ON u.role_id = r.id
            WHERE u.username = ?
        """
        user = db.fetch_one(query, (username,))
        if user is None:
            raise credentials_exception
        return user
    except JWTError:
        raise credentials_exception


def check_permission(required_perm: str):
    """Dependency factory to check for specific permissions."""

    async def _check(current_user=Depends(get_current_user)):
        query = """
            SELECT p.name FROM permissions p
            JOIN role_permissions rp ON p.id = rp.permission_id
            JOIN roles r ON rp.role_id = r.id
            WHERE r.name = ? AND p.name = ?
        """
        perm = db.fetch_one(query, (current_user["role"], required_perm))
        if not perm:
            raise HTTPException(status_code=403, detail="Permission denied")
        return current_user

    return _check


# --- Routes ---


@router.post("/login")
async def login(user: UserLogin):
    """Login and get JWT token. Returns needs_password_change flag."""
    query = """
        SELECT u.*, r.name as role_name
        FROM users u
        JOIN roles r ON u.role_id = r.id
        WHERE u.username = ?
    """
    record = db.fetch_one(query, (user.username,))

    if not record or not bcrypt.checkpw(
        user.password.encode("utf-8"), record["password_hash"].encode("utf-8")
    ):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(
        data={"sub": record["username"], "role": record["role_name"]}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": record["role_name"],
        "needs_password_change": bool(record["needs_password_change"]),
    }


@router.post("/change-password")
async def change_password(data: PasswordChange):
    """
    Change password for first-time login.
    User must have needs_password_change=1.
    Sets needs_password_change=0 after successful change.
    """
    # Validate user exists
    user_query = (
        "SELECT * FROM users u JOIN roles r ON u.role_id = r.id WHERE u.username = ?"
    )
    user = db.fetch_one(user_query, (data.username,))

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate password strength
    is_valid, errors = validate_password_strength(data.new_password)
    if not is_valid:
        raise HTTPException(status_code=400, detail="; ".join(errors))

    # Hash new password
    pwd_hash = bcrypt.hashpw(
        data.new_password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")

    # Update password and set needs_password_change to 0
    db.execute(
        "UPDATE users SET password_hash = ?, needs_password_change = 0 WHERE username = ?",
        (pwd_hash, data.username),
    )

    # Generate new JWT token
    access_token = create_access_token(
        data={"sub": data.username, "role": user["name"]}  # role name from JOIN
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user["name"],
        "message": "Password changed successfully",
    }


@router.post("/validate-reset")
async def validate_reset(data: ValidateReset):
    """
    Validate user for password reset.
    Only allows users who have logged in at least once (needs_password_change=0).
    """
    query = "SELECT needs_password_change FROM users WHERE username = ?"
    user = db.fetch_one(query, (data.username,))

    if not user:
        raise HTTPException(status_code=404, detail="Username not found")

    # Check if user has completed first login
    if user["needs_password_change"] == 1:
        raise HTTPException(
            status_code=403,
            detail="Password reset not available. Please contact administrator for first-time login.",
        )

    return {"message": "User validated for password reset"}


@router.post("/reset-password")
async def reset_password(data: PasswordReset):
    """
    Reset password for users who forgot their password.
    User must have needs_password_change=0 (must have logged in at least once).
    """
    # Validate user exists and has completed first login
    query = "SELECT needs_password_change FROM users WHERE username = ?"
    user = db.fetch_one(query, (data.username,))

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user["needs_password_change"] == 1:
        raise HTTPException(
            status_code=403, detail="Password reset not available for first-time users"
        )

    # Validate password strength
    is_valid, errors = validate_password_strength(data.new_password)
    if not is_valid:
        raise HTTPException(status_code=400, detail="; ".join(errors))

    # Hash new password
    pwd_hash = bcrypt.hashpw(
        data.new_password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")

    # Update password
    db.execute(
        "UPDATE users SET password_hash = ? WHERE username = ?",
        (pwd_hash, data.username),
    )

    return {"message": "Password reset successfully"}


@router.get("/list")
async def list_users(_=Depends(check_permission("manage_users"))):
    """List all users (admin only)"""
    query = """
        SELECT u.username, r.name as role, u.created_at
        FROM users u
        JOIN roles r ON u.role_id = r.id
        ORDER BY u.created_at DESC
    """
    users = db.fetch_all(query)
    return [dict(user) for user in users]


@router.post("/add")
async def add_user(user: UserCreate, _=Depends(check_permission("manage_users"))):
    """
    Add new user (admin only).
    Sets needs_password_change=1 to force password change on first login.
    Role can be "admin" or "developer".
    """
    # Validate password strength
    is_valid, errors = validate_password_strength(user.password)
    if not is_valid:
        raise HTTPException(status_code=400, detail="; ".join(errors))

    # Validate role
    if user.role not in ["admin", "developer"]:
        raise HTTPException(
            status_code=400, detail="Role must be 'admin' or 'developer'"
        )

    # Map the string role to an ID
    role_rec = db.fetch_one("SELECT id FROM roles WHERE name = ?", (user.role,))
    if not role_rec:
        raise HTTPException(status_code=400, detail="Invalid role provided")

    if db.fetch_one("SELECT id FROM users WHERE username = ?", (user.username,)):
        raise HTTPException(status_code=400, detail="Username already exists")

    pwd_hash = bcrypt.hashpw(user.password.encode("utf-8"), bcrypt.gensalt()).decode(
        "utf-8"
    )

    # Insert with needs_password_change=1
    db.execute(
        "INSERT INTO users (username, password_hash, role_id, needs_password_change) VALUES (?, ?, ?, 1)",
        (user.username, pwd_hash, role_rec["id"]),
    )
    return {
        "message": f"User {user.username} created successfully. \
            User will be prompted to change password on first login."
    }


@router.put("/{username}")
async def update_user(
    username: str, updates: UserUpdate, _=Depends(check_permission("manage_users"))
):
    """
    Update user (admin only).
    Can update role and/or password.
    If password is updated, sets needs_password_change=1.
    """
    if username == "admin" and updates.role and updates.role != "admin":
        raise HTTPException(status_code=400, detail="Cannot change admin user's role")

    # Check user exists
    user = db.fetch_one("SELECT id FROM users WHERE username = ?", (username,))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_fields = []
    params = []

    # Update role if provided
    if updates.role:
        if updates.role not in ["admin", "developer"]:
            raise HTTPException(
                status_code=400, detail="Role must be 'admin' or 'developer'"
            )

        role_rec = db.fetch_one("SELECT id FROM roles WHERE name = ?", (updates.role,))
        if not role_rec:
            raise HTTPException(status_code=400, detail="Invalid role")

        update_fields.append("role_id = ?")
        params.append(role_rec["id"])

    # Update password if provided
    if updates.password:
        is_valid, errors = validate_password_strength(updates.password)
        if not is_valid:
            raise HTTPException(status_code=400, detail="; ".join(errors))

        pwd_hash = bcrypt.hashpw(
            updates.password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        update_fields.append("password_hash = ?")
        update_fields.append("needs_password_change = 1")  # Force password change
        params.append(pwd_hash)

    if not update_fields:
        raise HTTPException(status_code=400, detail="No updates provided")

    # Build and execute update query
    params.append(username)
    query = f"UPDATE users SET {', '.join(update_fields)} WHERE username = ?"
    db.execute(query, tuple(params))

    return {"message": f"User {username} updated successfully"}


@router.delete("/{username}")
async def delete_user(username: str, _=Depends(check_permission("manage_users"))):
    """Delete user (admin only)"""
    if username == "admin":
        raise HTTPException(status_code=400, detail="Cannot delete root admin")

    db.execute("DELETE FROM users WHERE username = ?", (username,))
    return {"message": f"User {username} deleted"}
