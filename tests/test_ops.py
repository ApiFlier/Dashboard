"""
Tests for Ops Mode v1: schema, auth, and ops log endpoints.
"""
import tempfile
import pytest
from pathlib import Path
from unittest import mock
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixture: isolated temp DB with full schema + bootstrapped admin
# ---------------------------------------------------------------------------

@pytest.fixture
def ops_client():
    """Provides a TestClient backed by a fresh temp DB with the admin bootstrapped."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = str(Path(temp_dir) / "test_ops.sqlite")
        with mock.patch("app.core.config.settings.STATE_DIR", temp_dir):
            with mock.patch("app.core.config.settings.DB_PATH", db_path):
                with mock.patch("app.core.config.settings.PUBLIC_READONLY_MODE", False):
                    from app.main import app
                    with TestClient(app) as client:
                        yield client


@pytest.fixture
def ops_token(ops_client):
    """Returns a valid session token for the default meeks admin."""
    res = ops_client.post("/api/ops/auth/login", json={"username": "meeks", "password": "meeks"})
    assert res.status_code == 200, f"Login failed: {res.json()}"
    return res.json()["token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Schema: ops tables exist after migration
# ---------------------------------------------------------------------------

def test_ops_tables_exist(ops_client):
    import sqlite3
    from app.core.config import settings as cfg
    conn = sqlite3.connect(cfg.DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in cursor.fetchall()}
    conn.close()
    assert "ops_log_entries" in tables
    assert "admin_users" in tables
    assert "admin_sessions" in tables


def test_default_admin_bootstrapped(ops_client):
    """Default meeks/meeks admin must exist after startup."""
    import sqlite3
    from app.core.config import settings as cfg
    conn = sqlite3.connect(cfg.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM admin_users")
    rows = cursor.fetchall()
    conn.close()
    usernames = [r["username"] for r in rows]
    assert "meeks" in usernames


# ---------------------------------------------------------------------------
# Auth: login
# ---------------------------------------------------------------------------

def test_login_valid_credentials(ops_client):
    res = ops_client.post("/api/ops/auth/login", json={"username": "meeks", "password": "meeks"})
    assert res.status_code == 200
    data = res.json()
    assert "token" in data
    assert data["username"] == "meeks"


def test_login_case_insensitive_username(ops_client):
    """Username lookup is case-insensitive: MEEKS and Meeks both resolve to stored 'meeks'."""
    for variant in ("MEEKS", "Meeks", "MeEkS"):
        res = ops_client.post("/api/ops/auth/login", json={"username": variant, "password": "meeks"})
        assert res.status_code == 200, f"Login failed for username variant '{variant}': {res.json()}"
        assert res.json()["username"] == "meeks"


def test_login_invalid_password(ops_client):
    res = ops_client.post("/api/ops/auth/login", json={"username": "meeks", "password": "wrong"})
    assert res.status_code == 401


def test_login_password_is_case_sensitive(ops_client):
    """Password must match exactly — 'Meeks' is not the same as 'meeks'."""
    res = ops_client.post("/api/ops/auth/login", json={"username": "meeks", "password": "Meeks"})
    assert res.status_code == 401


def test_login_unknown_user(ops_client):
    res = ops_client.post("/api/ops/auth/login", json={"username": "nobody", "password": "x"})
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# Ops status: requires auth
# ---------------------------------------------------------------------------

def test_ops_status_unauthenticated(ops_client):
    res = ops_client.get("/api/ops/status")
    assert res.status_code == 401


def test_ops_status_authenticated(ops_client, ops_token):
    res = ops_client.get("/api/ops/status", headers=auth_headers(ops_token))
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["ops_mode"] == "v1"


# ---------------------------------------------------------------------------
# GET /api/ops/logs: requires auth
# ---------------------------------------------------------------------------

def test_get_logs_unauthenticated(ops_client):
    res = ops_client.get("/api/ops/logs")
    assert res.status_code == 401


def test_get_logs_invalid_token(ops_client):
    res = ops_client.get("/api/ops/logs", headers={"Authorization": "Bearer notreal"})
    assert res.status_code == 401


def test_get_logs_authenticated_empty(ops_client, ops_token):
    res = ops_client.get("/api/ops/logs", headers=auth_headers(ops_token))
    assert res.status_code == 200
    assert res.json() == []


# ---------------------------------------------------------------------------
# POST /api/ops/logs: requires auth
# ---------------------------------------------------------------------------

def test_create_log_unauthenticated(ops_client):
    res = ops_client.post("/api/ops/logs", json={
        "airport_ident": "KAGC",
        "category": "General",
        "severity": "Info",
        "entry_text": "Test entry",
        "created_by": "Tester"
    })
    assert res.status_code == 401


def test_create_log_no_token(ops_client):
    res = ops_client.post("/api/ops/logs", json={
        "airport_ident": "KAGC",
        "entry_text": "No token",
        "created_by": "x"
    })
    assert res.status_code == 401


def test_create_log_authenticated(ops_client, ops_token):
    res = ops_client.post(
        "/api/ops/logs",
        json={
            "airport_ident": "kagc",
            "category": "Weather",
            "severity": "Advisory",
            "entry_text": "Ceiling lowering, MVFR conditions.",
            "created_by": "Meeks"
        },
        headers=auth_headers(ops_token)
    )
    assert res.status_code == 201
    data = res.json()
    assert "id" in data
    assert data["status"] == "created"


# ---------------------------------------------------------------------------
# Round-trip: create then list
# ---------------------------------------------------------------------------

def test_create_then_list(ops_client, ops_token):
    headers = auth_headers(ops_token)

    ops_client.post("/api/ops/logs", json={
        "airport_ident": "KPIT",
        "category": "Runway",
        "severity": "Warning",
        "entry_text": "RWY 28C FOD reported.",
        "created_by": "Meeks"
    }, headers=headers)

    ops_client.post("/api/ops/logs", json={
        "airport_ident": "KAGC",
        "category": "General",
        "severity": "Info",
        "entry_text": "Morning ops check complete.",
        "created_by": "Meeks"
    }, headers=headers)

    # List all
    res = ops_client.get("/api/ops/logs", headers=headers)
    assert res.status_code == 200
    entries = res.json()
    assert len(entries) == 2

    idents = {e["airport_ident"] for e in entries}
    assert "KPIT" in idents
    assert "KAGC" in idents


def test_filter_by_airport(ops_client, ops_token):
    headers = auth_headers(ops_token)

    ops_client.post("/api/ops/logs", json={
        "airport_ident": "KAVP", "category": "Security",
        "severity": "Warning", "entry_text": "Gate breach.", "created_by": "Meeks"
    }, headers=headers)
    ops_client.post("/api/ops/logs", json={
        "airport_ident": "KAGC", "category": "General",
        "severity": "Info", "entry_text": "Quiet shift.", "created_by": "Meeks"
    }, headers=headers)

    res = ops_client.get("/api/ops/logs?airport_ident=KAVP", headers=headers)
    assert res.status_code == 200
    entries = res.json()
    assert all(e["airport_ident"] == "KAVP" for e in entries)
    assert len(entries) == 1


def test_airport_ident_uppercased(ops_client, ops_token):
    """lowercase airport_ident in POST should be stored as uppercase."""
    headers = auth_headers(ops_token)
    ops_client.post("/api/ops/logs", json={
        "airport_ident": "kphl", "entry_text": "Test.", "created_by": "x"
    }, headers=headers)
    res = ops_client.get("/api/ops/logs", headers=headers)
    assert res.json()[0]["airport_ident"] == "KPHL"


# ---------------------------------------------------------------------------
# X-Admin-Token fallback auth
# ---------------------------------------------------------------------------

def test_x_admin_token_auth(ops_client, ops_token):
    """A valid X-Admin-Token should also grant ops access."""
    with mock.patch("app.core.config.settings.ADMIN_API_TOKEN", "super-secret-token"):
        res = ops_client.get("/api/ops/status", headers={"X-Admin-Token": "super-secret-token"})
        assert res.status_code == 200


def test_x_admin_token_wrong_value(ops_client):
    with mock.patch("app.core.config.settings.ADMIN_API_TOKEN", "super-secret-token"):
        res = ops_client.get("/api/ops/status", headers={"X-Admin-Token": "wrong"})
        assert res.status_code == 401


# ---------------------------------------------------------------------------
# Credential change: session invalidation on rename
# ---------------------------------------------------------------------------

def test_old_session_invalidated_after_username_change(ops_client, ops_token):
    """After a username rename the original session token must no longer grant access."""
    old_headers = auth_headers(ops_token)

    # Confirm old token works now
    res = ops_client.get("/api/ops/status", headers=old_headers)
    assert res.status_code == 200

    # Rename the user (requires active session + current password)
    res = ops_client.post(
        "/api/ops/auth/change-credentials",
        json={"current_password": "meeks", "new_username": "MeeksRenamed"},
        headers=old_headers,
    )
    assert res.status_code == 200
    new_token = res.json().get("token")
    assert new_token, "Expected a fresh token after rename"

    # Old token must now be rejected
    res = ops_client.get("/api/ops/status", headers=old_headers)
    assert res.status_code == 401

    # New token must work
    res = ops_client.get("/api/ops/status", headers=auth_headers(new_token))
    assert res.status_code == 200
    assert res.json()["authenticated_as"] == "MeeksRenamed"


# ---------------------------------------------------------------------------
# Public dashboard still works (non-regression)
# ---------------------------------------------------------------------------

def test_public_health_still_works(ops_client):
    """Public /api/health must remain accessible."""
    res = ops_client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_public_dashboard_still_works(ops_client):
    """Public GET dashboard endpoint must not require Ops auth."""
    res = ops_client.get("/api/airport/KAVP/dashboard")
    assert res.status_code != 401
    assert res.status_code != 403


# ---------------------------------------------------------------------------
# Shift Handoff endpoints
# ---------------------------------------------------------------------------

_HANDOFF_PAYLOAD = {
    "airport_ident": "KAGC",
    "shift_name": "Day Shift",
    "outgoing_operator": "Alice",
    "incoming_operator": "Bob",
    "weather_summary": "VFR, winds calm.",
    "operations_summary": "Routine morning ops.",
    "open_items": "Check taxiway alpha lights.",
}


def test_get_handoffs_unauthenticated(ops_client):
    res = ops_client.get("/api/ops/handoffs")
    assert res.status_code == 401


def test_post_handoff_unauthenticated(ops_client):
    res = ops_client.post("/api/ops/handoffs", json=_HANDOFF_PAYLOAD)
    assert res.status_code == 401


def test_create_handoff_authenticated(ops_client, ops_token):
    res = ops_client.post(
        "/api/ops/handoffs",
        json=_HANDOFF_PAYLOAD,
        headers=auth_headers(ops_token),
    )
    assert res.status_code == 201
    data = res.json()
    assert "id" in data
    assert data["status"] == "created"


def test_get_handoffs_authenticated(ops_client, ops_token):
    headers = auth_headers(ops_token)
    ops_client.post("/api/ops/handoffs", json=_HANDOFF_PAYLOAD, headers=headers)
    res = ops_client.get("/api/ops/handoffs", headers=headers)
    assert res.status_code == 200
    entries = res.json()
    assert len(entries) >= 1
    assert entries[0]["shift_name"] == "Day Shift"
    assert entries[0]["outgoing_operator"] == "Alice"


def test_handoff_airport_ident_uppercased(ops_client, ops_token):
    headers = auth_headers(ops_token)
    payload = {**_HANDOFF_PAYLOAD, "airport_ident": "kagc"}
    ops_client.post("/api/ops/handoffs", json=payload, headers=headers)
    res = ops_client.get("/api/ops/handoffs", headers=headers)
    idents = [e["airport_ident"] for e in res.json()]
    assert all(i == i.upper() for i in idents)


def test_handoff_airport_filter(ops_client, ops_token):
    headers = auth_headers(ops_token)
    ops_client.post("/api/ops/handoffs", json={**_HANDOFF_PAYLOAD, "airport_ident": "KPIT"}, headers=headers)
    ops_client.post("/api/ops/handoffs", json={**_HANDOFF_PAYLOAD, "airport_ident": "KAVP"}, headers=headers)
    res = ops_client.get("/api/ops/handoffs?airport_ident=KPIT", headers=headers)
    assert res.status_code == 200
    entries = res.json()
    assert all(e["airport_ident"] == "KPIT" for e in entries)
    assert len(entries) == 1


def test_handoff_required_fields_missing(ops_client, ops_token):
    """POST without shift_name must be rejected."""
    headers = auth_headers(ops_token)
    res = ops_client.post(
        "/api/ops/handoffs",
        json={"airport_ident": "KAGC"},
        headers=headers,
    )
    assert res.status_code == 422


def test_handoff_x_admin_token(ops_client, ops_token):
    with mock.patch("app.core.config.settings.ADMIN_API_TOKEN", "test-secret"):
        res = ops_client.get(
            "/api/ops/handoffs",
            headers={"X-Admin-Token": "test-secret"},
        )
        assert res.status_code == 200


def test_handoff_created_by_is_authenticated_user(ops_client, ops_token):
    headers = auth_headers(ops_token)
    ops_client.post("/api/ops/handoffs", json=_HANDOFF_PAYLOAD, headers=headers)
    res = ops_client.get("/api/ops/handoffs", headers=headers)
    assert res.json()[0]["created_by"] == "meeks"


# ---------------------------------------------------------------------------
# Migration: old Meeks/Meeks default account normalization
# ---------------------------------------------------------------------------

import sqlite3 as _sqlite3
from datetime import datetime as _dt, timezone as _tz


@pytest.fixture
def migration_db():
    """
    DB pre-seeded with the old Meeks/Meeks default account (simulates an
    existing Docker volume from before the credential rename).  Settings are
    patched for the lifetime of each test that uses this fixture.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = str(Path(temp_dir) / "migration.sqlite")
        with mock.patch("app.core.config.settings.STATE_DIR", temp_dir), \
             mock.patch("app.core.config.settings.DB_PATH", db_path):
            from app.services.runtime_db import init_runtime_db_if_needed
            from app.services.ops_auth import hash_password
            init_runtime_db_if_needed()
            now = _dt.now(_tz.utc).isoformat()
            conn = _sqlite3.connect(db_path)
            conn.execute(
                "INSERT INTO admin_users (username, password_hash, created_at, updated_at) VALUES (?, ?, ?, ?)",
                ("Meeks", hash_password("Meeks"), now, now)
            )
            conn.commit()
            conn.close()
            yield db_path


