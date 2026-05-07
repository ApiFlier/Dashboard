import asyncio
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from app.services.airport_data import search_airports, get_airport_directory
from app.api.routes import weather, runways, alternates, hazards, brief

router = APIRouter()

@router.get("/airports/search")
async def search(q: str = ""):
    return search_airports(q)

@router.get("/airport/{airport}/directory")
async def directory(airport: str):
    data = get_airport_directory(airport)
    if not data:
        raise HTTPException(status_code=404, detail="Airport not found")
    return data

@router.get("/airport/{airport}/dashboard")
async def get_dashboard_data(airport: str):
    airport = airport.upper()
    directory_data = get_airport_directory(airport)
    if not directory_data:
        raise HTTPException(status_code=404, detail="Airport not found")

    # Fetch everything concurrently
    # Note: we are calling the route functions directly as they contain the logic
    tasks = [
        weather.weather(airport),
        runways.runways(airport),
        alternates.alternates(airport),
        hazards.hazards(airport),
        brief.brief(airport)
    ]
    
    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            "airport": directory_data,
            "weather": results[0] if not isinstance(results[0], Exception) else {"error": str(results[0])},
            "runways": results[1] if not isinstance(results[1], Exception) else {"error": str(results[1])},
            "alternates": results[2] if not isinstance(results[2], Exception) else {"error": str(results[2])},
            "hazards": results[3] if not isinstance(results[3], Exception) else {"error": str(results[3])},
            "brief": results[4] if not isinstance(results[4], Exception) else {"error": str(results[4])}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to aggregate dashboard data: {str(e)}")
