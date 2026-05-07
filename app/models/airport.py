from pydantic import BaseModel
from typing import List

class Frequency(BaseModel):
    type: str
    frequency: str

class AirportDirectory(BaseModel):
    icao: str
    name: str
    lat: float
    lon: float
    elevation_ft: int
    frequencies: List[Frequency]
