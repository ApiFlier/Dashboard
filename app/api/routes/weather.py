import datetime
import logging
from typing import Optional, Any
from fastapi import APIRouter
from app.services.aviationweather_client import aw_client
from app.models.weather import NormalizedWeather, NormalizedMetar, NormalizedTaf, NormalizedWind
from app.services.weather_normalization import (
    normalize_timestamp, 
    normalize_visibility, 
    normalize_altimeter, 
    get_ceiling,
    derive_flight_category
)

router = APIRouter()
logger = logging.getLogger(__name__)

def parse_metar(raw_metar: dict) -> NormalizedMetar:
    wdir = raw_metar.get("wdir")
    
    # Handle wdir as int, float, or special string "VRB"
    direction_deg = None
    if isinstance(wdir, (int, float)):
        direction_deg = int(wdir)
    elif isinstance(wdir, str) and wdir.isdigit():
        direction_deg = int(wdir)
        
    wind = NormalizedWind(
        direction_deg=direction_deg,
        speed_kt=float(raw_metar.get("wspd")) if raw_metar.get("wspd") is not None else None,
        gust_kt=float(raw_metar.get("wgst")) if raw_metar.get("wgst") is not None else None,
        variable=wdir == "VRB"
    )
    
    # Prefer reportTime, then obsTime
    observed_at = raw_metar.get("reportTime") or raw_metar.get("obsTime")
    
    vis = normalize_visibility(raw_metar.get("visib"))
    ceil = get_ceiling(raw_metar.get("clouds"))
    flt_cat = raw_metar.get("fltcat")
    
    if not flt_cat or flt_cat == "UNKNOWN":
        if vis is not None or ceil is not None:
            flt_cat = derive_flight_category(ceil, vis)
        else:
            flt_cat = "Rules unavailable"
            
    return NormalizedMetar(
        raw=raw_metar.get("rawOb", ""),
        observed_at=normalize_timestamp(observed_at) or "",
        flight_category=flt_cat,
        wind=wind,
        visibility_sm=vis,
        ceiling_ft_agl=ceil,
        temperature_c=float(raw_metar.get("temp")) if raw_metar.get("temp") is not None else None,
        dewpoint_c=float(raw_metar.get("dewp")) if raw_metar.get("dewp") is not None else None,
        altimeter_in_hg=normalize_altimeter(raw_metar.get("altim"))
    )

def parse_taf(raw_taf: dict) -> NormalizedTaf:
    issued_at = raw_taf.get("issueTime") or raw_taf.get("bulletinTime")
    
    forecast_periods = []
    for f in raw_taf.get("fcsts", []):
        forecast_periods.append({
            "fcst_from": normalize_timestamp(f.get("validTimeFrom")),
            "fcst_to": normalize_timestamp(f.get("validTimeTo")),
            "rawFcst": f.get("rawFcst"),
            "visibility_sm": normalize_visibility(f.get("visib")),
            "ceiling_ft_agl": get_ceiling(f.get("clouds"))
        })

    return NormalizedTaf(
        raw=raw_taf.get("rawTAF", ""),
        issued_at=normalize_timestamp(issued_at) or "",
        valid_from=normalize_timestamp(raw_taf.get("validTimeFrom")) or "",
        valid_to=normalize_timestamp(raw_taf.get("validTimeTo")) or "",
        forecast_periods=forecast_periods
    )

from app.services.airport_data import get_airport_directory
from app.services.coverage_service import find_nearest_reporting_stations

@router.get("/airport/{airport}/weather", response_model=NormalizedWeather)
async def weather(airport: str):
    airport = airport.upper()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    warnings = []
    
    try:
        metar_data = await aw_client.get_metar(airport)
    except Exception as e:
        logger.error(f"Failed to fetch METAR for {airport}: {e}")
        metar_data = []
        warnings.append(f"Weather fetch failed: {str(e)}")

    try:
        taf_data = await aw_client.get_taf(airport)
    except Exception as e:
        logger.error(f"Failed to fetch TAF for {airport}: {e}")
        taf_data = []
        warnings.append(f"Forecast fetch failed: {str(e)}")
    
    metar = None
    if metar_data and len(metar_data) > 0:
        try:
            metar = parse_metar(metar_data[0])
        except Exception as e:
            logger.error(f"Failed to parse METAR for {airport}: {e}")
            warnings.append(f"METAR parsing failed: {str(e)}")
    else:
        if not any("Weather fetch failed" in w for w in warnings):
            warnings.append("METAR unavailable")
        
    taf = None
    if taf_data and len(taf_data) > 0:
        try:
            taf = parse_taf(taf_data[0])
        except Exception as e:
            logger.error(f"Failed to parse TAF for {airport}: {e}")
            warnings.append(f"TAF parsing failed: {str(e)}")
    else:
        if not any("Forecast fetch failed" in w for w in warnings):
            warnings.append("TAF unavailable")

    nearby_stations = []
    if metar is None:
        apt = get_airport_directory(airport)
        if apt:
            nearby_stations = await find_nearest_reporting_stations(apt["lat"], apt["lon"], airport)
    
    return NormalizedWeather(
        airport=airport,
        generated_at=now,
        metar=metar,
        taf=taf,
        nearby_weather_stations=nearby_stations,
        warnings=warnings
    )
