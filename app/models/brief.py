from pydantic import BaseModel
from typing import Optional, List
from .weather import NormalizedWeather
from .runway import RunwayAnalysis
from .alternate import AlternateAirport
from .hazard import HazardSummary

class BriefCondition(BaseModel):
    flight_category: str
    weather_risk: str
    hazard_risk: str

class FavoredRunwayBrief(BaseModel):
    end: Optional[str] = None
    reason: str

class AirportBrief(BaseModel):
    airport: dict
    generated_at: str
    condition: BriefCondition
    favored_runway: FavoredRunwayBrief
    main_concerns: List[str]
    best_alternates: List[AlternateAirport]
    plain_english: List[str]
    warnings: List[str]
    disclaimer: str
