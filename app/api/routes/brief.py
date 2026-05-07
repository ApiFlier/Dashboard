from fastapi import APIRouter
from app.services.brief_service import build_airport_brief
from app.models.brief import AirportBrief

router = APIRouter()

@router.get("/airport/{airport}/brief", response_model=AirportBrief)
async def brief(airport: str):
    return await build_airport_brief(airport)
