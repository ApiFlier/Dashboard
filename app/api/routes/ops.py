import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

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


class SharedAlertCreate(BaseModel):
    airport_ident: str
    category: str
    affected_asset: Optional[str] = None
    severity: str
    visibility: str = "shared_airline_station"
    title: str
    message: str
    expires_at: str


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
_VALID_OPERATOR_MODES = {"airport", "airline"}
_VALID_ALERT_SEVERITIES = {"Watch", "Advisory", "Warning", "Critical"}
_VALID_ALERT_VISIBILITIES = {"shared_airline_station"}
SHARED_ALERTS_ADVISORY = (
    "Shared airport alerts are advisory coordination notes only. Verify through "
    "official airport, NOTAM, ATC, company, and regulatory channels before "
    "operational decisions. Not for dispatch, release, navigation, operational "
    "control, or tactical aircraft movement."
)


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
    """Returns the authenticated username. Accepts session Bearer token or X-Admin-Token.

    All /api/ops/* endpoints use this dependency because Ops records are private
    operational data created by the instance owner.  Unlike public weather/airport
    data, ops records must never be readable without authentication.
    """
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


def _get_ops_user_profile(username: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT username, operator_mode, airport_ident, organization_name,
                      display_name, is_active
               FROM admin_users
               WHERE username = ?""",
            (username,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


async def require_ops_identity(
    authorization: str = Header(None),
    x_admin_token: str = Header(None),
) -> Dict[str, Any]:
    """Return the authenticated Ops identity for role-scoped endpoints.

    The legacy X-Admin-Token fallback intentionally does not receive a synthetic
    airport/role identity because shared alerts enforce per-airport role scope.
    """
    if authorization and authorization.startswith("Bearer "):
        token = authorization[len("Bearer "):]
        username = validate_session(token)
        if username:
            profile = _get_ops_user_profile(username)
            if not profile:
                raise HTTPException(status_code=401, detail="Ops user profile was not found.")
            if not profile.get("is_active"):
                raise HTTPException(status_code=403, detail="Ops user is inactive.")
            operator_mode = profile.get("operator_mode") or "airport"
            if operator_mode not in _VALID_OPERATOR_MODES:
                raise HTTPException(status_code=403, detail="Ops user has an invalid operator mode.")
            profile["operator_mode"] = operator_mode
            profile["airport_ident"] = profile.get("airport_ident").upper() if profile.get("airport_ident") else None
            profile["is_active"] = bool(profile.get("is_active"))
            profile["auth_source"] = "session"
            return profile

    if x_admin_token and settings.ADMIN_API_TOKEN and x_admin_token == settings.ADMIN_API_TOKEN:
        raise HTTPException(
            status_code=403,
            detail="X-Admin-Token is not allowed for role-scoped Ops shared alert endpoints.",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Ops Mode requires authentication.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _require_assigned_airport(identity: Dict[str, Any]) -> str:
    airport_ident = identity.get("airport_ident")
    if not airport_ident:
        raise HTTPException(status_code=403, detail="Ops user is not assigned to an airport.")
    return airport_ident.upper()


def _parse_future_utc_timestamp(value: str) -> str:
    if not value or not value.strip():
        raise HTTPException(status_code=400, detail="expires_at is required.")
    raw = value.strip()
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        raise HTTPException(status_code=400, detail="expires_at must be a valid ISO 8601 UTC timestamp.")
    if parsed.tzinfo is None:
        raise HTTPException(status_code=400, detail="expires_at must include a UTC timezone offset.")
    expires_utc = parsed.astimezone(timezone.utc)
    if expires_utc <= datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="expires_at must be in the future.")
    return expires_utc.isoformat()


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


# --- Ops identity and shared airport alerts ---

@router.get("/ops/me")
async def ops_me(identity: Dict[str, Any] = Depends(require_ops_identity)):
    return {
        "username": identity["username"],
        "operator_mode": identity["operator_mode"],
        "airport_ident": identity.get("airport_ident"),
        "organization_name": identity.get("organization_name"),
        "display_name": identity.get("display_name"),
        "is_active": identity["is_active"],
    }


def _shared_alert_response(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        **row,
        "acknowledged": bool(row.get("acknowledged_at")),
    }


@router.get("/ops/shared-alerts")
async def get_ops_shared_alerts(
    airport_ident: Optional[str] = None,
    active_only: bool = True,
    identity: Dict[str, Any] = Depends(require_ops_identity),
):
    assigned_airport = _require_assigned_airport(identity)
    requested_airport = airport_ident.strip().upper() if airport_ident else assigned_airport
    if requested_airport != assigned_airport:
        raise HTTPException(status_code=403, detail="Ops user can only list shared alerts for their assigned airport.")

    conditions = ["a.airport_ident = ?"]
    params: List[Any] = [requested_airport]
    if active_only:
        conditions.append("a.cancelled_at IS NULL")
        conditions.append("a.expires_at > ?")
        params.append(datetime.now(timezone.utc).isoformat())

    params.append(identity["username"])
    where = " AND ".join(conditions)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""SELECT a.*, ack.acknowledged_at
                FROM ops_shared_alerts a
                LEFT JOIN ops_shared_alert_acknowledgements ack
                  ON ack.alert_id = a.id AND ack.username = ?
                WHERE {where}
                ORDER BY a.expires_at ASC, a.created_at DESC""",
            [params[-1], *params[:-1]],
        )
        alerts = [_shared_alert_response(dict(row)) for row in cursor.fetchall()]

    return {
        "metadata": {
            "advisory": SHARED_ALERTS_ADVISORY,
            "active_only": active_only,
            "airport_ident": requested_airport,
        },
        "alerts": alerts,
    }


