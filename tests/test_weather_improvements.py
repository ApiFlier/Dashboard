import pytest
from app.services.weather_normalization import derive_flight_category
from app.api.routes.weather import parse_metar
from app.core.cache import cache
import time

def test_derive_flight_category():
    # VFR
    assert derive_flight_category(3501, 6.0) == "VFR"
    assert derive_flight_category(None, None) == "VFR" # default assumption
    
    # MVFR
    assert derive_flight_category(3000, 6.0) == "MVFR"
    assert derive_flight_category(3501, 5.0) == "MVFR"
    
    # IFR
    assert derive_flight_category(999, 5.0) == "IFR"
    assert derive_flight_category(3501, 2.9) == "IFR"
    
    # LIFR
    assert derive_flight_category(499, 3.0) == "LIFR"
    assert derive_flight_category(1000, 0.9) == "LIFR"

def test_parse_metar_with_derived_rules():
    # fltcat missing but data present
    raw = {
        "rawOb": "METAR KAGC ...",
        "visib": "2",
        "clouds": [{"cover": "OVC", "base": "2500"}]
    }
    metar = parse_metar(raw)
    assert metar.flight_category == "IFR" # vis 2 is IFR

    # fltcat UNKNOWN but data present
    raw["fltcat"] = "UNKNOWN"
    metar = parse_metar(raw)
    assert metar.flight_category == "IFR"

def test_persistent_cache_logic(tmp_path):
    # Mock DB for test? The project already uses a file DB.
    # We'll just test the logic with the current DB if safe, 
    # but better to use the already established pattern in other tests.
    
    key = "test_key"
    val = {"foo": "bar"}
    
    cache.set(key, val, ttl_seconds=1)
    assert cache.get(key) == val
    
    # Wait for expiry
    time.sleep(1.1)
    assert cache.get(key) is None
    
    # Stale allowed
    data, is_stale = cache.get_stale_allowed(key)
    assert data["foo"] == "bar"
    assert is_stale is True
    assert "_cached_at" in data
