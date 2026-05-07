import pytest
from app.api.routes.weather import normalize_timestamp, normalize_visibility, normalize_altimeter, get_ceiling, parse_metar

def test_normalize_timestamp():
    # Epoch int
    assert normalize_timestamp(1778086380) == "2026-05-06T16:53:00+00:00"
    # Epoch float
    assert normalize_timestamp(1778086380.0) == "2026-05-06T16:53:00+00:00"
    # ISO string
    assert normalize_timestamp("2026-05-06T17:00:00.000Z") == "2026-05-06T17:00:00.000Z"
    # None
    assert normalize_timestamp(None) is None

def test_normalize_visibility():
    assert normalize_visibility(10) == 10.0
    assert normalize_visibility("10+") == 10.0
    assert normalize_visibility("6+") == 6.0
    assert normalize_visibility("P6SM") == 6.0
    assert normalize_visibility("M1/4SM") == 0.25
    assert normalize_visibility("1 1/2") == 1.5
    assert normalize_visibility("") is None
    assert normalize_visibility(None) is None

def test_normalize_altimeter():
    # inHg
    assert normalize_altimeter(29.92) == 29.92
    # hPa
    assert normalize_altimeter(1013.25) == 29.92 # 1013.25 * 0.02953 = 29.921...
    # String
    assert normalize_altimeter("29.82") == 29.82
    assert normalize_altimeter(None) is None

def test_get_ceiling():
    clouds = [
        {"cover": "FEW", "base": 2000},
        {"cover": "BKN", "base": 700},
        {"cover": "OVC", "base": 1600}
    ]
    assert get_ceiling(clouds) == 700
    
    assert get_ceiling([{"cover": "SCT", "base": 500}]) is None
    assert get_ceiling([]) is None
    assert get_ceiling(None) is None

def test_parse_metar_robustness():
    payload = {
        "obsTime": 1778086380,
        "reportTime": "2026-05-06T17:00:00.000Z",
        "visib": "10+",
        "rawOb": "METAR KAGC 061653Z 30007KT 10SM BKN007 OVC016 10/09 A2982",
        "fltcat": "IFR",
        "clouds": [{"cover":"BKN","base":700},{"cover":"OVC","base":1600}],
        "altim": 1009.9,
        "wdir": 300,
        "wspd": 7
    }
    
    metar = parse_metar(payload)
    assert metar.observed_at == "2026-05-06T17:00:00.000Z" # reportTime preferred
    assert metar.visibility_sm == 10.0
    assert metar.ceiling_ft_agl == 700
    assert metar.altimeter_in_hg == 29.82 # 1009.9 * 0.02953
    assert metar.wind.direction_deg == 300
    assert metar.wind.speed_kt == 7
