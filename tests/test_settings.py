import pytest
from unittest import mock
import sqlite3
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.services import runtime_db

client = TestClient(app)

@pytest.fixture
def temp_db_with_settings():
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test_airfieldops.sqlite"
        with mock.patch("app.core.config.settings.STATE_DIR", temp_dir):
            with mock.patch("app.core.config.settings.DB_PATH", str(db_path)):
                runtime_db.ensure_state_dir()
                conn = sqlite3.connect(str(db_path))
                conn.row_factory = sqlite3.Row
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                conn.execute("INSERT INTO settings (key, value, updated_at) VALUES ('default_airport', 'KXYZ', 'now')")
                conn.execute("INSERT INTO settings (key, value, updated_at) VALUES ('theme_mode', 'dark', 'now')")
                conn.execute("INSERT INTO settings (key, value, updated_at) VALUES ('monitor_mode', '1', 'now')")
                conn.commit()
                # Initialize airports table to pass the PUT validation
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS airports (
                        ident TEXT PRIMARY KEY,
                        iata_code TEXT,
                        name TEXT,
                        type TEXT,
                        city TEXT,
                        state TEXT,
                        country TEXT,
                        lat REAL,
                        lon REAL,
                        elevation_ft INTEGER,
                        source TEXT,
                        updated_at TEXT
                    )
                """)
                conn.execute("INSERT INTO airports (ident, name) VALUES ('KXYZ', 'Test Airport')")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS frequencies (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        airport_ident TEXT NOT NULL,
                        type TEXT,
                        description TEXT,
                        frequency_mhz REAL,
                        source TEXT,
                        updated_at TEXT
                    )
                """)
                conn.commit()
                yield str(db_path)

def test_settings_defaults_from_db_or_config(temp_db_with_settings):
    with mock.patch("app.core.config.settings.DB_PATH", temp_db_with_settings):
        response = client.get("/api/settings/defaults")
        assert response.status_code == 200
        assert response.json()["default_airport"] == "KXYZ"

def test_settings_defaults_fallback():
    with mock.patch("app.core.config.settings.DB_PATH", "/does/not/exist/db.sqlite"):
        with mock.patch.dict("os.environ", {"DEFAULT_AIRPORT": "KABC"}):
            response = client.get("/api/settings/defaults")
            assert response.status_code == 200
            assert response.json()["default_airport"] == "KABC"

def test_get_settings(temp_db_with_settings):
    with mock.patch("app.core.config.settings.DB_PATH", temp_db_with_settings):
        response = client.get("/api/settings")
        assert response.status_code == 200
        data = response.json()
        assert data["default_airport"] == "KXYZ"
        assert data["theme_mode"] == "dark"
        assert data["monitor_mode"] is True

def test_put_settings(temp_db_with_settings):
    with mock.patch("app.core.config.settings.DB_PATH", temp_db_with_settings):
        with mock.patch("app.core.config.settings.PUBLIC_READONLY_MODE", False):
            response = client.put(
                "/api/settings",
                json={
                    "default_airport": "KXYZ",
                    "alternate_radius_nm": 100,
                    "refresh_interval_seconds": 600,
                    "theme_mode": "light",
                    "monitor_mode": False,
                    "show_raw_weather_default": False,
                    "accent_color": "green"
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert data["theme_mode"] == "light"
            assert data["monitor_mode"] is False
            assert data["show_raw_weather_default"] is False

            # Verify DB changed
            get_response = client.get("/api/settings")
            assert get_response.json()["theme_mode"] == "light"
            assert get_response.json()["monitor_mode"] is False
