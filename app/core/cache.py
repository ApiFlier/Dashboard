import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Optional
from app.services.runtime_db import get_connection

logger = logging.getLogger(__name__)

class PersistentCache:
    def get(self, key: str) -> Optional[Any]:
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT payload_json, expires_at FROM api_cache WHERE cache_key = ?",
                    (key,)
                )
                row = cursor.fetchone()
                if not row:
                    return None

                payload_json, expires_at_str = row
                expires_at = datetime.fromisoformat(expires_at_str)

                if expires_at < datetime.now(timezone.utc):
                    # Stale but return it? The requirements say:
                    # "if live fetch fails but stale cache exists, return stale cache with warning"
                    # So we return the raw data and let the caller decide.
                    # For a simple 'get', we return only if fresh.
                    return None

                return json.loads(payload_json)
        except Exception as e:
            logger.error(f"Cache get error for {key}: {e}")
            return None

    def get_stale_allowed(self, key: str) -> tuple[Optional[Any], bool]:
        """Returns (data, is_stale)"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT payload_json, expires_at, fetched_at FROM api_cache WHERE cache_key = ?",
                    (key,)
                )
                row = cursor.fetchone()
                if not row:
                    return None, False

                payload_json, expires_at_str, fetched_at_str = row
                expires_at = datetime.fromisoformat(expires_at_str)
                is_stale = expires_at < datetime.now(timezone.utc)
                
                data = json.loads(payload_json)
                # Inject fetched_at so the caller knows how old it is
                if isinstance(data, dict):
                    data["_cached_at"] = fetched_at_str
                
                return data, is_stale
        except Exception as e:
            logger.error(f"Cache get_stale error for {key}: {e}")
            return None, False

    def set(self, key: str, value: Any, ttl_seconds: int = 300, source: str = "api"):
        try:
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(seconds=ttl_seconds)
            payload_json = json.dumps(value)

            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO api_cache 
                    (cache_key, source, payload_json, fetched_at, expires_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (key, source, payload_json, now.isoformat(), expires_at.isoformat())
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Cache set error for {key}: {e}")

cache = PersistentCache()
