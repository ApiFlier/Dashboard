import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from app.main import app
from app.models.airport import AirportSummary

client = TestClient(app)

@pytest.mark.asyncio
async def test_get_airport_summary():
    # Mock services to return controlled data
    with patch("app.api.routes.airport.get_airport_summary", new_callable=AsyncMock) as mock_summary:
        mock_summary.return_value = AirportSummary(
            icao="KAVP",
            name="Wilkes-Barre Scranton Intl",
            flight_category="VFR",
            field_weather_available=True,
            weather_status="available",
            nearby_weather_used=False,
            wind_summary="230@12KT",
            favored_runway_end="22",
            favored_runway_reason="Aligned with wind",
            hazard_risk="low",
            has_runways=True,
            has_frequencies=True,
            generated_at="2026-05-07T12:00:00Z",
            warnings=[]
        )
        
        response = client.get("/api/airport/KAVP/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["icao"] == "KAVP"
        assert data["flight_category"] == "VFR"
        assert "iata_code" in data
        assert "wind_summary" in data

@pytest.mark.asyncio
async def test_get_batch_summaries():
    with patch("app.api.routes.airport.get_batch_airport_summaries", new_callable=AsyncMock) as mock_batch:
        mock_batch.return_value = [
            {"icao": "KAVP", "flight_category": "VFR"},
            {"icao": "KAGC", "flight_category": "MVFR"}
        ]
        
        response = client.get("/api/airports/summary?idents=KAVP,KAGC")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["icao"] == "KAVP"
        assert data[1]["icao"] == "KAGC"

@pytest.mark.asyncio
async def test_batch_summary_caps_at_12():
    # Test service directly for capping logic
    from app.services.summary_service import get_batch_airport_summaries
    
    dummy_summary = AirportSummary(
        icao="DUMMY", name="Dummy", flight_category="VFR",
        field_weather_available=True, weather_status="available",
        nearby_weather_used=False, wind_summary="000@0KT",
        hazard_risk="low", has_runways=True, has_frequencies=True,
        generated_at="2026-05-07T12:00:00Z", warnings=[]
    )

    with patch("app.services.summary_service.get_airport_summary", new_callable=AsyncMock) as mock_summary:
        mock_summary.return_value = dummy_summary
        
        idents = [f"K{i:03}" for i in range(20)]
        summaries = await get_batch_airport_summaries(idents)
        assert len(summaries) == 12

def test_summary_remains_public():
    """Summary endpoint should remain accessible in read-only mode."""
    with patch("app.core.config.settings.PUBLIC_READONLY_MODE", True):
        # Just check it's not 403
        response = client.get("/api/airport/KAVP/summary")
        assert response.status_code != 403
