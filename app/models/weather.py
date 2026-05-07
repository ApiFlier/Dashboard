from pydantic import BaseModel
from typing import Optional, Dict, Any, List

class NormalizedWind(BaseModel):
    direction_deg: Optional[int] = None
    speed_kt: Optional[float] = None
    gust_kt: Optional[float] = None
    variable: bool = False

class NormalizedMetar(BaseModel):
    raw: str
    observed_at: str
    flight_category: str
    wind: NormalizedWind
    visibility_sm: Optional[float] = None
    ceiling_ft_agl: Optional[float] = None
    temperature_c: Optional[float] = None
    dewpoint_c: Optional[float] = None
    altimeter_in_hg: Optional[float] = None

class NormalizedTaf(BaseModel):
    raw: str
    issued_at: str
    valid_from: str
    valid_to: str
    forecast_periods: List[Dict[str, Any]] = []

class NormalizedWeather(BaseModel):
    airport: str
    generated_at: str
    metar: Optional[NormalizedMetar] = None
    taf: Optional[NormalizedTaf] = None
    source: str = "AviationWeather.gov"
    warnings: List[str] = []
