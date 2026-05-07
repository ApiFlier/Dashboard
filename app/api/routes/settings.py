import os
import sqlite3
import logging
from fastapi import APIRouter
from app.services.runtime_db import get_connection

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/settings/defaults")
async def defaults():
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = 'default_airport'")
            row = cursor.fetchone()
            if row:
                return {"default_airport": row["value"]}
    except sqlite3.OperationalError:
        logger.warning("SQLite DB unavailable for settings, falling back to env")
    
    return {"default_airport": os.environ.get("DEFAULT_AIRPORT", "KAGC")}
