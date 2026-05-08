import pytest
from app.models.runway import RunwayConditions, RunwayRiskFlags
from app.services.runway_math import calculate_wind_components
from fastapi.testclient import TestClient
from unittest import mock
from app.main import app

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

def test_runway_model_accepts_float_heading():
    r = RunwayConditions(
        id="31L",
        heading=30.6,
        length_ft=14511,
        width_ft=200,
        risk_flags=RunwayRiskFlags()
    )
    assert r.heading == 30.6

def test_runway_math_with_decimal_heading():
    hw, tw, cw, cwg = calculate_wind_components(30.6, 30, 10)
    assert hw == 10.0
    assert tw == 0.0
    assert cw == 0.1

def test_kjfk_summary_no_error(client):
    mock_runways = [
        {"id": "31L", "heading": 30.6, "length_ft": 14511, "width_ft": 200},
        {"id": "13R", "heading": 210.6, "length_ft": 14511, "width_ft": 200}
    ]
    mock_dir = {"icao": "KJFK", "name": "John F Kennedy Intl", "lat": 40.6, "lon": -73.7, "frequencies": []}
    
    with mock.patch("app.api.routes.runways.get_airport_runways", return_value=mock_runways), \
         mock.patch("app.services.airport_data.get_airport_runways", return_value=mock_runways), \
         mock.patch("app.services.airport_data.get_airport_directory", return_value=mock_dir), \
         mock.patch("app.services.aviationweather_client.aw_client.get_metar", return_value=[]), \
         mock.patch("app.services.aviationweather_client.aw_client.get_metars", return_value=[]), \
         mock.patch("app.services.aviationweather_client.aw_client.get_taf", return_value=[]), \
         mock.patch("app.services.nws_client.nws_client.get_alerts_by_point", return_value=[]):
        
        response = client.get("/api/airports/summary?idents=KJFK")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert "error" not in data[0]
        assert data[0]["icao"] == "KJFK"

def test_batch_summary_mixed(client):
    mock_runways = [
        {"id": "04", "heading": 40.0, "length_ft": 7500, "width_ft": 150}
    ]
    
    with mock.patch("app.api.routes.runways.get_airport_runways", return_value=mock_runways), \
         mock.patch("app.services.airport_data.get_airport_runways", return_value=mock_runways), \
         mock.patch("app.services.aviationweather_client.aw_client.get_metar", return_value=[]), \
         mock.patch("app.services.aviationweather_client.aw_client.get_metars", return_value=[]), \
         mock.patch("app.services.aviationweather_client.aw_client.get_taf", return_value=[]), \
         mock.patch("app.services.nws_client.nws_client.get_alerts_by_point", return_value=[]), \
         mock.patch("app.services.airport_data.get_airport_directory") as mock_dir:
        
        mock_dir.side_effect = lambda icao: {"icao": icao, "name": f"Name {icao}", "lat": 0, "lon": 0, "frequencies": []}
        
        response = client.get("/api/airports/summary?idents=KAVP,KAGC,KLAX,KJFK")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 4
        for item in data:
            assert "error" not in item
