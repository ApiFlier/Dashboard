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
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                conn.execute("INSERT INTO settings (key, value, updated_at) VALUES ('default_airport', 'KXYZ', 'now')")
                conn.commit()
                yield str(db_path)

def test_settings_defaults_from_db_or_config(temp_db_with_settings):
    with mock.patch("app.core.config.settings.DB_PATH", temp_db_with_settings):
        response = client.get("/api/settings/defaults")
        assert response.status_code == 200
        assert response.json()["default_airport"] == "KXYZ"

def test_settings_defaults_fallback():
    # Provide a path that doesn't exist so it throws OperationalError
    with mock.patch("app.core.config.settings.DB_PATH", "/does/not/exist/db.sqlite"):
        with mock.patch.dict("os.environ", {"DEFAULT_AIRPORT": "KABC"}):
            response = client.get("/api/settings/defaults")
            assert response.status_code == 200
            assert response.json()["default_airport"] == "KABC"