def test_fresh_db_creates_meeks(migration_db):
    """Fresh bootstrap (empty admin_users) must create username 'meeks' with password 'meeks'."""
    # Clear the pre-seeded user so the table is empty, then bootstrap.
    conn = _sqlite3.connect(migration_db)
    conn.execute("DELETE FROM admin_users")
    conn.commit()
    conn.close()
    from app.services.ops_auth import bootstrap_default_admin, authenticate_user
    bootstrap_default_admin()
    assert authenticate_user("meeks", "meeks") == "meeks"


def test_migration_old_default_migrates_to_meeks(migration_db):
    """Old Meeks/Meeks account (unmodified default) must be migrated to meeks/meeks."""
    from app.services.ops_auth import bootstrap_default_admin, authenticate_user
    bootstrap_default_admin()
    assert authenticate_user("meeks", "meeks") == "meeks"


def test_migration_new_password_works_after_migration(migration_db):
    """meeks/meeks must succeed after migration."""
    from app.services.ops_auth import bootstrap_default_admin, authenticate_user
    bootstrap_default_admin()
    assert authenticate_user("meeks", "meeks") == "meeks"


def test_migration_old_password_rejected_after_migration(migration_db):
    """meeks/Meeks (old capitalised password) must be rejected after migration."""
    from app.services.ops_auth import bootstrap_default_admin, authenticate_user
    bootstrap_default_admin()
    assert authenticate_user("meeks", "Meeks") is None


