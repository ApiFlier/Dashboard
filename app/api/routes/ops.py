import logging
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Header, Depends, status
from pydantic import BaseModel

from app.services.runtime_db import get_connection
from app.services.ops_auth import (
    authenticate_user, create_session, validate_session,
    change_password, change_username, invalidate_sessions
)
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


# --- Models ---

class LoginRequest(BaseModel):
    username: str
    password: str


class ChangeCredentialsRequest(BaseModel):
    current_password: str
    new_username: Optional[str] = None
    new_password: Optional[str] = None


class OpsLogEntryCreate(BaseModel):
    airport_ident: str
    category: str = "General"
    severity: str = "Info"
    entry_text: str
    created_by: str
    source_context_json: Optional[str] = None


# --- Auth dependency ---

async def require_ops_auth(
    authorization: str = Header(None),
    x_admin_token: str = Header(None),
) -> str:
    """Returns the authenticated username. Accepts session Bearer token or X-Admin-Token."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization[len("Bearer "):]
        username = validate_session(token)
        if username:
            return username

    if x_admin_token and settings.ADMIN_API_TOKEN and x_admin_token == settings.ADMIN_API_TOKEN:
        return "admin-token"

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Ops Mode requires authentication.",
        headers={"WWW-Authenticate": "Bearer"},
    )


# --- Auth endpoints ---

@router.post("/ops/auth/login")
async def ops_login(req: LoginRequest):
    if not req.username or not req.password:
        raise HTTPException(status_code=400, detail="Username and password are required.")
    if not authenticate_user(req.username, req.password):
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    token = create_session(req.username)
    return {"token": token, "username": req.username}


@router.post("/ops/auth/change-credentials")
async def ops_change_credentials(
    req: ChangeCredentialsRequest,
    authorization: str = Header(None),
):
    """Change username and/or password. Requires an active session token (not X-Admin-Token)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="An active session token is required to change credentials.")
    token = authorization[len("Bearer "):]
    current_username = validate_session(token)
    if not current_username:
        raise HTTPException(status_code=401, detail="Invalid or expired session.")

    if not authenticate_user(current_username, req.current_password):
        raise HTTPException(status_code=403, detail="Current password is incorrect.")

    if req.new_password:
        change_password(current_username, req.new_password)

    if req.new_username and req.new_username.strip() and req.new_username != current_username:
        success = change_username(current_username, req.new_username.strip())
        if not success:
            raise HTTPException(status_code=400, detail="Username change failed. Name may already be taken.")
        # Invalidate old sessions (stored under current_username) then create a fresh one
        invalidate_sessions(current_username)
        new_token = create_session(req.new_username.strip())
        return {"status": "ok", "token": new_token, "username": req.new_username.strip()}

    return {"status": "ok"}


# --- Ops status ---

@router.get("/ops/status")
async def ops_status(username: str = Depends(require_ops_auth)):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM ops_log_entries")
        row = cursor.fetchone()
        return {"status": "ok", "ops_mode": "v1", "log_entry_count": row["cnt"], "authenticated_as": username}


# --- Ops log endpoints ---

@router.get("/ops/logs")
async def get_ops_logs(
    airport_ident: Optional[str] = None,
    limit: int = 50,
    username: str = Depends(require_ops_auth),
):
    with get_connection() as conn:
        cursor = conn.cursor()
        if airport_ident:
            cursor.execute(
                "SELECT * FROM ops_log_entries WHERE airport_ident = ? ORDER BY created_at DESC LIMIT ?",
                (airport_ident.upper(), limit),
            )
        else:
            cursor.execute(
                "SELECT * FROM ops_log_entries ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


@router.post("/ops/logs", status_code=201)
async def create_ops_log_entry(
    entry: OpsLogEntryCreate,
    username: str = Depends(require_ops_auth),
):
    if not entry.entry_text.strip():
        raise HTTPException(status_code=400, detail="entry_text cannot be empty.")
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO ops_log_entries
               (airport_ident, category, severity, entry_text, created_by, source_context_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.airport_ident.upper(),
                entry.category,
                entry.severity,
                entry.entry_text.strip(),
                entry.created_by.strip() or username,
                entry.source_context_json,
                now,
                now,
            ),
        )
        conn.commit()
        row_id = cursor.lastrowid
    return {"id": row_id, "status": "created"}
