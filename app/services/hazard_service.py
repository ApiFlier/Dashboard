import datetime
from app.models.hazard import HazardSummary
from .nws_client import nws_client

async def get_hazards_for_airport(airport: str, lat: float, lon: float, radius_nm: float = 75) -> HazardSummary:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    summary = HazardSummary(
        airport=airport,
        generated_at=now,
        risk_level="unknown",
        counts={"nws_alerts": 0, "sigmets": 0, "gairmets": 0, "cwas": 0}
    )
    
    # NWS Active alerts for point
    alerts = await nws_client.get_alerts_by_point(lat, lon)
    summary.nws_alerts = alerts if alerts else []
    summary.counts["nws_alerts"] = len(summary.nws_alerts)
    
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
        
    return summary
