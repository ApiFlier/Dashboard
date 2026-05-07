import httpx
import logging
from typing import Dict, Any, List, Optional
from app.core.config import settings
from app.core.cache import cache

logger = logging.getLogger(__name__)

class AviationWeatherClient:
    BASE_URL = "https://aviationweather.gov/api/data"
    
    METAR_TTL = 300  # 5 minutes
    TAF_TTL = 600    # 10 minutes

    async def _get_json(self, endpoint: str, params: Dict[str, Any], ttl: int = 300) -> Any:
        cache_key = f"aw:{endpoint}:{params.get('ids','')}"
        
        # Check cache
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return cached_data

        try:
            async with httpx.AsyncClient(timeout=settings.TIMEOUT_SEC) as client:
                headers = {"User-Agent": settings.USER_AGENT}
                response = await client.get(f"{self.BASE_URL}/{endpoint}", params=params, headers=headers)
                if response.status_code == 204:
                    return []
                response.raise_for_status()
                data = response.json()
                
                # Cache fresh data
                cache.set(cache_key, data, ttl_seconds=ttl)
                return data
        except Exception as e:
            logger.warning(f"Live fetch failed for {endpoint}/{params.get('ids','')}: {e}")
            # Try stale cache
            stale_data, is_stale = cache.get_stale_allowed(cache_key)
            if stale_data is not None:
                logger.info(f"Returning stale cache for {endpoint}/{params.get('ids','')}")
                # We can't easily return warnings from here without changing return types, 
                # so we just return the data and let the higher layer handle it if possible.
                return stale_data
            raise e

    async def get_metar(self, icao: str) -> Optional[List[Dict[str, Any]]]:
        try:
            return await self._get_json("metar", {"ids": icao, "format": "json"}, ttl=self.METAR_TTL)
        except Exception:
            return []

    async def get_taf(self, icao: str) -> Optional[List[Dict[str, Any]]]:
        try:
            return await self._get_json("taf", {"ids": icao, "format": "json"}, ttl=self.TAF_TTL)
        except Exception:
            return []

    async def get_airport(self, icao: str) -> Optional[List[Dict[str, Any]]]:
        try:
            return await self._get_json("airport", {"ids": icao, "format": "json"})
        except Exception:
            return []

    async def get_station_info(self, icao: str) -> Optional[List[Dict[str, Any]]]:
        try:
            return await self._get_json("stationinfo", {"ids": icao, "format": "json"})
        except Exception:
            return []
            
    async def get_sigmet(self) -> Dict[str, Any]:
        try:
            return await self._get_json("airsigmet", {"format": "geojson"})
        except Exception:
            return {"features": []}

    async def get_gairmet(self) -> Dict[str, Any]:
        try:
            return await self._get_json("gairmet", {"format": "geojson"})
        except Exception:
            return {"features": []}
            
    async def get_cwa(self) -> Dict[str, Any]:
        try:
            return await self._get_json("cwa", {"format": "geojson"})
        except Exception:
            return {"features": []}

aw_client = AviationWeatherClient()
