import pytest
from unittest.mock import patch, AsyncMock
from app.services.hazard_service import detect_convective_risk

@pytest.mark.asyncio
async def test_detect_convective_risk_high_field_ts():
    # METAR with TSRA
    with patch("app.services.aviationweather_client.aw_client.get_metar") as mock_metar, \
         patch("app.services.aviationweather_client.aw_client.get_taf") as mock_taf:
        
        mock_metar.return_value = [{"rawOb": "KAGC 101234Z 28010KT 2SM TSRA BKN010 15/10 A2992"}]
        mock_taf.return_value = []
        
        convective = await detect_convective_risk("KAGC", [], 0, 0)
        assert convective.risk_level == "high"
        assert convective.field_thunderstorm is True
        assert any("Thunderstorms reported at the field" in ind for ind in convective.indicators)

@pytest.mark.asyncio
async def test_detect_convective_risk_moderate_vcts():
    # METAR with VCTS
    with patch("app.services.aviationweather_client.aw_client.get_metar") as mock_metar, \
         patch("app.services.aviationweather_client.aw_client.get_taf") as mock_taf:
        
        mock_metar.return_value = [{"rawOb": "KAGC 101234Z 28010KT 10SM VCTS SCT040 15/10 A2992"}]
        mock_taf.return_value = []
        
        convective = await detect_convective_risk("KAGC", [], 0, 0)
        assert convective.risk_level == "moderate"
        assert convective.vicinity_thunderstorm is True

@pytest.mark.asyncio
async def test_detect_convective_risk_moderate_taf():
    # TAF with TS
    with patch("app.services.aviationweather_client.aw_client.get_metar") as mock_metar, \
         patch("app.services.aviationweather_client.aw_client.get_taf") as mock_taf:
        
        mock_metar.return_value = []
        mock_taf.return_value = [{"rawTAF": "TAF KAGC 101120Z 1012/1112 28010KT P6SM TS SCT040"}]
        
        convective = await detect_convective_risk("KAGC", [], 0, 0)
        assert convective.risk_level == "moderate"
        assert convective.taf_thunderstorm is True

@pytest.mark.asyncio
async def test_detect_convective_risk_high_nws_warning():
    # NWS Severe Thunderstorm Warning
    mock_alerts = [{
        "properties": {
            "event": "Severe Thunderstorm Warning",
            "severity": "Severe",
            "description": "A SEVERE THUNDERSTORM IS APPROACHING..."
        }
    }]
    with patch("app.services.aviationweather_client.aw_client.get_metar", return_value=[]), \
         patch("app.services.aviationweather_client.aw_client.get_taf", return_value=[]):
        
        convective = await detect_convective_risk("KAGC", mock_alerts, 0, 0)
        assert convective.risk_level == "high"
        assert convective.convective_alert_active is True

@pytest.mark.asyncio
async def test_detect_convective_risk_low():
    with patch("app.services.aviationweather_client.aw_client.get_metar", return_value=[]), \
         patch("app.services.aviationweather_client.aw_client.get_taf", return_value=[]):
        
        convective = await detect_convective_risk("KAGC", [], 0, 0)
        assert convective.risk_level == "low"
        assert "No convective indicators" in convective.summary
