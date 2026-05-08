import math
from typing import Optional, Tuple

def calculate_wind_components(runway_heading_deg: float, wind_direction_deg: Optional[int], wind_speed_kt: Optional[float], gust_kt: Optional[float] = None) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    if wind_direction_deg is None or wind_speed_kt is None:
        return None, None, None, None
        
    if wind_speed_kt == 0:
        return 0.0, 0.0, 0.0, None

    angle_rad = math.radians(wind_direction_deg - runway_heading_deg)
    headwind_raw = math.cos(angle_rad) * wind_speed_kt
    crosswind_raw = math.sin(angle_rad) * wind_speed_kt

    headwind = headwind_raw if headwind_raw > 0 else 0.0
    tailwind = -headwind_raw if headwind_raw < 0 else 0.0
    crosswind = abs(crosswind_raw)

    crosswind_gust = None
    if gust_kt is not None and gust_kt > wind_speed_kt:
        crosswind_gust = abs(math.sin(angle_rad) * gust_kt)

    return round(headwind, 1), round(tailwind, 1), round(crosswind, 1), round(crosswind_gust, 1) if crosswind_gust is not None else None
