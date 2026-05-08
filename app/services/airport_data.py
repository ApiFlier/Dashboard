import json
import sqlite3
import math
from pathlib import Path
from typing import Optional, Dict, Any, List
import logging
from haversine import haversine, Unit

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

def search_airports(query: str, limit: int = 10):
    q = query.strip().upper()
    if not q:
        return []
    
    # Cap limit
    limit = min(max(1, limit), 50)
    
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            sql = """
                SELECT 
                    ident, name, iata_code, type, city, state, country, lat, lon, elevation_ft,
                    CASE 
                        WHEN ident = ? THEN 1
                        WHEN iata_code = ? THEN 2
                        WHEN ident LIKE ? THEN 3
                        WHEN iata_code LIKE ? THEN 4
                        WHEN name LIKE ? THEN 5
                        WHEN name LIKE ? THEN 6
                        WHEN city LIKE ? THEN 7
                        ELSE 10
                    END as rank
                FROM airports 
                WHERE 
                    ident LIKE ? OR 
                    iata_code LIKE ? OR 
                    name LIKE ? OR 
                    city LIKE ?
                ORDER BY rank ASC, name ASC
                LIMIT ?
            """
            
            # Parameters for the query
            search_params = (
                q, # exact ident
                q, # exact iata
                f"{q}%", # ident starts with
                f"{q}%", # iata starts with
                f"{q}%", # name starts with
                f"%{q}%", # name contains
                f"%{q}%", # city contains
                f"%{q}%", # ident like
                f"%{q}%", # iata like
                f"%{q}%", # name like
                f"%{q}%", # city like
                limit
            )
            
            cursor.execute(sql, search_params)
            results = []
            for row in cursor.fetchall():
                res = dict(row)
                # Add a display label for the frontend
                iata = f" ({row['iata_code']})" if row['iata_code'] else ""
                loc = f" - {row['city']}, {row['state']}" if row['city'] and row['state'] else ""
                res["display_label"] = f"{row['ident']}{iata} {row['name']}{loc}"
                results.append(res)
            return results
            
    except sqlite3.OperationalError as e:
        logger.warning(f"SQLite DB search failed ({e}), falling back to minimal JSON search")
        # Simple fallback ranking
        q_lower = q.lower()
        matches = []
        for a in airports_data_fallback:
            rank = 10
            if a["icao"].upper() == q: rank = 1
            elif a["icao"].upper().startswith(q): rank = 3
            elif q_lower in a["name"].lower(): rank = 5
            
            if rank < 10:
                matches.append({**a, "rank": rank, "ident": a["icao"], "display_label": f"{a['icao']} {a['name']}"})
        
        matches.sort(key=lambda x: (x["rank"], x["name"]))
        return matches[:limit]

def get_airport_runways(icao: str):
    icao = icao.upper()
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    surface_id as id, 
                    le_heading_deg as heading, 
                    length_ft, 
                    width_ft,
                    le_latitude_deg,
                    le_longitude_deg,
                    he_latitude_deg,
                    he_longitude_deg
                FROM runways 
                WHERE airport_ident = ?
            """, (icao,))
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

def get_nearby_candidates_from_db(lat: float, lon: float, radius_nm: float, exclude_icao: Optional[str] = None) -> List[Dict[str, Any]]:
    # Roughly 1 degree lat = 60 nm
    lat_delta = radius_nm / 60.0
    # Longitude delta depends on latitude
    cos_lat = math.cos(math.radians(lat))
    if cos_lat == 0:
        lon_delta = 360.0 # At the poles
    else:
        lon_delta = radius_nm / (60.0 * cos_lat)
    
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            sql = """
                SELECT ident, name, lat, lon, type
                FROM airports
                WHERE lat BETWEEN ? AND ?
                  AND lon BETWEEN ? AND ?
                  AND type IN ('large_airport', 'medium_airport', 'small_airport')
            """
            params = [lat - lat_delta, lat + lat_delta, lon - lon_delta, lon + lon_delta]
            
            if exclude_icao:
                sql += " AND ident != ?"
                params.append(exclude_icao.upper())
                
            cursor.execute(sql, params)
            
            candidates = []
            for row in cursor.fetchall():
                dist = haversine((lat, lon), (row["lat"], row["lon"]), unit=Unit.NAUTICAL_MILES)
                if dist <= radius_nm:
                    candidates.append({
                        "ident": row["ident"],
                        "name": row["name"],
                        "lat": row["lat"],
                        "lon": row["lon"],
                        "type": row["type"],
                        "distance_nm": dist
                    })
            
            # Prioritize large then medium then small, then distance
            type_score = {"large_airport": 1, "medium_airport": 2, "small_airport": 3}
            candidates.sort(key=lambda x: (type_score.get(x["type"], 4), x["distance_nm"]))
            return candidates
    except Exception as e:
        logger.error(f"Error finding nearby airports: {e}")
        return []
