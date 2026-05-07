import sqlite3
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from app.services.runtime_db import get_connection
from app.models.common import UserSettings
from app.services.airport_data import get_airport_directory
from app.api.auth import verify_admin_token

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/settings", response_model=UserSettings)
async def get_settings():
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value, updated_at FROM settings")
            rows = cursor.fetchall()
            
            data = {}
            last_updated = None
            for row in rows:
                key = row["key"]
                val = row["value"]
                # Type conversion
                if key in ["alternate_radius_nm", "refresh_interval_seconds"]:
                    val = int(val)
                elif key in ["monitor_mode", "show_raw_weather_default"]:
                    val = val == "1"
                
                data[key] = val
                if not last_updated or row["updated_at"] > last_updated:
                    last_updated = row["updated_at"]
            
            if not data:
                return UserSettings(source="default")
                
            return UserSettings(**data, updated_at=last_updated)
    except Exception as e:
        logger.error(f"Error fetching settings: {e}")
        return UserSettings(source="fallback")

@router.put("/settings", response_model=UserSettings, dependencies=[Depends(verify_admin_token)])
async def update_settings(new_settings: UserSettings):
    # 1. Validate airport if provided
    if new_settings.default_airport:
        if not get_airport_directory(new_settings.default_airport):
            raise HTTPException(status_code=400, detail=f"Airport {new_settings.default_airport} not found in reference data.")

    now = datetime.now(timezone.utc).isoformat()
    
    # 2. Map model to key/value pairs
    updates = {
        "default_airport": new_settings.default_airport,
        "alternate_radius_nm": str(new_settings.alternate_radius_nm),
        "refresh_interval_seconds": str(new_settings.refresh_interval_seconds),
        "theme_mode": new_settings.theme_mode,
        "monitor_mode": "1" if new_settings.monitor_mode else "0",
        "show_raw_weather_default": "1" if new_settings.show_raw_weather_default else "0",
        "accent_color": new_settings.accent_color
    }

    try:
        with get_connection() as conn:
            for key, val in updates.items():
                conn.execute(
                    "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
                    (key, val, now)
                )
            conn.commit()
        return await get_settings()
    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to save settings.")

import os
...
@router.get("/settings/defaults")
async def legacy_defaults():
    s = await get_settings()
    return {"default_airport": s.default_airport or os.environ.get("DEFAULT_AIRPORT", "KAGC")}