def test_migration_custom_password_not_overwritten(migration_db):
    """If Meeks has a custom password, bootstrap must not overwrite it."""
    from app.services.ops_auth import hash_password, bootstrap_default_admin, authenticate_user
    conn = _sqlite3.connect(migration_db)
    now = _dt.now(_tz.utc).isoformat()
    conn.execute(
        "UPDATE admin_users SET password_hash = ?, updated_at = ? WHERE username = 'Meeks'",
        (hash_password("customsecret"), now)
    )
    conn.commit()
    conn.close()
    bootstrap_default_admin()
    # Custom password must still authenticate (username may be case-folded but not removed)
    assert authenticate_user("Meeks", "customsecret") is not None


def test_migration_custom_username_not_overwritten(migration_db):
    """If the only admin has a custom username (not Meeks), bootstrap must not touch it."""
    conn = _sqlite3.connect(migration_db)
    now = _dt.now(_tz.utc).isoformat()
    conn.execute(
        "UPDATE admin_users SET username = 'tower_ops', updated_at = ? WHERE username = 'Meeks'",
        (now,)
    )
    conn.commit()
    conn.close()
    from app.services.ops_auth import bootstrap_default_admin, authenticate_user
    bootstrap_default_admin()
    assert authenticate_user("tower_ops", "Meeks") is not None


