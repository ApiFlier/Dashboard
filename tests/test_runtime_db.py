import os
import sqlite3
import pytest
from pathlib import Path
from unittest import mock
import tempfile
import json

from app.services import runtime_db
from app.services.airport_data import get_airport_directory, search_airports, get_airport_runways, get_all_airports

@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test_airfieldops.sqlite"
        
        with mock.patch("app.core.config.settings.STATE_DIR", temp_dir):
            with mock.patch("app.core.config.settings.DB_PATH", str(db_path)):
                # Ensure the test state dir exists
                runtime_db.ensure_state_dir()
                
                # Mock seed json for testing seeding
                seed_airports = [{"icao": "TEST", "name": "Test Airport", "lat": 1.0, "lon": 2.0, "elevation_ft": 100}]
                seed_runways = {"TEST": [{"id": "01", "length_ft": 5000, "width_ft": 100}]}
                seed_frequencies = {"TEST": [{"type": "TWR", "frequency": "118.1"}]}
                
                with mock.patch("builtins.open", mock.mock_open()) as mocked_file:
                    def side_effect(path, *args, **kwargs):
                        path_str = str(path)
                        if "airports_seed.json" in path_str:
                            return mock.mock_open(read_data=json.dumps(seed_airports)).return_value
                        if "runways_seed.json" in path_str:
                            return mock.mock_open(read_data=json.dumps(seed_runways)).return_value
                        if "frequencies_seed.json" in path_str:
                            return mock.mock_open(read_data=json.dumps(seed_frequencies)).return_value
                        return mock.mock_open(read_data="{}").return_value
                    
                    mocked_file.side_effect = side_effect
                    
                    runtime_db.init_runtime_db_if_needed()
                    yield str(db_path)

def test_runtime_db_creates_schema(temp_db):
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    
    assert "schema_meta" in tables
    assert "airports" in tables
    assert "runways" in tables
    assert "frequencies" in tables
    assert "settings" in tables
    assert "recent_airports" in tables

def test_runtime_db_seeds_airports(temp_db):
    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM airports WHERE ident='TEST'")
    airport = cursor.fetchone()
    assert airport is not None
    assert airport["name"] == "Test Airport"

    cursor.execute("SELECT * FROM runways WHERE airport_ident='TEST'")
    runways = cursor.fetchall()
    assert len(runways) == 1
    assert runways[0]["surface_id"] == "01"

def test_runtime_db_does_not_overwrite_existing_db(temp_db):
    # Add some custom data
    conn = sqlite3.connect(temp_db)
    conn.execute("INSERT INTO settings (key, value, updated_at) VALUES ('test_key', 'test_val', 'now')")
    conn.commit()
    conn.close()

    # Re-init should not blow away data
    with mock.patch("app.core.config.settings.DB_PATH", temp_db):
        runtime_db.init_runtime_db_if_needed()
    
    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key='test_key'")
    assert cursor.fetchone()["value"] == "test_val"

def test_airport_data_reads_from_runtime_db(temp_db):
    with mock.patch("app.core.config.settings.DB_PATH", temp_db):
        # We initialized temp_db with "TEST" airport.
        airport = get_airport_directory("TEST")
        assert airport is not None
        assert airport["icao"] == "TEST"
        assert airport["name"] == "Test Airport"
        assert len(airport["frequencies"]) == 1

        runways = get_airport_runways("TEST")
        assert len(runways) == 1
        assert runways[0]["id"] == "01"

        search = search_airports("test")
        assert len(search) == 1
        assert search[0]["ident"] == "TEST"
        all_apts = get_all_airports()
        assert len(all_apts) >= 1
