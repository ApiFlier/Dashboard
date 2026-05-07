from typing import List
from fastapi import APIRouter, HTTPException
from app.services.alternate_ranker import find_alternates
from app.services.airport_data import get_airport_directory
from app.models.alternate import AlternateAirport

router = APIRouter()

@router.get("/airport/{airport}/alternates", response_model=List[AlternateAirport])
async def alternates(airport: str, radius_nm: float = 75.0):
    directory = get_airport_directory(airport)
    if not directory:
        raise HTTPException(status_code=404, detail="Airport not found")
        
    alts = await find_alternates(directory["lat"], directory["lon"], airport, radius_nm)
    return alts
