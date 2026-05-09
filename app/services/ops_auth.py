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


def authenticate_user(username: str, password: str) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT password_hash FROM admin_users WHERE username = ?",
            (username,)
        )
        row = cursor.fetchone()
        if not row:
            return False
        return verify_password(password, row["password_hash"])


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
    """Create the default Meeks/Meeks admin if no admin users exist yet."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM admin_users")
        row = cursor.fetchone()
        if row["cnt"] == 0:
            now = datetime.now(timezone.utc).isoformat()
            password_hash = hash_password("Meeks")
            conn.execute(
                "INSERT INTO admin_users (username, password_hash, created_at, updated_at) VALUES (?, ?, ?, ?)",
                ("Meeks", password_hash, now, now)
            )
            conn.commit()
            logger.info("Bootstrapped default Ops Mode admin: Meeks")