# ---------------------------------------------------------------------------
# Inspection Checklist endpoints
# ---------------------------------------------------------------------------

import json as _json

_INSPECTION_PAYLOAD = {
    "airport_ident": "KAGC",
    "inspection_type": "Daily Field Review",
    "completed_by": "Alice",
    "checklist_json": _json.dumps([
        {"item": "Runways reviewed", "checked": True},
        {"item": "Taxiways reviewed", "checked": True},
        {"item": "Weather reviewed", "checked": False},
    ]),
    "notes": "Everything nominal.",
}


def test_get_inspections_unauthenticated(ops_client):
    res = ops_client.get("/api/ops/inspections")
    assert res.status_code == 401


def test_post_inspection_unauthenticated(ops_client):
    res = ops_client.post("/api/ops/inspections", json=_INSPECTION_PAYLOAD)
    assert res.status_code == 401


def test_create_inspection_authenticated(ops_client, ops_token):
    res = ops_client.post(
        "/api/ops/inspections",
        json=_INSPECTION_PAYLOAD,
        headers=auth_headers(ops_token),
    )
    assert res.status_code == 201
    data = res.json()
    assert "id" in data
    assert data["status"] == "created"


def test_get_inspections_authenticated(ops_client, ops_token):
    headers = auth_headers(ops_token)
    ops_client.post("/api/ops/inspections", json=_INSPECTION_PAYLOAD, headers=headers)
    res = ops_client.get("/api/ops/inspections", headers=headers)
    assert res.status_code == 200
    entries = res.json()
    assert len(entries) >= 1
    assert entries[0]["inspection_type"] == "Daily Field Review"
    assert entries[0]["completed_by"] == "Alice"


