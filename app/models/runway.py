from pydantic import BaseModel
from typing import Optional, List

class RunwayRiskFlags(BaseModel):
    calm_wind: bool = False
    variable_wind: bool = False
    missing_wind: bool = False
    gusty: bool = False
    crosswind: bool = False
    strong_crosswind: bool = False
    tailwind: bool = False
    strong_tailwind: bool = False

class RunwayConditions(BaseModel):
    id: str
    heading: int
    length_ft: int
    width_ft: int
    headwind_kt: Optional[float] = None
    tailwind_kt: Optional[float] = None
    crosswind_kt: Optional[float] = None
    crosswind_gust_kt: Optional[float] = None
    risk_flags: RunwayRiskFlags

class FavoredRunway(BaseModel):
    id: Optional[str] = None
    reason: str

class RunwayAnalysis(BaseModel):
    airport: str
    generated_at: str
    wind_direction_deg: Optional[int] = None
    favored_runway: FavoredRunway
    runways: List[RunwayConditions]
    warnings: List[str] = []
