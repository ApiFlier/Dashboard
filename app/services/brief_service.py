import datetime
from .airport_data import get_airport_directory
from .aviationweather_client import aw_client
from .runway_math import calculate_wind_components
from .alternate_ranker import find_alternates
from .hazard_service import get_hazards_for_airport
from app.models.brief import AirportBrief, BriefCondition, FavoredRunwayBrief
from app.api.routes.weather import weather as get_weather
from app.api.routes.runways import runways as get_runways
from app.core.disclaimers import ADVISORY_DISCLAIMER
from fastapi import HTTPException

async def build_airport_brief(icao: str) -> AirportBrief:
    icao = icao.upper()
    directory = get_airport_directory(icao)
    if not directory:
        raise HTTPException(status_code=404, detail="Airport not found")
        
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    # 1. Weather
    weather_data = await get_weather(icao)
    
    # 2. Runways
    runway_data = await get_runways(icao)
    
    # 3. Alternates (limit to best 3)
    alts = await find_alternates(directory["lat"], directory["lon"], icao, limit=3)
    best_alts = alts.alternates if alts and alts.alternates else []
    
    # 4. Hazards
    hazards = await get_hazards_for_airport(icao, directory["lat"], directory["lon"])
    
    # Extract states for brief logic
    metar = weather_data.metar
    flt_cat = getattr(metar, "flight_category", "UNKNOWN") if metar else "UNKNOWN"
    
    # Build conditions
    weather_risk = "low"
    if flt_cat in ["IFR", "LIFR"]:
        weather_risk = "high"
    elif flt_cat == "MVFR":
        weather_risk = "moderate"
    elif flt_cat == "UNKNOWN":
        weather_risk = "unknown"
        
    condition = BriefCondition(
        flight_category=flt_cat,
        weather_risk=weather_risk,
        hazard_risk=getattr(hazards, "risk_level", "unknown")
    )
    
    favored = FavoredRunwayBrief(
        end=getattr(runway_data.favored_runway, "id", None) if runway_data and runway_data.favored_runway else None,
        reason=getattr(runway_data.favored_runway, "reason", "Favored runway unavailable because runway data is unavailable.") if runway_data and runway_data.favored_runway else "Favored runway unavailable because runway data is unavailable."
    )
    
    concerns = []
    plain_english = []
    warnings = []
    
    # Analyze and build plain English
    if weather_data and weather_data.warnings:
        warnings.extend(weather_data.warnings)
    if runway_data and runway_data.warnings:
        warnings.extend(runway_data.warnings)
    if hazards and hazards.warnings:
        warnings.extend(hazards.warnings)
    
    if not metar:
        if weather_data.nearby_weather_stations:
            nearby = weather_data.nearby_weather_stations[0]
            plain_english.append(f"No field METAR available. Nearby station {nearby.ident} ({nearby.distance_nm} nm) shows {nearby.flight_category} conditions.")
            # Adjust overall condition risk if field is missing but nearby is bad
            if nearby.flight_category in ["IFR", "LIFR"]:
                condition.weather_risk = "high"
            elif nearby.flight_category == "MVFR":
                condition.weather_risk = "moderate"
        else:
            plain_english.append("No field METAR available and no nearby reporting stations found.")
        
        plain_english.append("Runway and alternate guidance is limited without field weather.")
    else:
        # flight category
        if flt_cat == "VFR":
            plain_english.append("Current conditions are VFR.")
        elif flt_cat != "UNKNOWN":
            plain_english.append(f"Current conditions are {flt_cat}.")
        else:
            plain_english.append("Current flight category is unknown.")
            
        # wind
        wind = getattr(metar, "wind", None)
        if wind:
            if wind.speed_kt == 0:
                plain_english.append("Winds are currently calm.")
            elif wind.variable:
                plain_english.append(f"Winds are variable at {wind.speed_kt} kt.")
            elif wind.direction_deg is not None and wind.speed_kt is not None:
                if wind.gust_kt:
                    plain_english.append(f"Winds are gusty ({wind.direction_deg}@{wind.speed_kt}G{wind.gust_kt} kt).")
                    concerns.append("Gusty winds")
                else:
                    plain_english.append(f"Winds are {wind.direction_deg}@{wind.speed_kt} kt.")
            else:
                plain_english.append("Wind data is incomplete.")
        else:
            plain_english.append("Wind data is unavailable.")

        # runway 
        if favored.end:
            plain_english.append(f"Runway {favored.end} appears favored by the current wind.")
        else:
            plain_english.append("No clear favored runway based on current winds.")
            
        # crosswind checks
        if runway_data and runway_data.runways:
            for r in runway_data.runways:
                if r.id == favored.end:
                    if getattr(r.risk_flags, "strong_crosswind", False):
                        plain_english.append("Strong crosswind component present on favored runway.")
                        concerns.append("Strong crosswind")
                    elif getattr(r.risk_flags, "crosswind", False):
                        plain_english.append("Noticeable crosswind component present on favored runway.")
                    break

    # hazards
    h_risk = getattr(hazards, "risk_level", "unknown")
    if h_risk == "low":
        plain_english.append("No major public weather alerts near the field.")
    elif h_risk in ["moderate", "high"]:
        nws_count = hazards.counts.get('nws_alerts', 0) if hazards and hazards.counts else 0
        plain_english.append(f"There are active weather alerts ({nws_count} NWS alerts).")
        concerns.append("Active weather alerts")
        
    return AirportBrief(
        airport=directory,
        generated_at=now,
        condition=condition,
        favored_runway=favored,
        main_concerns=concerns,
        best_alternates=best_alts,
        plain_english=plain_english,
        warnings=warnings,
        disclaimer=ADVISORY_DISCLAIMER
    )
