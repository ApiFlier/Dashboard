import pytest
import os
import sqlite3
import json
from scripts.import_ourairports import import_ourairports

@pytest.fixture
def test_db(tmp_path):
    db_path = tmp_path / "test_airfieldops.sqlite"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)")
    cursor.execute("""
        CREATE TABLE airports (
            ident TEXT PRIMARY KEY, name TEXT, city TEXT, state TEXT, country TEXT, 
            lat REAL, lon REAL, elevation_ft INTEGER, source TEXT, updated_at TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE runways (
            id INTEGER PRIMARY KEY AUTOINCREMENT, airport_ident TEXT, surface_id TEXT, 
            le_heading_deg REAL, le_latitude_deg REAL, le_longitude_deg REAL, 
            he_latitude_deg REAL, he_longitude_deg REAL, length_ft INTEGER, 
            width_ft INTEGER, surface TEXT, closed INTEGER, source TEXT, updated_at TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE frequencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT, airport_ident TEXT, type TEXT, 
            description TEXT, frequency_mhz REAL, source TEXT, updated_at TEXT
        )
    """)
    
    # Add curated KAVP
    cursor.execute("""
        INSERT INTO airports (ident, name, source, updated_at) 
        VALUES ('KAVP', 'Curated Wilkes-Barre', 'seed_json', '2026-01-01T00:00:00Z')
    """)
    cursor.execute("""
        INSERT INTO runways (airport_ident, surface_id, source, length_ft) 
        VALUES ('KAVP', '04', 'seed_json', 7501)
    """)
    cursor.execute("""
        INSERT INTO frequencies (airport_ident, type, source) 
        VALUES ('KAVP', 'TWR', 'seed_json')
    """)
    
    conn.commit()
    conn.close()
    return str(db_path)

def test_dry_run_does_not_mutate(test_db):
    data_dir = "tests/fixtures/ourairports"
    report = import_ourairports(test_db, data_dir, ["US"], ["large_airport", "small_airport"], dry_run=True)
    
    assert report["dry_run"] is True
    assert report["airports"]["inserted"] == 1 # KTEST
    assert report["airports"]["preserved"] == 1 # KAVP
    
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM airports WHERE ident = 'KTEST'")
    assert cursor.fetchone()[0] == 0
    
    cursor.execute("SELECT name FROM airports WHERE ident = 'KAVP'")
    assert cursor.fetchone()[0] == 'Curated Wilkes-Barre'
    conn.close()

def test_import_preserves_curated(test_db):
    data_dir = "tests/fixtures/ourairports"
    report = import_ourairports(test_db, data_dir, ["US"], ["large_airport", "small_airport"], dry_run=False)
    
    assert report["airports"]["inserted"] == 1 # KTEST
    assert report["airports"]["preserved"] == 1 # KAVP
    assert report["runways"]["preserved"] == 1 # KAVP 04 (preserved as 1 entry in our dummy setup)
    
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    
    # Check KAVP (preserved)
    cursor.execute("SELECT name, source FROM airports WHERE ident = 'KAVP'")
    row = cursor.fetchone()
    assert row[0] == 'Curated Wilkes-Barre'
    assert row[1] == 'seed_json'
    
    # Check KTEST (inserted)
    cursor.execute("SELECT name, source FROM airports WHERE ident = 'KTEST'")
    row = cursor.fetchone()
    assert row[0] == 'Test Airport'
    assert row[1] == 'OurAirports'
    
    conn.close()

def test_report_generation(test_db, tmp_path):
    data_dir = "tests/fixtures/ourairports"
    report_path = tmp_path / "report.json"
    import_ourairports(test_db, data_dir, ["US"], ["large_airport", "small_airport"], dry_run=False, report_path=str(report_path))
    
    assert os.path.exists(report_path)
    with open(report_path) as f:
        data = json.load(f)
    assert data["airports"]["inserted"] == 1
    assert data["final_counts"]["airports"] == 2
