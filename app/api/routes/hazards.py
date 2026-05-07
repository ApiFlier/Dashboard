from fastapi import APIRouter, HTTPException
from app.services.hazard_service import get_hazards_for_airport
from app.services.airport_data import get_airport_directory
from app.models.hazard import HazardSummary

router = APIRouter()

@router.get("/airport/{airport}/hazards", response_model=HazardSummary)
async def hazards(airport: str, radius_nm: float = 75.0):
    airport = airport.upper()
    directory = get_airport_directory(airport)
    if not directory:
        raise HTTPException(status_code=404, detail="Airport not found")
        
    h = await get_hazards_for_airport(airport, directory["lat"], directory["lon"], radius_nm)
    return h
