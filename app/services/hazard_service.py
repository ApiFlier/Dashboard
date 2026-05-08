import datetime
import re
from typing import Optional, List, Dict, Any
from app.models.hazard import HazardSummary
from app.models.convective import ConvectiveAwareness
from .nws_client import nws_client
from .aviationweather_client import aw_client

async def get_hazards_for_airport(airport: str, lat: float, lon: float, radius_nm: float = 75) -> HazardSummary:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    summary = HazardSummary(
        airport=airport,
        generated_at=now,
        risk_level="unknown",
        counts={"nws_alerts": 0, "sigmets": 0, "gairmets": 0, "cwas": 0}
    )
    
    # 1. NWS Active alerts for point
    alerts = await nws_client.get_alerts_by_point(lat, lon)
    summary.nws_alerts = alerts if alerts else []
    summary.counts["nws_alerts"] = len(summary.nws_alerts)
    
    # 2. Convective Awareness Logic
    convective = await detect_convective_risk(airport, alerts, lat, lon)
    summary.convective_awareness = convective
    
    # Aviation Weather hazards (MVP empty list)
    summary.sigmets = []
    summary.gairmets = []
    summary.cwas = []
    
    if alerts is None:
        summary.warnings.append("Could not fetch NWS alerts.")
        summary.risk_level = "unknown"
    else:
        # Determine risk level based on NWS alerts
        if len(summary.nws_alerts) > 0:
            is_high = False
            for alert in summary.nws_alerts:
                severity = alert.get("properties", {}).get("severity", "Unknown")
                if severity in ["Severe", "Extreme"]:
                    is_high = True
                    break
            summary.risk_level = "high" if is_high else "moderate"
        else:
            summary.risk_level = "low"
            
    # If convective risk is high, promote overall hazard risk
    if convective and convective.risk_level == "high":
        summary.risk_level = "high"
    elif convective and convective.risk_level == "moderate" and summary.risk_level == "low":
        summary.risk_level = "moderate"
        
    return summary

async def detect_convective_risk(icao: str, alerts: Optional[List[Dict[str, Any]]], lat: float, lon: float) -> ConvectiveAwareness:
    indicators = []
    field_ts = False
    vcts = False
    taf_ts = False
    alert_active = False
    
    # Fetch METAR/TAF for convective analysis
    try:
        metars = await aw_client.get_metar(icao)
        raw_metar = metars[0].get("rawOb", "") if metars else ""
        
        tafs = await aw_client.get_taf(icao)
        raw_taf = tafs[0].get("rawTAF", "") if tafs else ""
    except Exception:
        raw_metar = ""
        raw_taf = ""

    # METAR Analysis
    if raw_metar:
        # Field Thunderstorm: TS, TSRA, +TSRA, -TSRA
        if re.search(r'\b(\+|-)?TS(RA)?\b', raw_metar):
            field_ts = True
            indicators.append("Thunderstorms reported at the field (METAR).")
        # Vicinity Thunderstorm
        if "VCTS" in raw_metar:
            vcts = True
            indicators.append("Thunderstorms reported in the vicinity (METAR).")
        # Cumulonimbus clouds
        if "CB" in raw_metar:
            indicators.append("Cumulonimbus (convective) clouds reported.")

    # TAF Analysis
    if raw_taf:
        if "TS" in raw_taf or "VCTS" in raw_taf:
            taf_ts = True
            indicators.append("Thunderstorms forecast (TAF).")

    # NWS Alerts Analysis
    convective_alerts = [
        "Severe Thunderstorm Warning", "Severe Thunderstorm Watch",
        "Tornado Warning", "Tornado Watch", "Special Weather Statement"
    ]
    if alerts:
        for a in alerts:
            event = a.get("properties", {}).get("event", "")
            desc = a.get("properties", {}).get("description", "").lower()
            
            if any(ca in event for ca in convective_alerts):
                alert_active = True
                indicators.append(f"Active NWS Convective Alert: {event}")
            elif "thunderstorm" in desc or "lightning" in desc:
                alert_active = True
                indicators.append(f"NWS Alert mentioning convective activity: {event}")

    # Risk Determination
    risk = "low"
    if field_ts or any("Tornado Warning" in ind or "Severe Thunderstorm Warning" in ind for ind in indicators):
        risk = "high"
    elif vcts or taf_ts or alert_active:
        risk = "moderate"
        
    # Summary wording
    if risk == "high":
        if field_ts:
            summary_text = "Thunderstorms reported at or near the field. Ramp and ground operations may be affected."
        else:
            summary_text = "Severe convective warnings active for this area. High risk of thunderstorms."
    elif risk == "moderate":
        summary_text = "Convective activity detected in the vicinity or forecast. Monitor local conditions."
    else:
        summary_text = "No convective indicators currently detected from available sources."

    return ConvectiveAwareness(
        risk_level=risk,
        field_thunderstorm=field_ts,
        vicinity_thunderstorm=vcts,
        taf_thunderstorm=taf_ts,
        convective_alert_active=alert_active,
        summary=summary_text,
        indicators=list(set(indicators))
    )