@router.post("/ops/shared-alerts", status_code=201)
async def create_ops_shared_alert(
    alert: SharedAlertCreate,
    identity: Dict[str, Any] = Depends(require_ops_identity),
):
    if identity["operator_mode"] != "airport":
        raise HTTPException(status_code=403, detail="Only airport operators can create shared airport alerts.")

    assigned_airport = _require_assigned_airport(identity)
    airport_ident = alert.airport_ident.strip().upper() if alert.airport_ident else ""
    if airport_ident != assigned_airport:
        raise HTTPException(status_code=403, detail="Airport operators can only create alerts for their assigned airport.")
    if not alert.category.strip():
        raise HTTPException(status_code=400, detail="category cannot be empty.")
    if alert.severity not in _VALID_ALERT_SEVERITIES:
        raise HTTPException(status_code=400, detail=f"severity must be one of: {', '.join(sorted(_VALID_ALERT_SEVERITIES))}")
    if alert.visibility not in _VALID_ALERT_VISIBILITIES:
        raise HTTPException(status_code=400, detail="visibility must be shared_airline_station.")
    if not alert.title.strip():
        raise HTTPException(status_code=400, detail="title cannot be empty.")
    if not alert.message.strip():
        raise HTTPException(status_code=400, detail="message cannot be empty.")

    expires_at = _parse_future_utc_timestamp(alert.expires_at)
    now = datetime.now(timezone.utc).isoformat()
    source_label = identity.get("organization_name") or "Airport Ops"

    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO ops_shared_alerts
               (airport_ident, category, affected_asset, severity, visibility,
                title, message, source_label, created_by, created_at, updated_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                airport_ident,
                alert.category.strip(),
                alert.affected_asset.strip() if alert.affected_asset else None,
                alert.severity,
                alert.visibility,
                alert.title.strip(),
                alert.message.strip(),
                source_label.strip() or "Airport Ops",
                identity["username"],
                now,
                now,
                expires_at,
            ),
        )
        conn.commit()
        row_id = cursor.lastrowid

    return {"id": row_id, "status": "created", "advisory": SHARED_ALERTS_ADVISORY}