def test_inspection_airport_ident_uppercased(ops_client, ops_token):
    headers = auth_headers(ops_token)
    payload = {**_INSPECTION_PAYLOAD, "airport_ident": "kagc"}
    ops_client.post("/api/ops/inspections", json=payload, headers=headers)
    res = ops_client.get("/api/ops/inspections", headers=headers)
    assert all(e["airport_ident"] == e["airport_ident"].upper() for e in res.json())


def test_inspection_airport_filter(ops_client, ops_token):
    headers = auth_headers(ops_token)
    ops_client.post("/api/ops/inspections", json={**_INSPECTION_PAYLOAD, "airport_ident": "KPIT"}, headers=headers)
    ops_client.post("/api/ops/inspections", json={**_INSPECTION_PAYLOAD, "airport_ident": "KAVP"}, headers=headers)
    res = ops_client.get("/api/ops/inspections?airport_ident=KPIT", headers=headers)
    assert res.status_code == 200
    entries = res.json()
    assert all(e["airport_ident"] == "KPIT" for e in entries)
    assert len(entries) == 1


def test_inspection_checklist_json_stored_correctly(ops_client, ops_token):
    headers = auth_headers(ops_token)
    ops_client.post("/api/ops/inspections", json=_INSPECTION_PAYLOAD, headers=headers)
    res = ops_client.get("/api/ops/inspections", headers=headers)
    stored = _json.loads(res.json()[0]["checklist_json"])
    assert isinstance(stored, list)
    assert stored[0]["item"] == "Runways reviewed"
    assert stored[0]["checked"] is True
    assert stored[2]["checked"] is False


