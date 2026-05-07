import pytest
import sqlite3
import os
import json
from pathlib import Path
from app.services.runtime_db import (
    get_connection, 
    seed_reference_data_from_json, 
    get_db_path,
    run_migrations,
    seed_default_settings
)

def test_seeder_preserves_settings(tmp_path):
    db_file = tmp_path / "test_ref_seed.sqlite"
    
    # Mock settings.DB_PATH
    import app.services.runtime_db
    original_db_path = app.services.runtime_db.get_db_path
    app.services.runtime_db.get_db_path = lambda: str(db_file)
    
    try:
        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
        
        run_migrations(conn)
        seed_default_settings(conn)
        
        # Manually change a setting
        conn.execute("UPDATE settings SET value = 'KPIT' WHERE key = 'default_airport'")
        conn.commit()
        
        # Run seeder
        seed_reference_data_from_json(conn)
        conn.commit()
        
        # Verify setting preserved
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = 'default_airport'")
        assert cursor.fetchone()["value"] == "KPIT"
        
        # Verify airports seeded
        cursor.execute("SELECT count(*) FROM airports")
        assert cursor.fetchone()[0] > 0
        
    finally:
        app.services.runtime_db.get_db_path = original_db_path
        if db_file.exists():
            os.remove(db_file)

def test_seeder_updates_existing_airport_safely(tmp_path):
    db_file = tmp_path / "test_ref_update.sqlite"
    
    import app.services.runtime_db
    original_db_path = app.services.runtime_db.get_db_path
    app.services.runtime_db.get_db_path = lambda: str(db_file)
    
    try:
        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
        run_migrations(conn)
        
        # Insert a "stale" airport
        conn.execute(
            "INSERT INTO airports (ident, name, lat, lon, elevation_ft, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("KAGC", "Old Name", 40.0, -79.0, 1000, "2020-01-01T00:00:00Z")
        )
        conn.commit()
        
        # Run seeder (which should update KAGC from JSON)
        seed_reference_data_from_json(conn)
        conn.commit()
        
        cursor = conn.cursor()
        cursor.execute("SELECT name, lat, lon FROM airports WHERE ident = 'KAGC'")
        row = cursor.fetchone()
        assert row["name"] == "Allegheny County Airport"
        assert row["lat"] == 40.3544
        
    finally:
        app.services.runtime_db.get_db_path = original_db_path
        if db_file.exists():
            os.remove(db_file)

def test_reference_status_endpoint(tmp_path):
    # This test verifies the schema metadata in the status endpoint
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app
    from app.services.runtime_db import init_runtime_db_if_needed

    db_file = tmp_path / "test_status.sqlite"
    import app.services.runtime_db
    original_db_path = app.services.runtime_db.get_db_path
    app.services.runtime_db.get_db_path = lambda: str(db_file)

    try:
        init_runtime_db_if_needed()
        
        client = TestClient(fastapi_app)
        response = client.get("/api/reference/status")
        assert response.status_code == 200
        data = response.json()
        
        assert "airport_count" in data
        assert "schema_version" in data
        assert "db_path" in data
        assert data["data_version"] == "1.1.0"
        assert data["schema_version"] >= 1
        
    finally:
        app.services.runtime_db.get_db_path = original_db_path
        if db_file.exists():
            os.remove(db_file)

def test_backup_script_execution():
    # Basic check that backup.sh is executable and runs without error
    import subprocess
    import os
    
    if os.path.exists("./backup.sh"):
        result = subprocess.run(["./backup.sh"], capture_output=True, text=True)
        assert result.returncode == 0
        assert "Backup successfully created" in result.stdout
