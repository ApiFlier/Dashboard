import json
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


class OpsHandoffCreate(BaseModel):
    airport_ident: str
    shift_name: str
    outgoing_operator: Optional[str] = None
    incoming_operator: Optional[str] = None
    weather_summary: Optional[str] = None
    operations_summary: Optional[str] = None
    open_items: Optional[str] = None


class OpsInspectionCreate(BaseModel):
    airport_ident: str
    inspection_type: str
    completed_by: Optional[str] = None
    checklist_json: str
    notes: Optional[str] = None


_VALID_PRIORITIES = {"Low", "Medium", "High", "Critical"}
_VALID_STATUSES = {"Open", "In Progress", "Closed"}


class MaintenanceItemCreate(BaseModel):
    airport_ident: str
    title: str
    description: Optional[str] = None
    priority: str = "Medium"
    status: str = "Open"
    due_date: Optional[str] = None
    assigned_to: Optional[str] = None


class MaintenanceItemUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    due_date: Optional[str] = None
    assigned_to: Optional[str] = None


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
    stored_username = authenticate_user(req.username, req.password)
    if stored_username is None:
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    token = create_session(stored_username)
    return {"token": token, "username": stored_username}


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

    if authenticate_user(current_username, req.current_password) is None:
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


# --- Ops handoff endpoints ---

@router.get("/ops/handoffs")
async def get_ops_handoffs(
    airport_ident: Optional[str] = None,
    limit: int = 50,
    username: str = Depends(require_ops_auth),
):
    with get_connection() as conn:
        cursor = conn.cursor()
        if airport_ident:
            cursor.execute(
                "SELECT * FROM ops_handoffs WHERE airport_ident = ? ORDER BY created_at DESC LIMIT ?",
                (airport_ident.upper(), limit),
            )
        else:
            cursor.execute(
                "SELECT * FROM ops_handoffs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


@router.post("/ops/handoffs", status_code=201)
async def create_ops_handoff(
    entry: OpsHandoffCreate,
    username: str = Depends(require_ops_auth),
):
    if not entry.airport_ident.strip():
        raise HTTPException(status_code=400, detail="airport_ident cannot be empty.")
    if not entry.shift_name.strip():
        raise HTTPException(status_code=400, detail="shift_name cannot be empty.")
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO ops_handoffs
               (airport_ident, shift_name, outgoing_operator, incoming_operator,
                weather_summary, operations_summary, open_items, created_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.airport_ident.strip().upper(),
                entry.shift_name.strip(),
                entry.outgoing_operator.strip() if entry.outgoing_operator else None,
                entry.incoming_operator.strip() if entry.incoming_operator else None,
                entry.weather_summary.strip() if entry.weather_summary else None,
                entry.operations_summary.strip() if entry.operations_summary else None,
                entry.open_items.strip() if entry.open_items else None,
                username,
                now,
                now,
            ),
        )
        conn.commit()
        row_id = cursor.lastrowid
    return {"id": row_id, "status": "created"}


# --- Ops inspection endpoints ---

@router.get("/ops/inspections")
async def get_ops_inspections(
    airport_ident: Optional[str] = None,
    limit: int = 50,
    username: str = Depends(require_ops_auth),
):
    with get_connection() as conn:
        cursor = conn.cursor()
        if airport_ident:
            cursor.execute(
                "SELECT * FROM ops_inspections WHERE airport_ident = ? ORDER BY created_at DESC LIMIT ?",
                (airport_ident.upper(), limit),
            )
        else:
            cursor.execute(
                "SELECT * FROM ops_inspections ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


@router.post("/ops/inspections", status_code=201)
async def create_ops_inspection(
    entry: OpsInspectionCreate,
    username: str = Depends(require_ops_auth),
):
    if not entry.airport_ident.strip():
        raise HTTPException(status_code=400, detail="airport_ident cannot be empty.")
    if not entry.inspection_type.strip():
        raise HTTPException(status_code=400, detail="inspection_type cannot be empty.")
    try:
        json.loads(entry.checklist_json)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="checklist_json must be valid JSON.")
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO ops_inspections
               (airport_ident, inspection_type, completed_by, checklist_json,
                notes, created_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.airport_ident.strip().upper(),
                entry.inspection_type.strip(),
                entry.completed_by.strip() if entry.completed_by else None,
                entry.checklist_json,
                entry.notes.strip() if entry.notes else None,
                username,
                now,
                now,
            ),
        )
        conn.commit()
        row_id = cursor.lastrowid
    return {"id": row_id, "status": "created"}


