import logging
import asyncio
import math
from typing import List, Optional, Dict, Any
from haversine import haversine, Unit
from app.services.airport_data import get_airport_directory, get_airport_runways, get_nearby_candidates_from_db
from app.services.aviationweather_client import aw_client
from app.services.weather_normalization import normalize_visibility, get_ceiling, derive_flight_category, normalize_timestamp
from app.models.airport import AirportCoverage, NearbyWeatherStation

logger = logging.getLogger(__name__)

def calculate_bearing(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (math.sin(lat1) * math.cos(lat2) * math.cos(dlon))
    initial_bearing = math.atan2(x, y)
    initial_bearing = math.degrees(initial_bearing)
    compass_bearing = (initial_bearing + 360) % 360
    return round(compass_bearing, 1)

async def get_airport_coverage(icao: str) -> AirportCoverage:
    icao = icao.upper()
    apt = get_airport_directory(icao)
    if not apt:
        return AirportCoverage(
            ident=icao, 
            has_field_metar=False, 
            metar_status="unavailable", 
            has_taf=False, 
            taf_status="unavailable", 
            has_runways=False, 
            has_frequencies=False, 
            has_runway_geometry=False, 
            warnings=["Airport not found in reference database"]
        )

    # Check database coverage
    runways = get_airport_runways(icao)
    has_runways = len(runways) > 0
    has_frequencies = len(apt.get("frequencies", [])) > 0
    has_runway_geometry = any(r.get("le_latitude_deg") is not None for r in runways)

    # Check live weather
    has_field_metar = False
    metar_status = "unavailable"
    has_taf = False
    taf_status = "unavailable"
    warnings = []

    try:
        metar_data = await aw_client.get_metar(icao)
        if metar_data:
            has_field_metar = True
            metar_status = "available"
        else:
            metar_status = "unavailable"
    except Exception as e:
        metar_status = "fetch_failed"
        warnings.append(f"METAR fetch failed: {str(e)}")

    try:
        taf_data = await aw_client.get_taf(icao)
        if taf_data:
            has_taf = True
            taf_status = "available"
        else:
            taf_status = "unavailable"
    except Exception as e:
        taf_status = "fetch_failed"
        warnings.append(f"TAF fetch failed: {str(e)}")

    nearby_stations = []
    if not has_field_metar:
        nearby_stations = await find_nearest_reporting_stations(apt["lat"], apt["lon"], icao)

    return AirportCoverage(
        ident=icao,
        has_field_metar=has_field_metar,
        metar_status=metar_status,
        has_taf=has_taf,
        taf_status=taf_status,
        has_runways=has_runways,
        has_frequencies=has_frequencies,
        has_runway_geometry=has_runway_geometry,
        nearby_weather_stations=nearby_stations,
        warnings=warnings
    )

async def find_nearest_reporting_stations(lat: float, lon: float, exclude_icao: str, radius_nm: float = 75, limit: int = 3) -> List[NearbyWeatherStation]:
    # 1. Find candidate airports from DB
    candidates = get_nearby_candidates_from_db(lat, lon, radius_nm, exclude_icao)
    if not candidates:
        return []

    # 2. Fetch METARs for all candidates in one go (limit candidates to avoid huge fanout)
    # We take first 10 candidates to check for weather
    top_candidates = candidates[:10]
    candidate_icaos = [c["ident"] for c in top_candidates]
    metars = await aw_client.get_metars(candidate_icaos)
    
    # Map METARs by ident
    metar_map = {m["icao"]: m for m in metars}
    
    reporting_stations = []
    for c in top_candidates:
        m = metar_map.get(c["ident"])
        if not m:
            continue
            
        # Parse minimal info for NearbyWeatherStation
        vis = normalize_visibility(m.get("visib"))
        ceil = get_ceiling(m.get("clouds"))
        flt_cat = m.get("fltcat")
        if not flt_cat or flt_cat == "UNKNOWN":
            flt_cat = derive_flight_category(ceil, vis)

        wdir = m.get("wdir")
        wspd = m.get("wspd")
        wgst = m.get("wgst")
        wind_str = None
        if wspd is not None:
            wdir_label = "VRB" if wdir == "VRB" else str(int(wdir)) if wdir is not None else "???"
            wind_str = f"{wdir_label}@{int(wspd)}KT"
            if wgst:
                wind_str += f" G{int(wgst)}KT"

        observed_at = m.get("reportTime") or m.get("obsTime")

        reporting_stations.append(NearbyWeatherStation(
            ident=c["ident"],
            name=c["name"],
            distance_nm=round(c["distance_nm"], 1),
            bearing_deg=round(calculate_bearing(lat, lon, c["lat"], c["lon"]), 0),
            flight_category=flt_cat,
            wind=wind_str,
            visibility_sm=vis,
            ceiling_ft_agl=ceil,
            observed_at=normalize_timestamp(observed_at) or ""
        ))
        
        if len(reporting_stations) >= limit:
            break
            
    return reporting_stations
