import httpx
import logging
from typing import Dict, Any, List
from app.core.config import settings
from app.core.cache import cache

logger = logging.getLogger(__name__)

class NWSClient:
    BASE_URL = "https://api.weather.gov"
    ALERTS_TTL = 600 # 10 minutes

    async def get_alerts_by_point(self, lat: float, lon: float) -> List[Dict[str, Any]]:
        # Round lat/lon to ~1 mile precision for better cache hits (0.01 deg is roughly 0.6nm)
        cache_key = f"nws:alerts:{round(lat,2)}:{round(lon,2)}"
        
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return cached_data

        try:
            async with httpx.AsyncClient(timeout=settings.TIMEOUT_SEC) as client:
                headers = {"User-Agent": settings.USER_AGENT}
                response = await client.get(f"{self.BASE_URL}/alerts/active", params={"point": f"{lat},{lon}"}, headers=headers)
                response.raise_for_status()
                data = response.json()
                alerts = data.get("features", [])
                
                cache.set(cache_key, alerts, ttl_seconds=self.ALERTS_TTL)
                return alerts
        except Exception as e:
            logger.warning(f"Live NWS fetch failed for {lat},{lon}: {e}")
            stale_data, is_stale = cache.get_stale_allowed(cache_key)
            if stale_data is not None:
                return stale_data
            return []

nws_client = NWSClient()
