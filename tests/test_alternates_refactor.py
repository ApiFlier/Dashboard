import pytest
from app.services.alternate_ranker import find_alternates
from app.services.airport_data import get_airport_directory
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_alternates_default_limit():
    # KPHL coordinates approx 39.8, -75.2
    # Mocking get_nearby_candidates_from_db to return 30 airports
    mock_candidates = [
        {"ident": f"TEST{i}", "name": f"Test Airport {i}", "lat": 40.0, "lon": -75.0, "type": "small_airport", "distance_nm": 10.0 + i}
        for i in range(30)
    ]
    
    with patch("app.services.alternate_ranker.get_nearby_candidates_from_db", return_value=mock_candidates), \
         patch("app.services.alternate_ranker.aw_client.get_metars", new_callable=AsyncMock) as mock_metars:
        
        # All have METAR
        mock_metars.return_value = [
            {"icao": f"TEST{i}", "fltcat": "VFR"} for i in range(30)
        ]
        
        res = await find_alternates(39.8, -75.2, "KPHL", limit=10)
        assert len(res.alternates) == 10
        assert res.limit == 10
        assert res.candidates_considered == 30

@pytest.mark.asyncio
async def test_alternates_exclude_non_reporting_by_default():
    mock_candidates = [
        {"ident": "REPT1", "name": "Reporting", "lat": 40.0, "lon": -75.0, "type": "medium_airport", "distance_nm": 10.0},
        {"ident": "NON1", "name": "Non Reporting", "lat": 40.1, "lon": -75.1, "type": "small_airport", "distance_nm": 11.0}
    ]
    
    with patch("app.services.alternate_ranker.get_nearby_candidates_from_db", return_value=mock_candidates), \
         patch("app.services.alternate_ranker.aw_client.get_metars", new_callable=AsyncMock) as mock_metars:
        
        # Only REPT1 has METAR
        mock_metars.return_value = [{"icao": "REPT1", "fltcat": "VFR"}]
        
        res = await find_alternates(39.8, -75.2, "KPHL", include_non_reporting=False)
        assert len(res.alternates) == 1
        assert res.alternates[0].icao == "REPT1"
        assert res.excluded_summary.no_weather == 1

@pytest.mark.asyncio
async def test_alternates_include_non_reporting_true():
    mock_candidates = [
        {"ident": "REPT1", "name": "Reporting", "lat": 40.0, "lon": -75.0, "type": "medium_airport", "distance_nm": 10.0},
        {"ident": "NON1", "name": "Non Reporting", "lat": 40.1, "lon": -75.1, "type": "small_airport", "distance_nm": 11.0}
    ]
    
    with patch("app.services.alternate_ranker.get_nearby_candidates_from_db", return_value=mock_candidates), \
         patch("app.services.alternate_ranker.aw_client.get_metars", new_callable=AsyncMock) as mock_metars:
        
        mock_metars.return_value = [{"icao": "REPT1", "fltcat": "VFR"}]
        
        res = await find_alternates(39.8, -75.2, "KPHL", include_non_reporting=True)
        assert len(res.alternates) == 2
        assert any(a.icao == "NON1" for a in res.alternates)
