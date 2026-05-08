import datetime
import logging
import asyncio
from typing import Optional, List, Dict, Any
from app.services.airport_data import get_airport_directory, get_airport_runways
from app.services.aviationweather_client import aw_client
from app.services.hazard_service import get_hazards_for_airport
from app.api.routes.weather import weather as get_weather_data
from app.api.routes.runways import runways as get_runway_data
from app.models.airport import AirportSummary

logger = logging.getLogger(__name__)

async def get_airport_summary(icao: str) -> AirportSummary:
    icao = icao.upper()
    directory = get_airport_directory(icao)
    if not directory:
        raise ValueError(f"Airport {icao} not found")

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    # 1. Weather (Lightweight call to route logic)
    weather = await get_weather_data(icao)
    metar = weather.metar
    
    # 2. Runway Analysis (Lightweight call to route logic)
    # This recalculates wind components based on the metar fetched above
    runways = await get_runway_data(icao)
    
    # 3. Hazard Risk (Lightweight call to hazard service)
    hazards = await get_hazards_for_airport(icao, directory["lat"], directory["lon"])
    
    # Determine flight category and nearby status
    flt_cat = "UNKNOWN"
    field_weather_available = False
    nearby_weather_used = False
    wind_summary = "N/A"
    
    if metar:
        flt_cat = metar.flight_category
        field_weather_available = True
        # Format wind: e.g. "230@12KT"
        wdir = metar.wind.direction_deg
        wspd = metar.wind.speed_kt
        wgst = metar.wind.gust_kt
        wdir_str = "VRB" if metar.wind.variable else str(wdir).zfill(3) if wdir is not None else "???"
        wind_summary = f"{wdir_str}@{int(wspd)}KT" if wspd is not None else "N/A"
        if wgst:
            wind_summary += f" G{int(wgst)}KT"
    elif weather.nearby_weather_stations:
        nearby = weather.nearby_weather_stations[0]
        flt_cat = nearby.flight_category
        nearby_weather_used = True
        wind_summary = nearby.wind or "N/A"

    warnings = []
    warnings.extend(weather.warnings)
    warnings.extend(runways.warnings)
    warnings.extend(hazards.warnings)
    
    # Status labeling
    # We can infer status from weather.source or warnings
    weather_status = "available"
    if not field_weather_available:
        weather_status = "unavailable"
    if any("fetch failed" in w.lower() for w in weather.warnings):
        weather_status = "error"

    # Favored runway compacting for summary
    favored_end = getattr(runways.favored_runway, "id", None) if runways.favored_runway else None
    favored_reason = getattr(runways.favored_runway, "reason", "No runway data") if runways.favored_runway else "No runway data"
    
    if not field_weather_available and not nearby_weather_used:
        favored_reason = "No field wind"
    elif metar and metar.wind.speed_kt == 0:
        favored_reason = "Calm"
    elif not runways.runways:
        favored_reason = "No runway data"

    return AirportSummary(
        icao=icao,
        iata_code=directory.get("iata_code"),
        name=directory["name"],
        flight_category=flt_cat,
        field_weather_available=field_weather_available,
        weather_status=weather_status,
        nearby_weather_used=nearby_weather_used,
        wind_summary=wind_summary,
        favored_runway_end=favored_end,
        favored_runway_reason=favored_reason,
        hazard_risk=getattr(hazards, "risk_level", "unknown"),
        has_runways=len(get_airport_runways(icao)) > 0,
        has_frequencies=len(directory.get("frequencies", [])) > 0,
        generated_at=now,
        warnings=list(set(warnings)) # unique warnings
    )

async def get_batch_airport_summaries(idents: List[str]) -> List[Dict[str, Any]]:
    # Limit to 12
    idents = list(set([i.upper() for i in idents]))[:12]
    
    tasks = [get_airport_summary(ident) for ident in idents]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    summaries = []
    for i, res in enumerate(results):
        ident = idents[i]
        if isinstance(res, Exception):
            logger.error(f"Failed to get summary for {ident}: {res}")
            summaries.append({"icao": ident, "error": str(res)})
        else:
            summaries.append(res.model_dump())
            
    return summaries