@router.post("/ops/shared-alerts/{alert_id}/ack")
async def acknowledge_ops_shared_alert(
    alert_id: int,
    identity: Dict[str, Any] = Depends(require_ops_identity),
):
    assigned_airport = _require_assigned_airport(identity)
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ops_shared_alerts WHERE id = ?", (alert_id,))
        alert = cursor.fetchone()
        if not alert:
            raise HTTPException(status_code=404, detail="Shared airport alert not found.")
        if alert["airport_ident"] != assigned_airport:
            raise HTTPException(status_code=403, detail="Ops user cannot acknowledge alerts for another airport.")

        conn.execute(
            """INSERT OR IGNORE INTO ops_shared_alert_acknowledgements
               (alert_id, username, acknowledged_at) VALUES (?, ?, ?)""",
            (alert_id, identity["username"], now),
        )
        conn.commit()

        cursor.execute(
            """SELECT acknowledged_at FROM ops_shared_alert_acknowledgements
               WHERE alert_id = ? AND username = ?""",
            (alert_id, identity["username"]),
        )
        ack_row = cursor.fetchone()

    return {
        "status": "acknowledged",
        "alert_id": alert_id,
        "username": identity["username"],
        "acknowledged_at": ack_row["acknowledged_at"],
    }


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


# --- Ops overview endpoint ---

