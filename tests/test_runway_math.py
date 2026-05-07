from app.services.runway_math import calculate_wind_components

def test_aligned_wind():
    hw, tw, cw, cwg = calculate_wind_components(100, 100, 10)
    assert hw == 10.0
    assert tw == 0.0
    assert cw == 0.0
    assert cwg is None

def test_direct_crosswind():
    hw, tw, cw, cwg = calculate_wind_components(100, 190, 10)
    assert hw == 0.0
    assert tw == 0.0
    assert cw == 10.0
    assert cwg is None

def test_direct_tailwind():
    hw, tw, cw, cwg = calculate_wind_components(100, 280, 10)
    assert hw == 0.0
    assert tw == 10.0
    assert cw == 0.0
    assert cwg is None

def test_gust_handling():
    hw, tw, cw, cwg = calculate_wind_components(100, 145, 10, 20)
    # sin(45) ~ 0.707 -> 10 * 0.707 = 7.07, 20 * 0.707 = 14.14
    assert cw == 7.1
    assert cwg == 14.1

def test_variable_missing_wind():
    hw, tw, cw, cwg = calculate_wind_components(100, None, 10)
    assert hw is None
    assert tw is None
    assert cw is None
    assert cwg is None

def test_calm_wind():
    hw, tw, cw, cwg = calculate_wind_components(100, 100, 0)
    assert hw == 0.0
    assert tw == 0.0
    assert cw == 0.0
    assert cwg is None
