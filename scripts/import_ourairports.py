#!/usr/bin/env python3
import csv
import sqlite3
import os
import argparse
import urllib.request
import json
from datetime import datetime, timezone
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Constants
OURAIRPORTS_BASE_URL = "https://davidmegginson.github.io/ourairports-data"
FILES = {
    "airports": "airports.csv",
    "runways": "runways.csv",
    "frequencies": "airport-frequencies.csv"
}

DEFAULT_COUNTRIES = ["US"]
DEFAULT_AIRPORT_TYPES = ["large_airport", "medium_airport", "small_airport"]

CURATED_AIRPORTS = ['KAVP', 'KAGC']

def download_file(url, dest):
    logger.info(f"Downloading {url} to {dest}...")
    urllib.request.urlretrieve(url, dest)

def get_db_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def import_ourairports(db_path, data_dir, countries, types, download=False, dry_run=False, report_path=None):
    if download and not dry_run:
        os.makedirs(data_dir, exist_ok=True)
        for key, filename in FILES.items():
            url = f"{OURAIRPORTS_BASE_URL}/{filename}"
            download_file(url, os.path.join(data_dir, filename))

    now = datetime.now(timezone.utc).isoformat()
    
    report = {
        "timestamp": now,
        "dry_run": dry_run,
        "parameters": {
            "countries": countries,
            "types": types
        },
        "airports": {"inserted": 0, "updated": 0, "skipped": 0, "preserved": 0},
        "runways": {"inserted": 0, "updated": 0, "skipped": 0, "preserved": 0},
        "frequencies": {"inserted": 0, "updated": 0, "skipped": 0, "preserved": 0},
        "conflicts": [],
        "warnings": []
    }

    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # 1. Load Airports
    airports_path = os.path.join(data_dir, FILES["airports"])
    if not os.path.exists(airports_path):
        logger.error(f"Airports file not found: {airports_path}")
        report["errors"] = [f"Airports file not found: {airports_path}"]
        return report

    logger.info(f"Importing airports from {airports_path}...")
    imported_airports = set()
    with open(airports_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['iso_country'] not in countries:
                continue
            if row['type'] not in types:
                continue
            
            ident = row['ident']
            
            cursor.execute("SELECT source, name FROM airports WHERE ident = ?", (ident,))
            existing = cursor.fetchone()
            
            if ident in CURATED_AIRPORTS:
                if existing and existing['source'] == 'seed_json':
                    logger.info(f"Preserving curated airport metadata for {ident}")
                    report["airports"]["preserved"] += 1
                    imported_airports.add(ident)
                    continue
                else:
                    report["conflicts"].append({
                        "type": "airport",
                        "ident": ident,
                        "message": f"Curated airport {ident} missing from DB or not marked as seed_json. Importing as regular."
                    })

            if dry_run:
                if existing:
                    report["airports"]["updated"] += 1
                else:
                    report["airports"]["inserted"] += 1
            else:
                cursor.execute("""
                    INSERT OR REPLACE INTO airports (ident, name, city, state, country, lat, lon, elevation_ft, source, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ident,
                    row['name'],
                    row['municipality'],
                    row['iso_region'].split('-')[-1],
                    row['iso_country'],
                    float(row['latitude_deg']),
                    float(row['longitude_deg']),
                    int(row['elevation_ft']) if row['elevation_ft'] and row['elevation_ft'].isdigit() else None,
                    "OurAirports",
                    now
                ))
                if existing:
                    report["airports"]["updated"] += 1
                else:
                    report["airports"]["inserted"] += 1
            
            imported_airports.add(ident)

    logger.info(f"Airports: {report['airports']['inserted']} inserted, {report['airports']['updated']} updated, {report['airports']['preserved']} preserved.")

    # 2. Load Runways
    runways_path = os.path.join(data_dir, FILES["runways"])
    if os.path.exists(runways_path):
        logger.info(f"Importing runways from {runways_path}...")
        
        if not dry_run:
            cursor.execute("DELETE FROM runways WHERE source = 'OurAirports'")

        with open(runways_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                apt_ident = row['airport_ident']
                if apt_ident not in imported_airports:
                    continue
                
                if row['closed'] == '1':
                    report["runways"]["skipped"] += 1
                    continue

                if apt_ident in CURATED_AIRPORTS:
                    cursor.execute("SELECT count(*) as cnt FROM runways WHERE airport_ident = ? AND source = 'seed_json'", (apt_ident,))
                    if cursor.fetchone()['cnt'] > 0:
                        report["runways"]["preserved"] += 1
                        continue

                # Geometry check for logging
                has_geometry = row['le_latitude_deg'] and row['le_longitude_deg'] and row['he_latitude_deg'] and row['he_longitude_deg']
                if not has_geometry:
                    report["warnings"].append(f"Runway {apt_ident} {row['le_ident']}/{row['he_ident']} missing geometry. Fallback will be used in UI.")

                if dry_run:
                    report["runways"]["inserted"] += 2
                else:
                    if row['le_ident']:
                        cursor.execute("""
                            INSERT INTO runways (
                                airport_ident, surface_id, le_heading_deg, 
                                le_latitude_deg, le_longitude_deg, 
                                he_latitude_deg, he_longitude_deg, 
                                length_ft, width_ft, surface, closed, source, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            apt_ident,
                            row['le_ident'],
                            float(row['le_heading_degT']) if row['le_heading_degT'] else None,
                            float(row['le_latitude_deg']) if row['le_latitude_deg'] else None,
                            float(row['le_longitude_deg']) if row['le_longitude_deg'] else None,
                            float(row['he_latitude_deg']) if row['he_latitude_deg'] else None,
                            float(row['he_longitude_deg']) if row['he_longitude_deg'] else None,
                            int(row['length_ft']) if row['length_ft'] and row['length_ft'].isdigit() else None,
                            int(row['width_ft']) if row['width_ft'] and row['width_ft'].isdigit() else None,
                            row['surface'],
                            0,
                            "OurAirports",
                            now
                        ))
                        report["runways"]["inserted"] += 1

                    if row['he_ident']:
                        cursor.execute("""
                            INSERT INTO runways (
                                airport_ident, surface_id, le_heading_deg, 
                                le_latitude_deg, le_longitude_deg, 
                                he_latitude_deg, he_longitude_deg, 
                                length_ft, width_ft, surface, closed, source, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            apt_ident,
                            row['he_ident'],
                            float(row['he_heading_degT']) if row['he_heading_degT'] else None,
                            float(row['he_latitude_deg']) if row['he_latitude_deg'] else None,
                            float(row['he_longitude_deg']) if row['he_longitude_deg'] else None,
                            float(row['le_latitude_deg']) if row['le_latitude_deg'] else None,
                            float(row['le_longitude_deg']) if row['le_longitude_deg'] else None,
                            int(row['length_ft']) if row['length_ft'] and row['length_ft'].isdigit() else None,
                            int(row['width_ft']) if row['width_ft'] and row['width_ft'].isdigit() else None,
                            row['surface'],
                            0,
                            "OurAirports",
                            now
                        ))
                        report["runways"]["inserted"] += 1
        logger.info(f"Runways: {report['runways']['inserted']} inserted, {report['runways']['preserved']} preserved.")

    # 3. Load Frequencies
    freq_path = os.path.join(data_dir, FILES["frequencies"])
    if os.path.exists(freq_path):
        logger.info(f"Importing frequencies from {freq_path}...")
        
        if not dry_run:
            cursor.execute("DELETE FROM frequencies WHERE source = 'OurAirports'")

        with open(freq_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                apt_ident = row['airport_ident']
                if apt_ident not in imported_airports:
                    continue
                
                if apt_ident in CURATED_AIRPORTS:
                    cursor.execute("SELECT count(*) as cnt FROM frequencies WHERE airport_ident = ? AND source = 'seed_json'", (apt_ident,))
                    if cursor.fetchone()['cnt'] > 0:
                        report["frequencies"]["preserved"] += 1
                        continue

                if dry_run:
                    report["frequencies"]["inserted"] += 1
                else:
                    cursor.execute("""
                        INSERT INTO frequencies (airport_ident, type, description, frequency_mhz, source, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        apt_ident,
                        row['type'],
                        row['description'],
                        float(row['frequency_mhz']) if row['frequency_mhz'] else None,
                        "OurAirports",
                        now
                    ))
                    report["frequencies"]["inserted"] += 1
        logger.info(f"Frequencies: {report['frequencies']['inserted']} inserted, {report['frequencies']['preserved']} preserved.")

    # 4. Update Metadata
    cursor.execute("SELECT count(*) FROM airports")
    report["final_counts"] = {
        "airports": cursor.fetchone()[0],
    }
    cursor.execute("SELECT count(*) FROM runways")
    report["final_counts"]["runways"] = cursor.fetchone()[0]
    cursor.execute("SELECT count(*) FROM frequencies")
    report["final_counts"]["frequencies"] = cursor.fetchone()[0]

    if not dry_run:
        conn.execute("INSERT OR REPLACE INTO schema_meta (key, value, updated_at) VALUES (?, ?, ?)", ("ref_data_source", "OurAirports", now))
        conn.execute("INSERT OR REPLACE INTO schema_meta (key, value, updated_at) VALUES (?, ?, ?)", ("ref_data_version", now.split('T')[0], now))
        conn.execute("INSERT OR REPLACE INTO schema_meta (key, value, updated_at) VALUES (?, ?, ?)", ("last_imported_at", now, now))
        conn.commit()
    
    conn.close()
    
    if report_path:
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, 'w') as rf:
            json.dump(report, rf, indent=2)
        logger.info(f"Report saved to {report_path}")

    logger.info("Import " + ("(DRY RUN) " if dry_run else "") + "complete.")
    return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import airport data from OurAirports CSV files.")
    parser.add_argument("--db", default="/var/lib/airfieldops/airfieldops.sqlite", help="Path to SQLite database")
    parser.add_argument("--source", default="data_sources/ourairports", help="Directory containing CSV files")
    parser.add_argument("--country", action='append', help="Country codes to import (repeat for multiple)")
    parser.add_argument("--download", action='store_true', help="Download CSV files from OurAirports")
    parser.add_argument("--dry-run", action='store_true', help="Simulate import without modifying database")
    parser.add_argument("--report", help="Path to save import report JSON")
    
    args = parser.parse_args()
    
    countries = args.country if args.country else DEFAULT_COUNTRIES
    
    db_path = args.db
    if not os.path.isabs(db_path):
        db_path = os.path.abspath(db_path)

    import_ourairports(db_path, args.source, countries, DEFAULT_AIRPORT_TYPES, 
                        download=args.download, dry_run=args.dry_run, report_path=args.report)
