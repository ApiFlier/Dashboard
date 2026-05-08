import pytest
import sqlite3
import os
import tempfile
from pathlib import Path
from scripts.import_ourairports import import_ourairports

@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test_ref.sqlite"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)")
        conn.execute("""
            CREATE TABLE airports (
                ident TEXT PRIMARY KEY, name TEXT, iata_code TEXT, type TEXT, city TEXT, state TEXT, country TEXT, 
                lat REAL, lon REAL, elevation_ft INTEGER, source TEXT, updated_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE runways (
                id INTEGER PRIMARY KEY AUTOINCREMENT, airport_ident TEXT, surface_id TEXT, 
                le_heading_deg REAL, le_latitude_deg REAL, le_longitude_deg REAL, 
                he_latitude_deg REAL, he_longitude_deg REAL, length_ft INTEGER, width_ft INTEGER, 
                surface TEXT, closed INTEGER, source TEXT, updated_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE frequencies (
                id INTEGER PRIMARY KEY AUTOINCREMENT, airport_ident TEXT, type TEXT, 
                description TEXT, frequency_mhz REAL, source TEXT, updated_at TEXT
            )
        """)
        conn.commit()
        conn.close()
        yield str(db_path)

@pytest.fixture
def sample_csvs(tmp_path):
    data_dir = tmp_path / "ourairports"
    data_dir.mkdir()
    
    airports_csv = data_dir / "airports.csv"
    with open(airports_csv, "w") as f:
        f.write("ident,type,name,latitude_deg,longitude_deg,elevation_ft,iso_country,iso_region,municipality,scheduled_service,iata_code\n")
        f.write("KLAX,large_airport,Los Angeles International Airport,33.9425,-118.408,125,US,US-CA,Los Angeles,yes,LAX\n")
        f.write("KPHL,large_airport,Philadelphia International Airport,39.8719,-75.2411,36,US,US-PA,Philadelphia,yes,PHL\n")
        f.write("TEST,small_airport,Test Strip,0,0,0,US,US-ZZ,Test,no,\n")
    
    runways_csv = data_dir / "runways.csv"
    with open(runways_csv, "w") as f:
        f.write("id,airport_ident,length_ft,width_ft,surface,closed,le_ident,le_latitude_deg,le_longitude_deg,le_heading_degT,he_ident,he_latitude_deg,he_longitude_deg,he_heading_degT\n")
        f.write("1,KLAX,12091,150,ASP,0,25L,33.937,-118.42,251,07R,33.944,-118.38,71\n")
    
    freqs_csv = data_dir / "airport-frequencies.csv"
    with open(freqs_csv, "w") as f:
        f.write("id,airport_ident,type,description,frequency_mhz\n")
        f.write("1,KLAX,TWR,Tower,133.9\n")
        
    return data_dir

def test_import_basic(temp_db, sample_csvs):
    import_ourairports(temp_db, str(sample_csvs), ["US"], ["large_airport", "small_airport"])
    
    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Check airports
    cursor.execute("SELECT * FROM airports")
    airports = cursor.fetchall()
    assert len(airports) == 3
    klax = next(a for a in airports if a['ident'] == 'KLAX')
    assert klax['name'] == "Los Angeles International Airport"
    assert klax['iata_code'] == "LAX"
    
    # Check runways
    cursor.execute("SELECT * FROM runways WHERE airport_ident = 'KLAX'")
    runways = cursor.fetchall()
    assert len(runways) == 2 # 25L and 07R
    r25l = next(r for r in runways if r['surface_id'] == '25L')
    assert r25l['le_latitude_deg'] == 33.937
    assert r25l['he_latitude_deg'] == 33.944
    
    # Check frequencies
    cursor.execute("SELECT * FROM frequencies WHERE airport_ident = 'KLAX'")
    freqs = cursor.fetchall()
    assert len(freqs) == 1
    assert freqs[0]['frequency_mhz'] == 133.9
    
    # Check metadata
    cursor.execute("SELECT value FROM schema_meta WHERE key = 'ref_data_source'")
    assert cursor.fetchone()[0] == "OurAirports"
    
    conn.close()

def test_import_curated_protection(temp_db, sample_csvs):
    # Setup curated data
    conn = sqlite3.connect(temp_db)
    conn.execute("INSERT INTO airports (ident, name, source) VALUES ('KAVP', 'Curated AVP', 'seed_json')")
    conn.execute("INSERT INTO runways (airport_ident, surface_id, source) VALUES ('KAVP', '04', 'seed_json')")
    conn.commit()
    conn.close()
    
    # Add KAVP to sample CSVs
    airports_csv = sample_csvs / "airports.csv"
    with open(airports_csv, "a") as f:
        f.write("KAVP,large_airport,Wilkes-Barre/Scranton International Airport,41.3385,-75.7234,962,US,US-PA,Scranton,yes,AVP\n")
    
    runways_csv = sample_csvs / "runways.csv"
    with open(runways_csv, "a") as f:
        f.write("2,KAVP,7501,150,ASP,0,04,41.32,-75.73,41,22,41.35,-75.71,221\n")

    import_ourairports(temp_db, str(sample_csvs), ["US"], ["large_airport"])
    
    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Verify KAVP name still curated
    cursor.execute("SELECT name, source FROM airports WHERE ident = 'KAVP'")
    row = cursor.fetchone()
    assert row['name'] == "Curated AVP"
    assert row['source'] == "seed_json"
    
    # Verify KAVP runways still curated
    cursor.execute("SELECT count(*) as cnt FROM runways WHERE airport_ident = 'KAVP'")
    assert cursor.fetchone()['cnt'] == 1
    cursor.execute("SELECT source FROM runways WHERE airport_ident = 'KAVP'")
    assert cursor.fetchone()[0] == "seed_json"
    
    conn.close()
