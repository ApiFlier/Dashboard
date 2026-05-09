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
    """Returns a valid session token for the default Meeks admin."""
    res = ops_client.post("/api/ops/auth/login", json={"username": "Meeks", "password": "Meeks"})
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
    """Default Meeks/Meeks admin must exist after startup."""
    import sqlite3
    from app.core.config import settings as cfg
    conn = sqlite3.connect(cfg.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM admin_users")
    rows = cursor.fetchall()
    conn.close()
    usernames = [r["username"] for r in rows]
    assert "Meeks" in usernames


# ---------------------------------------------------------------------------
# Auth: login
# ---------------------------------------------------------------------------

def test_login_valid_credentials(ops_client):
    res = ops_client.post("/api/ops/auth/login", json={"username": "Meeks", "password": "Meeks"})
    assert res.status_code == 200
    data = res.json()
    assert "token" in data
    assert data["username"] == "Meeks"


def test_login_invalid_password(ops_client):
    res = ops_client.post("/api/ops/auth/login", json={"username": "Meeks", "password": "wrong"})
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
        json={"current_password": "Meeks", "new_username": "MeeksRenamed"},
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
