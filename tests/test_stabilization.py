import pytest
from app.services.alternate_ranker import find_alternates
from app.api.routes.runways import runways as get_runways
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_alternates_default_limit():
    mock_candidates = [
        {"ident": f"TEST{i}", "name": f"Test Airport {i}", "lat": 40.0, "lon": -75.0, "type": "small_airport", "distance_nm": 10.0 + i}
        for i in range(30)
    ]
    with patch("app.services.alternate_ranker.get_nearby_candidates_from_db", return_value=mock_candidates), \
         patch("app.services.alternate_ranker.aw_client.get_metars", new_callable=AsyncMock) as mock_metars:
        mock_metars.return_value = [{"icao": f"TEST{i}", "fltcat": "VFR"} for i in range(30)]
        res = await find_alternates(39.8, -75.2, "KPHL", limit=10)
        assert len(res.alternates) <= 10
        assert res.limit == 10

@pytest.mark.asyncio
async def test_alternates_hard_limit():
    mock_candidates = [
        {"ident": f"TEST{i}", "name": f"Test Airport {i}", "lat": 40.0, "lon": -75.0, "type": "small_airport", "distance_nm": 10.0 + i}
        for i in range(50)
    ]
    with patch("app.services.alternate_ranker.get_nearby_candidates_from_db", return_value=mock_candidates), \
         patch("app.services.alternate_ranker.aw_client.get_metars", new_callable=AsyncMock) as mock_metars:
        mock_metars.return_value = [{"icao": f"TEST{i}", "fltcat": "VFR"} for i in range(50)]
        res = await find_alternates(39.8, -75.2, "KPHL", limit=100)
        assert len(res.alternates) <= 25 # Hard limit

@pytest.mark.asyncio
async def test_alternates_prefetch_cap():
    mock_candidates = [
        {"ident": f"TEST{i}", "name": f"Test Airport {i}", "lat": 40.0, "lon": -75.0, "type": "small_airport", "distance_nm": 10.0 + i}
        for i in range(100)
    ]
    with patch("app.services.alternate_ranker.get_nearby_candidates_from_db", return_value=mock_candidates), \
         patch("app.services.alternate_ranker.aw_client.get_metars", new_callable=AsyncMock) as mock_metars:
        mock_metars.return_value = []
        await find_alternates(39.8, -75.2, "KPHL")
        # Ensure only 50 were requested
        args, _ = mock_metars.call_args
        requested_icaos = args[0]
        assert len(requested_icaos) <= 50

@pytest.mark.asyncio
async def test_runway_wording_calm():
    mock_runways = [{"id": "9-27", "heading": 90, "length_ft": 5000, "width_ft": 100}]
    mock_metar = [{"wdir": 0, "wspd": 0, "raw": "KPHL 00000KT"}]
    with patch("app.api.routes.runways.get_airport_runways", return_value=mock_runways), \
         patch("app.api.routes.runways.aw_client.get_metar", new_callable=AsyncMock) as mock_aw:
        mock_aw.return_value = mock_metar
        res = await get_runways("KPHL")
        assert res.favored_runway.reason == "Calm. Any runway may be used."

@pytest.mark.asyncio
async def test_runway_wording_no_wind():
    mock_runways = [{"id": "9-27", "heading": 90, "length_ft": 5000, "width_ft": 100}]
    with patch("app.api.routes.runways.get_airport_runways", return_value=mock_runways), \
         patch("app.api.routes.runways.aw_client.get_metar", new_callable=AsyncMock) as mock_aw:
        mock_aw.return_value = []
        res = await get_runways("KPHL")
        assert res.favored_runway.reason == "No field wind available."
