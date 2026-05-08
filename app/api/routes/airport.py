import asyncio
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from app.services.airport_data import search_airports, get_airport_directory
from app.api.routes import weather, runways, alternates, hazards, brief
from app.services.coverage_service import get_airport_coverage
from app.services.summary_service import get_airport_summary, get_batch_airport_summaries
from app.models.airport import AirportDirectory, AirportCoverage, AirportSummary

router = APIRouter()

@router.get("/airports/search")
async def search(q: str = "", limit: int = 10):
    return search_airports(q, limit)

@router.get("/airports/summary", response_model=List[dict])
async def batch_summary(idents: str = ""):
    if not idents:
        return []
    ident_list = [i.strip() for i in idents.split(",") if i.strip()]
    return await get_batch_airport_summaries(ident_list)

@router.get("/airport/{airport}/directory")
async def directory(airport: str):
    data = get_airport_directory(airport)
    if not data:
        raise HTTPException(status_code=404, detail="Airport not found")
    return data

@router.get("/airport/{airport}/coverage")
async def coverage(airport: str):
    return await get_airport_coverage(airport)

@router.get("/airport/{airport}/summary", response_model=AirportSummary)
async def summary(airport: str):
    try:
        return await get_airport_summary(airport)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/airport/{airport}/dashboard")
async def get_dashboard_data(airport: str):
    airport = airport.upper()
    directory_data = get_airport_directory(airport)
    if not directory_data:
        raise HTTPException(status_code=404, detail="Airport not found")

    # Fetch everything concurrently
    tasks = [
        weather.weather(airport),
        runways.runways(airport),
        alternates.alternates(airport),
        hazards.hazards(airport),
        brief.brief(airport),
        get_airport_coverage(airport)
    ]
    
    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            "airport": directory_data,
            "weather": results[0] if not isinstance(results[0], Exception) else {"error": str(results[0])},
            "runways": results[1] if not isinstance(results[1], Exception) else {"error": str(results[1])},
            "alternates": results[2] if not isinstance(results[2], Exception) else {"error": str(results[2])},
            "hazards": results[3] if not isinstance(results[3], Exception) else {"error": str(results[3])},
            "brief": results[4] if not isinstance(results[4], Exception) else {"error": str(results[4])},
            "coverage": results[5] if not isinstance(results[5], Exception) else {"error": str(results[5])}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to aggregate dashboard data: {str(e)}")
