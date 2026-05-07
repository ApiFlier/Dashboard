import asyncio
import math
from typing import List
from haversine import haversine, Unit
from .airport_data import get_all_airports
from .aviationweather_client import aw_client
from .weather_normalization import normalize_visibility, get_ceiling, derive_flight_category
from app.models.alternate import AlternateAirport

def calculate_bearing(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (math.sin(lat1) * math.cos(lat2) * math.cos(dlon))
    initial_bearing = math.atan2(x, y)
    initial_bearing = math.degrees(initial_bearing)
    compass_bearing = (initial_bearing + 360) % 360
    return round(compass_bearing, 1)

async def fetch_candidate_weather(c: dict):
    try:
        metars = await aw_client.get_metar(c["icao"])
        if metars and len(metars) > 0:
            m = metars[0]
            
            vis = normalize_visibility(m.get("visib"))
            ceil = get_ceiling(m.get("clouds"))
            flt_cat = m.get("fltcat")
            
            if not flt_cat or flt_cat == "UNKNOWN":
                if vis is not None or ceil is not None:
                    flt_cat = derive_flight_category(ceil, vis)
                else:
                    flt_cat = "Rules unavailable"
            
            c["flight_category"] = flt_cat
            c["ceiling_ft_agl"] = ceil
            c["visibility_sm"] = vis
            
            wdir = m.get("wdir")
            if wdir == "VRB":
                wdir_val = "VRB"
            elif isinstance(wdir, (int, float)):
                wdir_val = str(int(wdir))
            else:
                wdir_val = str(wdir) if wdir else ""

            wspd = m.get("wspd")
            wgst = m.get("wgst")
            
            if wspd is not None:
                wind_str = f"{wdir_val}@{wspd}"
                if wgst:
                    wind_str += f"G{wgst}"
                c["wind"] = wind_str
        else:
            c["warnings"].append("METAR unavailable")
    except Exception as e:
        c["warnings"].append(f"Weather fetch failed: {str(e)}")

async def find_alternates(origin_lat: float, origin_lon: float, origin_icao: str, radius_nm: float = 75) -> List[AlternateAirport]:
    all_airports = get_all_airports()
    candidates = []
    
    for a in all_airports:
        if a["icao"] == origin_icao:
            continue
        dist = haversine((origin_lat, origin_lon), (a["lat"], a["lon"]), unit=Unit.NAUTICAL_MILES)
        if dist <= radius_nm:
            bearing = calculate_bearing(origin_lat, origin_lon, a["lat"], a["lon"])
            candidates.append({
                "icao": a["icao"],
                "name": a["name"],
                "distance_nm": round(dist, 1),
                "bearing_deg": bearing,
                "flight_category": "UNKNOWN",
                "ceiling_ft_agl": None,
                "visibility_sm": None,
                "wind": None,
                "warnings": []
            })
            
    # Fetch METARs concurrently
    if candidates:
        await asyncio.gather(*(fetch_candidate_weather(c) for c in candidates))

    # Score: Flight rules (VFR>MVFR>IFR>LIFR), then distance
    rules_score = {
        "VFR": 100, 
        "MVFR": 75, 
        "IFR": 50, 
        "LIFR": 25, 
        "UNKNOWN": 0, 
        "Rules unavailable": 0,
        "Weather fetch failed": 0,
        "METAR unavailable": 0
    }
    
    final_alts = []
    for c in candidates:
        base_score = rules_score.get(c["flight_category"], 0)
        dist_penalty = c["distance_nm"] * 0.5  # small distance penalty
        score = int(base_score - dist_penalty)
        
        if c["flight_category"] in ["UNKNOWN", "Rules unavailable", "METAR unavailable"]:
            reason = f"{c['flight_category']} ({c['distance_nm']} nm)."
        else:
            reason = f"{c['flight_category']} conditions ({c['distance_nm']} nm)."
            
        final_alts.append(AlternateAirport(
            icao=c["icao"],
            name=c["name"],
            distance_nm=c["distance_nm"],
            bearing_deg=c["bearing_deg"],
            flight_category=c["flight_category"],
            ceiling_ft_agl=c["ceiling_ft_agl"],
            visibility_sm=c["visibility_sm"],
            wind=c["wind"],
            score=score,
            rank_reason=reason,
            warnings=c["warnings"]
        ))
            
    final_alts.sort(key=lambda x: x.score, reverse=True)
    return final_alts
