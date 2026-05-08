from fastapi import APIRouter, HTTPException
from app.services.alternate_ranker import find_alternates
from app.services.airport_data import get_airport_directory
from app.models.alternate import AlternatesResponse

router = APIRouter()

@router.get("/airport/{airport}/alternates", response_model=AlternatesResponse)
async def alternates(
    airport: str, 
    radius_nm: float = 75.0, 
    limit: int = 10, 
    include_non_reporting: bool = False
):
    directory = get_airport_directory(airport)
    if not directory:
        raise HTTPException(status_code=404, detail="Airport not found")
        
    res = await find_alternates(
        directory["lat"], 
        directory["lon"], 
        airport, 
        radius_nm=radius_nm, 
        limit=limit, 
        include_non_reporting=include_non_reporting
    )
    return res
