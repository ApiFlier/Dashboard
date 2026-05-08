from pydantic import BaseModel
from typing import Optional, List

class ConvectiveAwareness(BaseModel):
    risk_level: str # low, moderate, high, unknown
    field_thunderstorm: bool = False
    vicinity_thunderstorm: bool = False
    taf_thunderstorm: bool = False
    convective_alert_active: bool = False
    summary: str
    indicators: List[str] = []
    source_notes: str = "Derived from METAR, TAF, and NWS Alerts."
    disclaimer: str = "Awareness only. This app does not provide certified lightning strike detection or ramp-closure decisions."
