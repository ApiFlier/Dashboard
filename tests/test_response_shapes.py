from fastapi.testclient import TestClient
from unittest import mock
from app.main import app
import json
import pytest

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture
def mock_external_apis():
    # Provide predictable data without actually hitting APIs
    with mock.patch("app.services.aviationweather_client.aw_client.get_metar") as mock_metar, \
         mock.patch("app.services.aviationweather_client.aw_client.get_taf") as mock_taf, \
         mock.patch("app.services.nws_client.nws_client.get_alerts_by_point") as mock_alerts:
         
        mock_metar.return_value = [{
            "rawOb": "KAGC 101234Z 28010G20KT 10SM SCT040 15/10 A2992",
            "obsTime": "2024-01-01T12:34:00Z",
            "fltcat": "VFR",
            "wdir": 280,
            "wspd": 10,
            "wgst": 20,
            "visib": 10.0,
            "ceil": 4000.0,
            "temp": 15.0,
            "dewp": 10.0,
            "altim": 29.92
        }]
        
        mock_taf.return_value = [{
            "rawTAF": "TAF KAGC 101120Z 1012/1112 28010KT P6SM SCT040",
            "issueTime": "2024-01-01T11:20:00Z",
            "validTimeFrom": "2024-01-01T12:00:00Z",
            "validTimeTo": "2024-01-02T12:00:00Z",
            "fcsts": []
        }]
        
        mock_alerts.return_value = []
        
        yield {
            "metar": mock_metar,
            "taf": mock_taf,
            "alerts": mock_alerts
        }

def test_weather_shape(client, mock_external_apis):
    response = client.get("/api/airport/KAGC/weather")
    assert response.status_code == 200
    data = response.json()
    assert data["airport"] == "KAGC"
    assert "generated_at" in data
    assert data["metar"]["flight_category"] == "VFR"
    assert data["metar"]["wind"]["speed_kt"] == 10
    assert data["metar"]["wind"]["gust_kt"] == 20
    assert len(data["warnings"]) == 0

def test_weather_missing(client, mock_external_apis):
    mock_external_apis["metar"].return_value = []
    mock_external_apis["taf"].return_value = []
    
    response = client.get("/api/airport/KAGC/weather")
    assert response.status_code == 200
    data = response.json()
    assert data["metar"] is None
    assert data["taf"] is None
    assert "METAR unavailable" in data["warnings"]
    assert "TAF unavailable" in data["warnings"]

def test_runway_shape(client, mock_external_apis):
    response = client.get("/api/airport/KAGC/runways")
    assert response.status_code == 200
    data = response.json()
    
    assert data["favored_runway"]["id"] == "28"
    
    # Look for runway 28
    rwy_28 = next((r for r in data["runways"] if r["id"] == "28"), None)
    assert rwy_28 is not None
    assert rwy_28["headwind_kt"] == 10.0
    assert rwy_28["tailwind_kt"] == 0.0
    assert rwy_28["crosswind_kt"] == 0.0
    
def test_alternates_shape(client, mock_external_apis):
    response = client.get("/api/airport/KAGC/alternates")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    
    if len(data) > 0:
        first = data[0]
        assert "icao" in first
        assert "rank_reason" in first
        assert "score" in first

def test_hazards_shape(client, mock_external_apis):
    response = client.get("/api/airport/KAGC/hazards")
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] == "low"
    assert data["counts"]["nws_alerts"] == 0

def test_brief_shape(client, mock_external_apis):
    response = client.get("/api/airport/KAGC/brief")
    assert response.status_code == 200
    data = response.json()
    
    assert "airport" in data
    assert "generated_at" in data
    assert "condition" in data
    assert "favored_runway" in data
    assert "main_concerns" in data
    assert "best_alternates" in data
    assert "plain_english" in data
    assert "warnings" in data
    assert "disclaimer" in data
    
    assert data["airport"]["icao"] == "KAGC"
    assert len(data["plain_english"]) > 0
    assert "Runway 28 appears favored by the current wind." in data["plain_english"]
