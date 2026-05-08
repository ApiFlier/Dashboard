import pytest
from unittest.mock import patch, AsyncMock
from app.services.coverage_service import get_airport_coverage
from app.services.aviationweather_client import aw_client

@pytest.mark.asyncio
async def test_get_airport_coverage_with_metar():
    # Mock airport directory and weather
    with patch("app.services.coverage_service.get_airport_directory") as mock_dir, \
         patch("app.services.coverage_service.get_airport_runways") as mock_rwys, \
         patch.object(aw_client, "get_metar", new_callable=AsyncMock) as mock_metar, \
         patch.object(aw_client, "get_taf", new_callable=AsyncMock) as mock_taf:
        
        mock_dir.return_value = {
            "icao": "KAVP", "name": "Wilkes-Barre Scranton Intl",
            "lat": 41.338, "lon": -75.723, "frequencies": [{"type": "ATIS", "frequency": "121.8"}]
        }
        mock_rwys.return_value = [{"id": "04/22", "le_latitude_deg": 41.338}] # has geometry
        mock_metar.return_value = [{"icao": "KAVP", "rawOb": "KAVP ...", "fltcat": "VFR"}]
        mock_taf.return_value = [{"icao": "KAVP", "rawTAF": "KAVP ..."}]
        
        coverage = await get_airport_coverage("KAVP")
        
        assert coverage.ident == "KAVP"
        assert coverage.has_field_metar is True
        assert coverage.metar_status == "available"
        assert coverage.has_taf is True
        assert coverage.has_runways is True
        assert coverage.has_frequencies is True
        assert coverage.has_runway_geometry is True
        assert len(coverage.nearby_weather_stations) == 0

@pytest.mark.asyncio
async def test_get_airport_coverage_fallback():
    # Mock airport directory (no weather)
    with patch("app.services.coverage_service.get_airport_directory") as mock_dir, \
         patch("app.services.coverage_service.get_airport_runways") as mock_rwys, \
         patch.object(aw_client, "get_metar", new_callable=AsyncMock) as mock_metar, \
         patch.object(aw_client, "get_taf", new_callable=AsyncMock) as mock_taf, \
         patch("app.services.coverage_service.find_nearest_reporting_stations", new_callable=AsyncMock) as mock_fallback:
        
        mock_dir.return_value = {
            "icao": "K99Y", "name": "Small Field",
            "lat": 40.0, "lon": -75.0, "frequencies": []
        }
        mock_rwys.return_value = [] 
        mock_metar.return_value = []
        mock_taf.return_value = []
        mock_fallback.return_value = [
            {"ident": "KPHL", "name": "Philadelphia", "distance_nm": 10.0, "bearing_deg": 180, "flight_category": "VFR", "observed_at": "..."}
        ]
        
        coverage = await get_airport_coverage("K99Y")
        
        assert coverage.ident == "K99Y"
        assert coverage.has_field_metar is False
        assert coverage.metar_status == "unavailable"
        assert len(coverage.nearby_weather_stations) == 1
        assert coverage.nearby_weather_stations[0].ident == "KPHL"

@pytest.mark.asyncio
async def test_runway_wind_no_fallback_by_default():
    from app.api.routes.runways import runways as get_runway_analysis
    
    with patch("app.api.routes.runways.get_airport_runways") as mock_rwys, \
         patch.object(aw_client, "get_metar", new_callable=AsyncMock) as mock_metar:
        
        mock_rwys.return_value = [{"id": "04", "heading": 40, "length_ft": 5000, "width_ft": 100}]
        mock_metar.return_value = [] # No field METAR
        
        analysis = await get_runway_analysis("K99Y")
        
        assert analysis.wind_direction_deg is None
        assert "No METAR data available" in analysis.warnings[0]
        assert analysis.favored_runway.reason == "Wind data unavailable."
        assert analysis.runways[0].headwind_kt is None
