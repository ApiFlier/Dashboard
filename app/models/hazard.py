from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from .convective import ConvectiveAwareness

class HazardSummary(BaseModel):
    airport: str
    generated_at: str
    risk_level: str # low, moderate, high, unknown
    counts: Dict[str, int]
    warnings: List[str] = []
    sources: List[str] = ["NWS", "AviationWeather"]
    nws_alerts: List[Dict[str, Any]] = []
    sigmets: List[Dict[str, Any]] = []
    gairmets: List[Dict[str, Any]] = []
    cwas: List[Dict[str, Any]] = []
    convective_awareness: Optional[ConvectiveAwareness] = None
