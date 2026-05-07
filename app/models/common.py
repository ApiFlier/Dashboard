from pydantic import BaseModel, Field
from typing import Optional

class SourceMeta(BaseModel):
    source: str
    generated_at: str

class UserSettings(BaseModel):
    default_airport: str = ""
    alternate_radius_nm: int = Field(75, ge=10, le=250)
    refresh_interval_seconds: int = Field(300, ge=30)
    theme_mode: str = "system" # light, dark, system
    monitor_mode: bool = False
    show_raw_weather_default: bool = True
    accent_color: str = "blue"
    updated_at: Optional[str] = None
    source: str = "database"
    public_readonly_mode: bool = True

class FavoriteAirport(BaseModel):
    ident: str
    created_at: str

class RecentAirport(BaseModel):
    ident: str
    last_viewed_at: str
    name: Optional[str] = None
