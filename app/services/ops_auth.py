import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import bcrypt

from app.services.runtime_db import get_connection

logger = logging.getLogger(__name__)

SESSION_TTL_HOURS = 24


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def authenticate_user(username: str, password: str) -> Optional[str]:
    """Returns the stored username if credentials are valid (case-insensitive username match), else None."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT username, password_hash FROM admin_users WHERE LOWER(username) = LOWER(?)",
            (username,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        if not verify_password(password, row["password_hash"]):
            return None
        return row["username"]


def create_session(username: str) -> str:
    token = secrets.token_hex(32)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=SESSION_TTL_HOURS)
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO admin_sessions (token, username, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, username, now.isoformat(), expires.isoformat())
        )
        conn.commit()
    return token


def validate_session(token: str) -> Optional[str]:
    """Returns username if the session token is valid and not expired, else None."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT username FROM admin_sessions WHERE token = ? AND expires_at > ?",
            (token, now)
        )
        row = cursor.fetchone()
        return row["username"] if row else None


def change_password(username: str, new_password: str) -> bool:
    now = datetime.now(timezone.utc).isoformat()
    password_hash = hash_password(new_password)
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE admin_users SET password_hash = ?, updated_at = ? WHERE username = ?",
            (password_hash, now, username)
        )
        conn.commit()
        return cursor.rowcount > 0


def change_username(old_username: str, new_username: str) -> bool:
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        try:
            cursor = conn.execute(
                "UPDATE admin_users SET username = ?, updated_at = ? WHERE username = ?",
                (new_username, now, old_username)
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception:
            return False


def invalidate_sessions(username: str):
    with get_connection() as conn:
        conn.execute("DELETE FROM admin_sessions WHERE username = ?", (username,))
        conn.commit()


def bootstrap_default_admin():
    """Create the default meeks/meeks admin if no admin users exist yet.

    Also migrates the old Meeks/Meeks default account (if both username and
    password are still the original bootstrap values) to meeks/meeks.  Custom
    credentials — a changed password, a renamed username, or any user other
    than the exact old default — are never touched.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM admin_users")
        row = cursor.fetchone()

        if row["cnt"] == 0:
            # Fresh install — create the new default.
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "INSERT INTO admin_users (username, password_hash, created_at, updated_at) VALUES (?, ?, ?, ?)",
                ("meeks", hash_password("meeks"), now, now)
            )
            conn.commit()
            logger.info("Bootstrapped default Ops Mode admin: meeks")
            return

        # Existing DB — migrate the old Meeks/Meeks default if still unmodified.
        cursor.execute(
            "SELECT username, password_hash FROM admin_users WHERE username = 'Meeks'"
        )
        old_row = cursor.fetchone()
        if old_row and verify_password("Meeks", old_row["password_hash"]):
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "UPDATE admin_users SET username = 'meeks', password_hash = ?, updated_at = ? WHERE username = 'Meeks'",
                (hash_password("meeks"), now)
            )
            # Keep existing session tokens valid under the new username.
            conn.execute(
                "UPDATE admin_sessions SET username = 'meeks' WHERE username = 'Meeks'"
            )
            conn.commit()
            logger.info("Migrated default Ops Mode admin: Meeks/Meeks → meeks/meeks")