@router.get("/ops/overview")
async def get_ops_overview(
    airport_ident: Optional[str] = None,
    username: str = Depends(require_ops_auth),
):
    # Use UTC consistently — created_at values are stored as UTC ISO strings.
    today_str = datetime.now(timezone.utc).date().isoformat()
    ap = airport_ident.upper() if airport_ident else None
    ap_params = [ap] if ap else []
    ap_where = "WHERE airport_ident = ?" if ap else ""

    with get_connection() as conn:
        cursor = conn.cursor()

        # Nested helpers close over `cursor` and `ap` to avoid repeating the
        # airport-filter branch in every COUNT query.
        def _count_today(table: str) -> int:
            if ap:
                cursor.execute(
                    f"SELECT COUNT(*) as cnt FROM {table} WHERE airport_ident = ? AND created_at LIKE ?",
                    [ap, f"{today_str}%"],
                )
            else:
                cursor.execute(
                    f"SELECT COUNT(*) as cnt FROM {table} WHERE created_at LIKE ?",
                    [f"{today_str}%"],
                )
            return cursor.fetchone()["cnt"]

        def _count_maint_status(status_val: str) -> int:
            if ap:
                cursor.execute(
                    "SELECT COUNT(*) as cnt FROM ops_maintenance_items WHERE airport_ident = ? AND status = ?",
                    [ap, status_val],
                )
            else:
                cursor.execute(
                    "SELECT COUNT(*) as cnt FROM ops_maintenance_items WHERE status = ?", [status_val]
                )
            return cursor.fetchone()["cnt"]

        def _count_overdue() -> int:
            if ap:
                cursor.execute(
                    "SELECT COUNT(*) as cnt FROM ops_maintenance_items"
                    " WHERE airport_ident = ? AND status != 'Closed'"
                    " AND due_date IS NOT NULL AND due_date != '' AND due_date < ?",
                    [ap, today_str],
                )
            else:
                cursor.execute(
                    "SELECT COUNT(*) as cnt FROM ops_maintenance_items"
                    " WHERE status != 'Closed' AND due_date IS NOT NULL AND due_date != '' AND due_date < ?",
                    [today_str],
                )
            return cursor.fetchone()["cnt"]

        log_today = _count_today("ops_log_entries")
        handoff_today = _count_today("ops_handoffs")
        inspection_today = _count_today("ops_inspections")
        open_maint = _count_maint_status("Open")
        in_progress_maint = _count_maint_status("In Progress")
        overdue_maint = _count_overdue()

        # Latest handoff and inspection
        cursor.execute(f"SELECT * FROM ops_handoffs {ap_where} ORDER BY created_at DESC LIMIT 1", ap_params)
        row = cursor.fetchone()
        latest_handoff = dict(row) if row else None

        cursor.execute(f"SELECT * FROM ops_inspections {ap_where} ORDER BY created_at DESC LIMIT 1", ap_params)
        row = cursor.fetchone()
        latest_inspection = dict(row) if row else None

        # Needs attention: overdue maintenance + recent warning/critical log entries
        if ap:
            cursor.execute(
                "SELECT * FROM ops_maintenance_items"
                " WHERE airport_ident = ? AND status != 'Closed'"
                " AND due_date IS NOT NULL AND due_date != '' AND due_date < ?"
                " ORDER BY due_date ASC LIMIT 10",
                [ap, today_str],
            )
        else:
            cursor.execute(
                "SELECT * FROM ops_maintenance_items"
                " WHERE status != 'Closed' AND due_date IS NOT NULL AND due_date != '' AND due_date < ?"
                " ORDER BY due_date ASC LIMIT 10",
                [today_str],
            )
        overdue_rows = cursor.fetchall()

        if ap:
            cursor.execute(
                "SELECT * FROM ops_log_entries WHERE airport_ident = ? AND severity IN ('Warning', 'Critical')"
                " ORDER BY created_at DESC LIMIT 5",
                [ap],
            )
        else:
            cursor.execute(
                "SELECT * FROM ops_log_entries WHERE severity IN ('Warning', 'Critical')"
                " ORDER BY created_at DESC LIMIT 5"
            )
        alert_log_rows = cursor.fetchall()

        needs_attention: List[dict] = []
        for row in overdue_rows:
            d = dict(row)
            needs_attention.append({
                "type": "maintenance",
                "id": d["id"],
                "airport_ident": d["airport_ident"],
                "summary": d["title"],
                "priority": d["priority"],
                "due_date": d["due_date"],
                "status": d["status"],
                "reason": "overdue",
            })
        for row in alert_log_rows:
            d = dict(row)
            needs_attention.append({
                "type": "log",
                "id": d["id"],
                "airport_ident": d["airport_ident"],
                "summary": f"{d['category']}: {d['entry_text'][:80]}",
                "severity": d["severity"],
                "created_at": d["created_at"],
                "reason": "severity",
            })
        needs_attention = needs_attention[:10]

        # Recent activity: latest 5 from each table, merged and sorted
        recent: List[dict] = []

        cursor.execute(f"SELECT * FROM ops_log_entries {ap_where} ORDER BY created_at DESC LIMIT 5", ap_params)
        for row in cursor.fetchall():
            d = dict(row)
            recent.append({
                "type": "log",
                "id": d["id"],
                "airport_ident": d["airport_ident"],
                "summary": f"{d['category']}: {d['entry_text'][:80]}",
                "created_at": d["created_at"],
                "meta": {"severity": d["severity"]},
            })

        cursor.execute(f"SELECT * FROM ops_handoffs {ap_where} ORDER BY created_at DESC LIMIT 5", ap_params)
        for row in cursor.fetchall():
            d = dict(row)
            recent.append({
                "type": "handoff",
                "id": d["id"],
                "airport_ident": d["airport_ident"],
                "summary": d["shift_name"],
                "created_at": d["created_at"],
                "meta": {},
            })

        cursor.execute(f"SELECT * FROM ops_inspections {ap_where} ORDER BY created_at DESC LIMIT 5", ap_params)
        for row in cursor.fetchall():
            d = dict(row)
            recent.append({
                "type": "inspection",
                "id": d["id"],
                "airport_ident": d["airport_ident"],
                "summary": d["inspection_type"],
                "created_at": d["created_at"],
                "meta": {},
            })

        cursor.execute(f"SELECT * FROM ops_maintenance_items {ap_where} ORDER BY created_at DESC LIMIT 5", ap_params)
        for row in cursor.fetchall():
            d = dict(row)
            recent.append({
                "type": "maintenance",
                "id": d["id"],
                "airport_ident": d["airport_ident"],
                "summary": d["title"],
                "created_at": d["created_at"],
                "meta": {"status": d["status"], "priority": d["priority"]},
            })

        recent.sort(key=lambda x: x["created_at"], reverse=True)
        recent_activity = recent[:10]

    return {
        "today": {
            "ops_log_count": log_today,
            "handoff_count": handoff_today,
            "inspection_count": inspection_today,
            "open_maintenance_count": open_maint,
            "in_progress_maintenance_count": in_progress_maint,
            "overdue_maintenance_count": overdue_maint,
        },
        "latest": {
            "handoff": latest_handoff,
            "inspection": latest_inspection,
        },
        "needs_attention": needs_attention,
        "recent_activity": recent_activity,
    }


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
