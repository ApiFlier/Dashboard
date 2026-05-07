import logging
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from app.services.runtime_db import get_connection
from app.models.common import RecentAirport
from app.services.airport_data import get_airport_directory
from app.api.auth import verify_admin_token

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/recent", response_model=List[RecentAirport])
async def get_recent():
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ident, last_viewed_at FROM recent_airports 
                ORDER BY last_viewed_at DESC LIMIT 10
            """)
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                icao = row["ident"]
                directory = get_airport_directory(icao)
                results.append(RecentAirport(
                    ident=icao,
                    last_viewed_at=row["last_viewed_at"],
                    name=directory["name"] if directory else "Unknown"
                ))
            return results
    except Exception as e:
        logger.error(f"Error fetching recent: {e}")
        return []

@router.post("/recent/{icao}", dependencies=[Depends(verify_admin_token)])
async def add_recent(icao: str):
    icao = icao.upper()
    if not get_airport_directory(icao):
        raise HTTPException(status_code=404, detail="Airport not found")
        
    now = datetime.now(timezone.utc).isoformat()
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO recent_airports (ident, last_viewed_at) VALUES (?, ?)",
                (icao, now)
            )
            conn.commit()
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error adding recent: {e}")
        raise HTTPException(status_code=500, detail="Failed to add recent airport.")

@router.delete("/recent/{icao}", dependencies=[Depends(verify_admin_token)])
async def delete_recent(icao: str):
    try:
        with get_connection() as conn:
            conn.execute("DELETE FROM recent_airports WHERE ident = ?", (icao.upper(),))
            conn.commit()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to delete recent airport.")

@router.delete("/recent", dependencies=[Depends(verify_admin_token)])
async def clear_recent():
    try:
        with get_connection() as conn:
            conn.execute("DELETE FROM recent_airports")
            conn.commit()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to clear recent history.")
