from pydantic import BaseModel
from typing import Optional, List, Any

class AlternateAirport(BaseModel):
    icao: str
    name: str
    type: str
    distance_nm: float
    bearing_deg: float
    flight_category: str
    ceiling_ft_agl: Optional[float] = None
    visibility_sm: Optional[float] = None
    wind: Optional[str] = None
    score: int
    rank_reason: str
    warnings: List[str] = []

class ExcludedSummary(BaseModel):
    no_weather: int = 0
    no_runways: int = 0
    closed_or_unsupported: int = 0
    too_far: int = 0
    private_or_restricted: int = 0

class AlternatesResponse(BaseModel):
    source_airport: str
    radius_nm: float
    limit: int
    candidates_considered: int
    reporting_candidates_count: int
    alternates: List[AlternateAirport]
    excluded_summary: ExcludedSummary
