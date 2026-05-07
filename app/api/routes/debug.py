from fastapi import APIRouter
from app.services.aviationweather_client import aw_client
from app.api.routes.weather import parse_metar, parse_taf
from app.core.cache import cache

router = APIRouter()

@router.get("/weather/{airport}")
async def debug_weather(airport: str):
    airport = airport.upper()
    
    # Check cache status first
    cache_key_metar = f"aw:metar:{airport}"
    cache_key_taf = f"aw:taf:{airport}"
    
    metar_cached, metar_stale = cache.get_stale_allowed(cache_key_metar)
    taf_cached, taf_stale = cache.get_stale_allowed(cache_key_taf)
    
    # Get metadata from the cached object (PersistentCache injects it if it's a dict, 
    # but METAR is a list. Let's handle both.)
    def get_meta(obj):
        if isinstance(obj, dict):
            return obj.get("_cached_at")
        # If it's a list, we might have injected it into a wrapper if we wanted, 
        # but right now it's just the raw list.
        return "metadata unavailable for list payload"

    raw_metar = await aw_client.get_metar(airport)
    raw_taf = await aw_client.get_taf(airport)
    
    normalized_metar = None
    if raw_metar and len(raw_metar) > 0:
        try:
            normalized_metar = parse_metar(raw_metar[0])
        except Exception as e:
            normalized_metar = {"error": str(e)}
        
    normalized_taf = None
    if raw_taf and len(raw_taf) > 0:
        try:
            normalized_taf = parse_taf(raw_taf[0])
        except Exception as e:
            normalized_taf = {"error": str(e)}
        
    return {
        "airport": airport,
        "cache": {
            "metar": {
                "exists": metar_cached is not None, 
                "stale": metar_stale, 
                "fetched_at": get_meta(metar_cached) if metar_cached else None
            },
            "taf": {
                "exists": taf_cached is not None, 
                "stale": taf_stale, 
                "fetched_at": get_meta(taf_cached) if taf_cached else None
            }
        },
        "raw": {
            "metar": raw_metar[0] if raw_metar and len(raw_metar) > 0 else None,
            "taf": raw_taf[0] if raw_taf and len(raw_taf) > 0 else None
        },
        "normalized": {
            "metar": normalized_metar,
            "taf": normalized_taf
        }
    }
