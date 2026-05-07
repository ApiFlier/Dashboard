import json
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any
import logging

from app.services.runtime_db import get_connection

logger = logging.getLogger(__name__)

def load_json(filename: str) -> Any:
    path = Path(__file__).parent.parent / "data" / filename
    with open(path, "r") as f:
        return json.load(f)

# Load fallback data
airports_data_fallback = load_json("airports_seed.json")
runways_data_fallback = load_json("runways_seed.json")
frequencies_data_fallback = load_json("frequencies_seed.json")

def get_airport_directory(icao: str) -> Optional[Dict[str, Any]]:
    icao = icao.upper()
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ident, name, lat, lon, elevation_ft FROM airports WHERE ident = ?", (icao,))
            apt = cursor.fetchone()
            if not apt:
                return None
            
            cursor.execute("SELECT type, frequency_mhz as frequency FROM frequencies WHERE airport_ident = ?", (icao,))
            freqs = [dict(row) for row in cursor.fetchall()]
            
            return {
                "icao": apt["ident"],
                "name": apt["name"],
                "lat": apt["lat"],
                "lon": apt["lon"],
                "elevation_ft": apt["elevation_ft"],
                "frequencies": freqs
            }
    except sqlite3.OperationalError:
        # Fallback to JSON
        logger.warning("SQLite DB unavailable, falling back to JSON for directory")
        airport = next((a for a in airports_data_fallback if a["icao"] == icao), None)
        if not airport:
            return None
        freqs = frequencies_data_fallback.get(icao, [])
        return {
            "icao": airport["icao"],
            "name": airport["name"],
            "lat": airport["lat"],
            "lon": airport["lon"],
            "elevation_ft": airport["elevation_ft"],
            "frequencies": freqs
        }

def search_airports(query: str):
    q = query.lower()
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ident as icao, name, lat, lon, elevation_ft FROM airports WHERE LOWER(ident) LIKE ? OR LOWER(name) LIKE ?", (f"%{q}%", f"%{q}%"))
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.OperationalError:
        logger.warning("SQLite DB unavailable, falling back to JSON for search")
        return [a for a in airports_data_fallback if q in a["icao"].lower() or q in a["name"].lower()]

def get_airport_runways(icao: str):
    icao = icao.upper()
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT surface_id as id, le_heading_deg as heading, length_ft, width_ft FROM runways WHERE airport_ident = ?", (icao,))
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.OperationalError:
        logger.warning("SQLite DB unavailable, falling back to JSON for runways")
        return runways_data_fallback.get(icao, [])

def get_all_airports():
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ident as icao, name, lat, lon, elevation_ft FROM airports")
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.OperationalError:
        logger.warning("SQLite DB unavailable, falling back to JSON for all airports")
        return airports_data_fallback
