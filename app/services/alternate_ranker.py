import asyncio
import math
from typing import List
from haversine import haversine, Unit
from .airport_data import get_all_airports, get_nearby_candidates_from_db, get_airport_runways
from .aviationweather_client import aw_client
from .weather_normalization import normalize_visibility, get_ceiling, derive_flight_category
from app.models.alternate import AlternateAirport, AlternatesResponse, ExcludedSummary

def calculate_bearing(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (math.sin(lat1) * math.cos(lat2) * math.cos(dlon))
    initial_bearing = math.atan2(x, y)
    initial_bearing = math.degrees(initial_bearing)
    compass_bearing = (initial_bearing + 360) % 360
    return round(compass_bearing, 1)

async def find_alternates(origin_lat: float, origin_lon: float, origin_icao: str, radius_nm: float = 75, limit: int = 10, include_non_reporting: bool = False) -> AlternatesResponse:
    # 1. Get initial candidates
    # get_nearby_candidates_from_db already filters by supported types and radius
    raw_candidates = get_nearby_candidates_from_db(origin_lat, origin_lon, radius_nm, exclude_icao=origin_icao)
    
    # Filter out closed or unsupported types strictly
    # Supported types: large_airport, medium_airport, small_airport
    # Exclude: closed, heliport, balloonport, seaplane_base, etc. (mostly handled by get_nearby_candidates_from_db)
    
    excluded = ExcludedSummary()
    candidates = []
    
    # 2. Basic mapping and exclusion
    for c in raw_candidates:
        # Extra safety check on type
        if c["type"] not in ["large_airport", "medium_airport", "small_airport"]:
            excluded.closed_or_unsupported += 1
            continue
            
        candidates.append({
            "icao": c["ident"],
            "name": c["name"],
            "type": c["type"],
            "distance_nm": round(c["distance_nm"], 1),
            "bearing_deg": calculate_bearing(origin_lat, origin_lon, c["lat"], c["lon"]),
            "flight_category": "UNKNOWN",
            "ceiling_ft_agl": None,
            "visibility_sm": None,
            "wind": None,
            "warnings": []
        })

    # Prefetch Cap: Limit to top 50 candidates for METAR batch lookup to avoid 400 errors and lag
    # raw_candidates is already sorted by type then distance
    candidates_to_fetch = candidates[:50]
    skipped_due_to_cap = len(candidates) - len(candidates_to_fetch)
    # We don't necessarily count these as 'excluded' in the summary yet, but they won't have weather.

    # 3. Fetch METARs in batch
    if candidates_to_fetch:
        icaos = [c["icao"] for c in candidates_to_fetch]
        try:
            metars = await aw_client.get_metars(icaos)
            metar_map = { (m.get("icao") or m.get("icaoId")): m for m in metars if (m.get("icao") or m.get("icaoId")) }
            
            for c in candidates_to_fetch:
                m = metar_map.get(c["icao"])
                if m:
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
                    wdir_val = "VRB" if wdir == "VRB" else str(int(wdir)) if isinstance(wdir, (int, float)) else str(wdir) if wdir else ""
                    wspd = m.get("wspd")
                    wgst = m.get("wgst")
                    
                    if wspd is not None:
                        wind_str = f"{wdir_val}@{wspd}"
                        if wgst:
                            wind_str += f"G{wgst}"
                        c["wind"] = wind_str
                else:
                    excluded.no_weather += 1
                    c["warnings"].append("METAR unavailable")
                    
        except Exception as e:
            for c in candidates_to_fetch:
                c["warnings"].append(f"Batch weather fetch failed: {str(e)}")

    # Update excluded count for those not even attempted
    excluded.no_weather += skipped_due_to_cap

    # 4. Scoring (Strongly reward reporting fields)
    rules_score = {
        "VFR": 100, "MVFR": 80, "IFR": 40, "LIFR": 10, 
        "UNKNOWN": -100, "Rules unavailable": -100, "METAR unavailable": -100
    }
    type_bonus = {
        "large_airport": 30,
        "medium_airport": 15,
        "small_airport": 0
    }
    
    scored_alts = []
    # We consider all candidates (including those skipped by METAR cap)
    for c in candidates:
        base = rules_score.get(c["flight_category"], -100)
        bonus = type_bonus.get(c["type"], 0)
        dist_penalty = c["distance_nm"] * 0.8
        
        score = int(base + bonus - dist_penalty)
        
        # Reason
        if c["flight_category"] in ["UNKNOWN", "Rules unavailable", "METAR unavailable"]:
            reason = f"Weather unavailable ({c['distance_nm']} nm)."
        else:
            reason = f"{c['flight_category']} conditions ({c['distance_nm']} nm)."
            
        scored_alts.append(AlternateAirport(
            icao=c["icao"],
            name=c["name"],
            type=c["type"],
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
            
    # Sort
    scored_alts.sort(key=lambda x: x.score, reverse=True)
    
    # 5. Result Selection (Reporting first, then non-reporting if requested)
    reporting = [a for a in scored_alts if a.flight_category not in ["UNKNOWN", "Rules unavailable", "METAR unavailable"]]
    non_reporting = [a for a in scored_alts if a.flight_category in ["UNKNOWN", "Rules unavailable", "METAR unavailable"]]
    
    # Hard Limit: 25
    limit = min(max(1, limit), 25)
    
    final_list = reporting[:limit]
    if include_non_reporting and len(final_list) < limit:
        needed = limit - len(final_list)
        final_list.extend(non_reporting[:needed])
        
    return AlternatesResponse(
        source_airport=origin_icao,
        radius_nm=radius_nm,
        limit=limit,
        candidates_considered=len(raw_candidates),
        reporting_candidates_count=len(reporting),
        alternates=final_list,
        excluded_summary=excluded
    )