def test_inspection_invalid_checklist_json_rejected(ops_client, ops_token):
    headers = auth_headers(ops_token)
    bad = {**_INSPECTION_PAYLOAD, "checklist_json": "not valid json {{{"}
    res = ops_client.post("/api/ops/inspections", json=bad, headers=headers)
    assert res.status_code == 400


def test_inspection_missing_required_fields(ops_client, ops_token):
    """POST without inspection_type must be rejected."""
    headers = auth_headers(ops_token)
    res = ops_client.post(
        "/api/ops/inspections",
        json={"airport_ident": "KAGC", "checklist_json": "[]"},
        headers=headers,
    )
    assert res.status_code == 422


def test_inspection_x_admin_token(ops_client, ops_token):
    with mock.patch("app.core.config.settings.ADMIN_API_TOKEN", "test-secret"):
        res = ops_client.get(
            "/api/ops/inspections",
            headers={"X-Admin-Token": "test-secret"},
        )
        assert res.status_code == 200


def test_inspection_created_by_is_authenticated_user(ops_client, ops_token):
    headers = auth_headers(ops_token)
    ops_client.post("/api/ops/inspections", json=_INSPECTION_PAYLOAD, headers=headers)
    res = ops_client.get("/api/ops/inspections", headers=headers)
    assert res.json()[0]["created_by"] == "meeks"


# ---------------------------------------------------------------------------
# Maintenance Reminders tests
# ---------------------------------------------------------------------------

_MAINTENANCE_PAYLOAD = {
    "airport_ident": "KAGC",
    "title": "Check PAPI bulbs on runway 28",
    "description": "Pilot reported one bulb out during landing.",
    "priority": "High",
    "status": "Open",
    "due_date": "2026-06-01",
    "assigned_to": "Bob",
}


def test_get_maintenance_unauthenticated(ops_client):
    res = ops_client.get("/api/ops/maintenance")
    assert res.status_code == 401


def test_post_maintenance_unauthenticated(ops_client):
    res = ops_client.post("/api/ops/maintenance", json=_MAINTENANCE_PAYLOAD)
    assert res.status_code == 401


def test_patch_maintenance_unauthenticated(ops_client):
    res = ops_client.patch("/api/ops/maintenance/999", json={"status": "Closed"})
    assert res.status_code == 401


def test_create_maintenance_authenticated(ops_client, ops_token):
    res = ops_client.post(
        "/api/ops/maintenance",
        json=_MAINTENANCE_PAYLOAD,
        headers=auth_headers(ops_token),
    )
    assert res.status_code == 201
    data = res.json()
    assert "id" in data
    assert data["status"] == "created"


def test_get_maintenance_authenticated(ops_client, ops_token):
    headers = auth_headers(ops_token)
    ops_client.post("/api/ops/maintenance", json=_MAINTENANCE_PAYLOAD, headers=headers)
    res = ops_client.get("/api/ops/maintenance", headers=headers)
    assert res.status_code == 200
    items = res.json()
    assert len(items) >= 1
    assert items[0]["title"] == "Check PAPI bulbs on runway 28"
    assert items[0]["priority"] == "High"
    assert items[0]["assigned_to"] == "Bob"


def test_maintenance_airport_ident_uppercased(ops_client, ops_token):
    headers = auth_headers(ops_token)
    payload = {**_MAINTENANCE_PAYLOAD, "airport_ident": "kagc"}
    ops_client.post("/api/ops/maintenance", json=payload, headers=headers)
    res = ops_client.get("/api/ops/maintenance", headers=headers)
    assert all(i["airport_ident"] == i["airport_ident"].upper() for i in res.json())


def test_maintenance_airport_filter(ops_client, ops_token):
    headers = auth_headers(ops_token)
    ops_client.post("/api/ops/maintenance", json={**_MAINTENANCE_PAYLOAD, "airport_ident": "KPIT"}, headers=headers)
    ops_client.post("/api/ops/maintenance", json={**_MAINTENANCE_PAYLOAD, "airport_ident": "KAVP"}, headers=headers)
    res = ops_client.get("/api/ops/maintenance?airport_ident=KPIT", headers=headers)
    assert res.status_code == 200
    items = res.json()
    assert all(i["airport_ident"] == "KPIT" for i in items)
    assert len(items) == 1


