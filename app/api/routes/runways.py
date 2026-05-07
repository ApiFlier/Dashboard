import datetime
from fastapi import APIRouter, HTTPException
from app.services.airport_data import get_airport_runways
from app.services.aviationweather_client import aw_client
from app.services.runway_math import calculate_wind_components
from app.models.runway import RunwayAnalysis, RunwayConditions, RunwayRiskFlags, FavoredRunway

router = APIRouter()

@router.get("/airport/{airport}/runways", response_model=RunwayAnalysis)
async def runways(airport: str):
    airport = airport.upper()
    runways_raw = get_airport_runways(airport)
    if not runways_raw:
        raise HTTPException(status_code=404, detail="Runway data not found for airport")
        
    metar_data = await aw_client.get_metar(airport)
    metar = metar_data[0] if metar_data and len(metar_data) > 0 else None
    
    wind_dir = None
    wind_spd = None
    wind_gust = None
    variable_wind = False
    
    warnings = []
    if metar:
        wdir_val = metar.get("wdir")
        if wdir_val == "VRB":
            variable_wind = True
            wind_dir = None
            wind_spd = metar.get("wspd")
        elif isinstance(wdir_val, (int, float)):
            wind_dir = int(wdir_val)
            wind_spd = metar.get("wspd")
        wind_gust = metar.get("wgst")
    else:
        warnings.append("No METAR data available. Wind analysis skipped.")

    results = []
    favored_candidates = []
    
    for r in runways_raw:
        hw, tw, cw, cwg = calculate_wind_components(r["heading"], wind_dir, wind_spd, wind_gust)
        
        flags = RunwayRiskFlags(
            calm_wind=(wind_spd == 0),
            variable_wind=variable_wind,
            missing_wind=(not metar or (wind_dir is None and not variable_wind and wind_spd != 0)),
        )
        
        if wind_spd and wind_spd > 0:
            if wind_gust and wind_gust - wind_spd >= 10:
                flags.gusty = True
            if cw is not None:
                if cw >= 15:
                    flags.strong_crosswind = True
                elif cw >= 10:
                    flags.crosswind = True
            if tw is not None:
                if tw >= 8:
                    flags.strong_tailwind = True
                elif tw >= 3:
                    flags.tailwind = True

        cond = RunwayConditions(
            id=r["id"],
            heading=r["heading"],
            length_ft=r["length_ft"],
            width_ft=r["width_ft"],
            le_latitude_deg=r.get("le_latitude_deg"),
            le_longitude_deg=r.get("le_longitude_deg"),
            he_latitude_deg=r.get("he_latitude_deg"),
            he_longitude_deg=r.get("he_longitude_deg"),
            headwind_kt=hw,
            tailwind_kt=tw,
            crosswind_kt=cw,
            crosswind_gust_kt=cwg,
            risk_flags=flags
        )
        results.append(cond)
        
        if hw is not None and tw == 0.0:
            favored_candidates.append(cond)

    favored = FavoredRunway(reason="Unknown")
    
    if not metar:
        favored.reason = "Wind data unavailable."
    elif wind_spd == 0:
        favored.reason = "Winds calm. Any runway may be used."
    elif variable_wind:
        favored.reason = "Winds variable. Choose based on runway length or local procedures."
    elif favored_candidates:
        # Pick the one with the strongest headwind component, tie-break by length
        best = sorted(favored_candidates, key=lambda x: (x.headwind_kt or 0, x.length_ft or 0), reverse=True)[0]
        favored.id = best.id
        favored.reason = f"Best headwind component ({best.headwind_kt} kt)."
    else:
        favored.reason = "No clear favored runway without a tailwind."

    return RunwayAnalysis(
        airport=airport,
        generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        wind_direction_deg=wind_dir,
        favored_runway=favored,
        runways=results,
        warnings=warnings
    )
