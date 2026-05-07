#!/usr/bin/env python3
import json
import sys
import sqlite3
import os
from pathlib import Path

def get_db_path():
    # Try to find DB path from environment or default
    return os.environ.get("AIRFIELDOPS_DB_PATH", "/var/lib/airfieldops/airfieldops.sqlite")

def validate_db():
    db_path = get_db_path()
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}, skipping DB validation.")
        return True

    print(f"--- Database Reference Data Validation ---")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    errors = []
    warnings = []

    # 1. Airports
    cursor.execute("SELECT * FROM airports")
    airports = cursor.fetchall()
    print(f"Airports: {len(airports)}")
    
    seen_idents = set()
    for a in airports:
        ident = a['ident']
        if ident in seen_idents:
            errors.append(f"Duplicate airport ident in DB: {ident}")
        seen_idents.add(ident)

        if not a['name']:
            warnings.append(f"Airport {ident} missing name")
        
        lat = a['lat']
        lon = a['lon']
        if lat is None or lon is None:
            errors.append(f"Airport {ident} missing lat/lon")
        else:
            if not (-90 <= lat <= 90):
                errors.append(f"Airport {ident} invalid lat: {lat}")
            if not (-180 <= lon <= 180):
                errors.append(f"Airport {ident} invalid lon: {lon}")

    # 2. Runways
    cursor.execute("SELECT * FROM runways")
    runways = cursor.fetchall()
    print(f"Runway entries: {len(runways)}")
    
    for r in runways:
        rid = f"{r['airport_ident']}-{r['surface_id']}"
        if r['airport_ident'] not in seen_idents:
            errors.append(f"Runway {rid} references unknown airport")
        
        if r['closed'] == 1:
            warnings.append(f"Runway {rid} is closed but present in DB")

        # Heading check
        heading = r['le_heading_deg']
        if heading is not None:
            if not (0 <= heading <= 360):
                errors.append(f"Runway {rid} invalid heading: {heading}")
        
        # Geometry check
        coords = [r['le_latitude_deg'], r['le_longitude_deg'], r['he_latitude_deg'], r['he_longitude_deg']]
        if any(c is not None for c in coords):
            # If any coord present, check ranges
            if r['le_latitude_deg'] is not None and not (-90 <= r['le_latitude_deg'] <= 90):
                errors.append(f"Runway {rid} invalid le_lat: {r['le_latitude_deg']}")
            if r['le_longitude_deg'] is not None and not (-180 <= r['le_longitude_deg'] <= 180):
                errors.append(f"Runway {rid} invalid le_lon: {r['le_longitude_deg']}")
            if r['he_latitude_deg'] is not None and not (-90 <= r['he_latitude_deg'] <= 90):
                errors.append(f"Runway {rid} invalid he_lat: {r['he_latitude_deg']}")
            if r['he_longitude_deg'] is not None and not (-180 <= r['he_longitude_deg'] <= 180):
                errors.append(f"Runway {rid} invalid he_lon: {r['he_longitude_deg']}")

        # Numeric checks
        if r['length_ft'] is not None and r['length_ft'] <= 0:
            warnings.append(f"Runway {rid} non-positive length: {r['length_ft']}")

    # 3. Frequencies
    cursor.execute("SELECT * FROM frequencies")
    frequencies = cursor.fetchall()
    print(f"Frequency entries: {len(frequencies)}")
    
    for f in frequencies:
        if f['airport_ident'] not in seen_idents:
            errors.append(f"Frequency {f['type']} at {f['airport_ident']} references unknown airport")
        
        if f['frequency_mhz'] is not None:
            if f['frequency_mhz'] <= 0 or f['frequency_mhz'] > 1000:
                warnings.append(f"Frequency {f['frequency_mhz']} at {f['airport_ident']} out of typical range")

    conn.close()

    # Output results
    print(f"\nWarnings: {len(warnings)}")
    for w in warnings[:10]:
        print(f"  [W] {w}")
    if len(warnings) > 10:
        print(f"  ... and {len(warnings) - 10} more")

    print(f"Errors: {len(errors)}")
    for e in errors[:10]:
        print(f"  [E] {e}")
    if len(errors) > 10:
        print(f"  ... and {len(errors) - 10} more")

    return len(errors) == 0

def validate_seeds():
    data_dir = Path(__file__).parent.parent / "app" / "data"
    airports_file = data_dir / "airports_seed.json"
    runways_file = data_dir / "runways_seed.json"
    frequencies_file = data_dir / "frequencies_seed.json"

    errors = []
    warnings = []

    try:
        with open(airports_file) as f:
            airports = json.load(f)
        with open(runways_file) as f:
            runways = json.load(f)
        with open(frequencies_file) as f:
            frequencies = json.load(f)
    except Exception as e:
        print(f"Error loading files: {e}")
        return False

    airport_idents = {a.get("icao") for a in airports if a.get("icao")}
    
    print(f"\n--- Seed JSON Reference Data Validation ---")
    print(f"Airports: {len(airports)}")
    print(f"Runway entries: {len(runways)}")
    print(f"Frequency entries: {len(frequencies)}")

    for a in airports:
        ident = a.get("icao")
        if not ident:
            errors.append("Seed: Airport missing icao ident")
            continue
        if not (-90 <= a['lat'] <= 90) or not (-180 <= a['lon'] <= 180):
            errors.append(f"Seed: Airport {ident} invalid coords")

    for ident, rwys in runways.items():
        if ident not in airport_idents:
            errors.append(f"Seed: Runways for unknown airport: {ident}")
        for r in rwys:
            if r.get("heading") is not None and not (0 <= r["heading"] <= 360):
                errors.append(f"Seed: Runway {r.get('id')} in {ident} invalid heading")

    # Output results
    print(f"Warnings: {len(warnings)}")
    print(f"Errors: {len(errors)}")
    for e in errors[:10]:
        print(f"  [E] {e}")

    return len(errors) == 0

if __name__ == "__main__":
    db_ok = validate_db()
    seed_ok = validate_seeds()
    
    if not db_ok or not seed_ok:
        sys.exit(1)
    else:
        print("\nValidation PASSED.")
