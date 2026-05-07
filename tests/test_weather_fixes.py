import pytest
import datetime
from app.api.routes.weather import normalize_timestamp, normalize_visibility, get_ceiling, parse_metar

def test_millisecond_epoch():
    # 1778086380000 is 2026-05-06 16:53:00 UTC in ms
    ms_epoch = 1778086380000
    expected = "2026-05-06T16:53:00+00:00"
    assert normalize_timestamp(ms_epoch) == expected

def test_visibility_variations():
    assert normalize_visibility("6SM") == 6.0
    assert normalize_visibility("10") == 10.0
    assert normalize_visibility("M1/4") == 0.25
    assert normalize_visibility("P6") == 6.0
    assert normalize_visibility(" - ") is None
    assert normalize_visibility("") is None

def test_robust_ceiling():
    # Malformed layer
    clouds = ["not a dict", {"cover": "BKN", "base": "700"}]
    assert get_ceiling(clouds) == 700
    
    # Missing base
    clouds = [{"cover": "OVC"}]
    assert get_ceiling(clouds) is None
    
    # Non-int base string
    clouds = [{"cover": "OVC", "base": "unkn"}]
    assert get_ceiling(clouds) is None

def test_wind_robustness():
    # VRB wind
    payload = {"wdir": "VRB", "wspd": 5}
    metar = parse_metar(payload)
    assert metar.wind.variable is True
    assert metar.wind.direction_deg is None
    assert metar.wind.speed_kt == 5.0
    
    # Missing wdir
    payload = {"wspd": 10}
    metar = parse_metar(payload)
    assert metar.wind.direction_deg is None
    assert metar.wind.speed_kt == 10.0
    
    # String wdir
    payload = {"wdir": "090", "wspd": 12}
    metar = parse_metar(payload)
    assert metar.wind.direction_deg == 90
    assert metar.wind.speed_kt == 12.0

def test_metar_parsing_missing_fields():
    # Very minimal payload
    payload = {"rawOb": "METAR KAGC ..."}
    metar = parse_metar(payload)
    assert metar.raw == "METAR KAGC ..."
    assert metar.observed_at == ""
    assert metar.wind.speed_kt is None
    assert metar.visibility_sm is None
