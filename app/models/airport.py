from pydantic import BaseModel
from typing import List, Optional

class Frequency(BaseModel):
    type: str
    frequency: str

class AirportDirectory(BaseModel):
    icao: str
    name: str
    lat: float
    lon: float
    elevation_ft: Optional[int] = None
    frequencies: List[Frequency]

class NearbyWeatherStation(BaseModel):
    ident: str
    name: str
    distance_nm: float
    bearing_deg: float
    flight_category: str
    wind: Optional[str] = None
    visibility_sm: Optional[float] = None
    ceiling_ft_agl: Optional[float] = None
    observed_at: str

class AirportCoverage(BaseModel):
    ident: str
    has_field_metar: bool
    metar_status: str # available, unavailable, fetch_failed, parse_failed
    has_taf: bool
    taf_status: str # available, unavailable, fetch_failed, parse_failed
    has_runways: bool
    has_frequencies: bool
    has_runway_geometry: bool
    nearby_weather_stations: List[NearbyWeatherStation] = []
    source: str = "OurAirports"
    warnings: List[str] = []

class AirportSummary(BaseModel):
    icao: str
    iata_code: Optional[str] = None
    name: str
    flight_category: str
    field_weather_available: bool
    weather_status: str # available, unavailable, etc.
    nearby_weather_used: bool
    wind_summary: Optional[str] = None
    favored_runway_end: Optional[str] = None
    favored_runway_reason: Optional[str] = None
    hazard_risk: str
    has_runways: bool
    has_frequencies: bool
    generated_at: str
    warnings: List[str] = []