def test_maintenance_status_filter(ops_client, ops_token):
    headers = auth_headers(ops_token)
    ops_client.post("/api/ops/maintenance", json={**_MAINTENANCE_PAYLOAD, "status": "Open"}, headers=headers)
    ops_client.post("/api/ops/maintenance", json={**_MAINTENANCE_PAYLOAD, "status": "Closed"}, headers=headers)
    res = ops_client.get("/api/ops/maintenance?status=Open", headers=headers)
    assert res.status_code == 200
    items = res.json()
    assert all(i["status"] == "Open" for i in items)


def test_maintenance_missing_title_rejected(ops_client, ops_token):
    headers = auth_headers(ops_token)
    bad = {k: v for k, v in _MAINTENANCE_PAYLOAD.items() if k != "title"}
    res = ops_client.post("/api/ops/maintenance", json=bad, headers=headers)
    assert res.status_code == 422


def test_maintenance_invalid_priority_rejected(ops_client, ops_token):
    headers = auth_headers(ops_token)
    bad = {**_MAINTENANCE_PAYLOAD, "priority": "Extreme"}
    res = ops_client.post("/api/ops/maintenance", json=bad, headers=headers)
    assert res.status_code == 400


def test_maintenance_invalid_status_rejected(ops_client, ops_token):
    headers = auth_headers(ops_token)
    bad = {**_MAINTENANCE_PAYLOAD, "status": "Pending"}
    res = ops_client.post("/api/ops/maintenance", json=bad, headers=headers)
    assert res.status_code == 400


def test_maintenance_patch_updates_status(ops_client, ops_token):
    headers = auth_headers(ops_token)
    create_res = ops_client.post("/api/ops/maintenance", json=_MAINTENANCE_PAYLOAD, headers=headers)
    item_id = create_res.json()["id"]
    patch_res = ops_client.patch(f"/api/ops/maintenance/{item_id}", json={"status": "In Progress"}, headers=headers)
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "In Progress"


def test_maintenance_patch_closed_sets_closed_at(ops_client, ops_token):
    headers = auth_headers(ops_token)
    create_res = ops_client.post("/api/ops/maintenance", json=_MAINTENANCE_PAYLOAD, headers=headers)
    item_id = create_res.json()["id"]
    ops_client.patch(f"/api/ops/maintenance/{item_id}", json={"status": "Closed"}, headers=headers)
    get_res = ops_client.get("/api/ops/maintenance", headers=headers)
    item = next(i for i in get_res.json() if i["id"] == item_id)
    assert item["status"] == "Closed"
    assert item["closed_at"] is not None


def test_maintenance_patch_reopen_clears_closed_at(ops_client, ops_token):
    headers = auth_headers(ops_token)
    create_res = ops_client.post("/api/ops/maintenance", json=_MAINTENANCE_PAYLOAD, headers=headers)
    item_id = create_res.json()["id"]
    ops_client.patch(f"/api/ops/maintenance/{item_id}", json={"status": "Closed"}, headers=headers)
    ops_client.patch(f"/api/ops/maintenance/{item_id}", json={"status": "Open"}, headers=headers)
    get_res = ops_client.get("/api/ops/maintenance", headers=headers)
    item = next(i for i in get_res.json() if i["id"] == item_id)
    assert item["status"] == "Open"
    assert item["closed_at"] is None


def test_maintenance_x_admin_token(ops_client, ops_token):
    with mock.patch("app.core.config.settings.ADMIN_API_TOKEN", "test-secret"):
        res = ops_client.get(
            "/api/ops/maintenance",
            headers={"X-Admin-Token": "test-secret"},
        )
        assert res.status_code == 200


def test_maintenance_created_by_is_authenticated_user(ops_client, ops_token):
    headers = auth_headers(ops_token)
    ops_client.post("/api/ops/maintenance", json=_MAINTENANCE_PAYLOAD, headers=headers)
    res = ops_client.get("/api/ops/maintenance", headers=headers)
    assert res.json()[0]["created_by"] == "meeks"