# --- Ops maintenance endpoints ---

@router.get("/ops/maintenance")
async def get_ops_maintenance(
    airport_ident: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    username: str = Depends(require_ops_auth),
):
    with get_connection() as conn:
        cursor = conn.cursor()
        conditions = []
        params: List = []
        if airport_ident:
            conditions.append("airport_ident = ?")
            params.append(airport_ident.upper())
        if status:
            conditions.append("status = ?")
            params.append(status)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        # Open/In Progress first (Closed last), then due_date ASC (NULLs last), then newest first
        order = (
            "ORDER BY CASE status WHEN 'Closed' THEN 1 ELSE 0 END ASC, "
            "CASE WHEN due_date IS NULL OR due_date = '' THEN 1 ELSE 0 END ASC, "
            "due_date ASC, created_at DESC"
        )
        params.append(limit)
        cursor.execute(
            f"SELECT * FROM ops_maintenance_items {where} {order} LIMIT ?",
            params,
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


@router.post("/ops/maintenance", status_code=201)
async def create_ops_maintenance(
    entry: MaintenanceItemCreate,
    username: str = Depends(require_ops_auth),
):
    if not entry.airport_ident.strip():
        raise HTTPException(status_code=400, detail="airport_ident cannot be empty.")
    if not entry.title.strip():
        raise HTTPException(status_code=400, detail="title cannot be empty.")
    if entry.priority not in _VALID_PRIORITIES:
        raise HTTPException(status_code=400, detail=f"priority must be one of: {', '.join(sorted(_VALID_PRIORITIES))}")
    if entry.status not in _VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of: {', '.join(sorted(_VALID_STATUSES))}")
    now = datetime.now(timezone.utc).isoformat()
    closed_at = now if entry.status == "Closed" else None
    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO ops_maintenance_items
               (airport_ident, title, description, priority, status, due_date,
                assigned_to, created_by, created_at, updated_at, closed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.airport_ident.strip().upper(),
                entry.title.strip(),
                entry.description.strip() if entry.description else None,
                entry.priority,
                entry.status,
                entry.due_date.strip() if entry.due_date else None,
                entry.assigned_to.strip() if entry.assigned_to else None,
                username,
                now,
                now,
                closed_at,
            ),
        )
        conn.commit()
        row_id = cursor.lastrowid
    return {"id": row_id, "status": "created"}


@router.patch("/ops/maintenance/{item_id}")
async def update_ops_maintenance(
    item_id: int,
    update: MaintenanceItemUpdate,
    username: str = Depends(require_ops_auth),
):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ops_maintenance_items WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Maintenance item not found.")

        fields: dict = dict(row)
        if update.title is not None:
            if not update.title.strip():
                raise HTTPException(status_code=400, detail="title cannot be empty.")
            fields["title"] = update.title.strip()
        if update.description is not None:
            fields["description"] = update.description.strip() or None
        if update.priority is not None:
            if update.priority not in _VALID_PRIORITIES:
                raise HTTPException(status_code=400, detail=f"priority must be one of: {', '.join(sorted(_VALID_PRIORITIES))}")
            fields["priority"] = update.priority
        if update.status is not None:
            if update.status not in _VALID_STATUSES:
                raise HTTPException(status_code=400, detail=f"status must be one of: {', '.join(sorted(_VALID_STATUSES))}")
            prev_status = fields["status"]
            fields["status"] = update.status
            now_ts = datetime.now(timezone.utc).isoformat()
            if update.status == "Closed" and prev_status != "Closed":
                fields["closed_at"] = now_ts
            elif update.status != "Closed" and prev_status == "Closed":
                fields["closed_at"] = None
        if update.due_date is not None:
            fields["due_date"] = update.due_date.strip() or None
        if update.assigned_to is not None:
            fields["assigned_to"] = update.assigned_to.strip() or None

        now_ts = datetime.now(timezone.utc).isoformat()
        fields["updated_at"] = now_ts

        conn.execute(
            """UPDATE ops_maintenance_items
               SET title=?, description=?, priority=?, status=?, due_date=?,
                   assigned_to=?, updated_at=?, closed_at=?
               WHERE id=?""",
            (
                fields["title"],
                fields["description"],
                fields["priority"],
                fields["status"],
                fields["due_date"],
                fields["assigned_to"],
                fields["updated_at"],
                fields["closed_at"],
                item_id,
            ),
        )
        conn.commit()

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ops_maintenance_items WHERE id = ?", (item_id,))
        return dict(cursor.fetchone())
