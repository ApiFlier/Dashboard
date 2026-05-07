from pydantic import BaseModel
from typing import Optional

class AlternateAirport(BaseModel):
    icao: str
    name: str
    distance_nm: float
    bearing_deg: float
    flight_category: str
    ceiling_ft_agl: Optional[float] = None
    visibility_sm: Optional[float] = None
    wind: Optional[str] = None
    score: int
    rank_reason: str
    warnings: list[str] = []
