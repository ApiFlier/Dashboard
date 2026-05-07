import datetime
from typing import Optional, Any

def derive_flight_category(ceiling_ft: Optional[int], visibility_sm: Optional[float]) -> str:
    """
    Derives flight category based on standard thresholds:
    LIFR: Ceiling < 500ft OR Visibility < 1sm
    IFR:  Ceiling 500 to <1000ft OR Visibility 1 to <3sm
    MVFR: Ceiling 1000 to 3000ft OR Visibility 3 to 5sm
    VFR:  Ceiling > 3000ft AND Visibility > 5sm
    """
    # Use very high values for None to simplify comparison (assume clear/unlimited)
    c = ceiling_ft if ceiling_ft is not None else 10000
    v = visibility_sm if visibility_sm is not None else 10.0

    if v < 1 or c < 500:
        return "LIFR"
    if v < 3 or c < 1000:
        return "IFR"
    if v <= 5 or c <= 3000:
        return "MVFR"
    return "VFR"

def normalize_timestamp(val: Any) -> Optional[str]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        try:
            # If the value is very large, it might be milliseconds
            if val > 2 * 10**12: # Far in the future for seconds, likely ms
                val = val / 1000
            elif val > 10**11: # Around 5000 AD for seconds, likely ms
                val = val / 1000
            return datetime.datetime.fromtimestamp(val, tz=datetime.timezone.utc).isoformat()
        except Exception:
            return str(val)
    if isinstance(val, str):
        return val
    return str(val)

def normalize_visibility(val: Any) -> Optional[float]:
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        s = val.upper().replace("SM", "").replace("P", "").replace("M", "").replace("+", "").replace("-", "").strip()
        if not s:
            return None
        try:
            if "/" in s:
                parts = s.split()
                if len(parts) > 1:
                    whole = float(parts[0])
                    frac = parts[1].split("/")
                    return whole + (float(frac[0]) / float(frac[1]))
                else:
                    frac = s.split("/")
                    if len(frac) == 2:
                        return float(frac[0]) / float(frac[1])
                    return float(frac[0])
            return float(s)
        except Exception:
            return None
    return None

def normalize_altimeter(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        fval = float(val)
        if fval > 500:
            return round(fval * 0.02953, 2)
        return round(fval, 2)
    except Exception:
        return None

def get_ceiling(clouds: Optional[list]) -> Optional[int]:
    if not clouds:
        return None
    bases = []
    for layer in clouds:
        if not isinstance(layer, dict):
            continue
        cover = str(layer.get("cover", "")).upper()
        if cover in ["BKN", "OVC", "VV"]:
            base = layer.get("base")
            if base is not None:
                try:
                    bases.append(int(base))
                except (ValueError, TypeError):
                    continue
    return min(bases) if bases else None
