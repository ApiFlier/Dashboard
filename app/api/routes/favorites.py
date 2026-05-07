import logging
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from app.services.runtime_db import get_connection
from app.models.common import FavoriteAirport
from app.services.airport_data import get_airport_directory
from app.api.auth import verify_admin_token

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/favorites", response_model=List[FavoriteAirport])
async def get_favorites():
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ident, created_at FROM favorites ORDER BY ident ASC")
            rows = cursor.fetchall()
            return [FavoriteAirport(ident=row["ident"], created_at=row["created_at"]) for row in rows]
    except Exception as e:
        logger.error(f"Error fetching favorites: {e}")
        return []

@router.post("/favorites/{icao}", dependencies=[Depends(verify_admin_token)])
async def add_favorite(icao: str):
    icao = icao.upper()
    if not get_airport_directory(icao):
        raise HTTPException(status_code=404, detail="Airport not found")
        
    now = datetime.now(timezone.utc).isoformat()
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO favorites (ident, created_at) VALUES (?, ?)",
                (icao, now)
            )
            conn.commit()
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error adding favorite: {e}")
        raise HTTPException(status_code=500, detail="Failed to add favorite.")

@router.delete("/favorites/{icao}", dependencies=[Depends(verify_admin_token)])
async def delete_favorite(icao: str):
    try:
        with get_connection() as conn:
            conn.execute("DELETE FROM favorites WHERE ident = ?", (icao.upper(),))
            conn.commit()
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error deleting favorite: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove favorite.")
