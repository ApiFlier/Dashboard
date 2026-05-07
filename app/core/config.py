import os

class Config:
    USER_AGENT = os.environ.get("AIRFIELDOPS_USER_AGENT", "AirfieldOps/0.1 contact: admin@example.com")
    TIMEOUT_SEC = float(os.environ.get("HTTP_TIMEOUT_SECONDS", "10.0"))
    STATE_DIR = os.environ.get("AIRFIELDOPS_STATE_DIR", "/var/lib/airfieldops")
    DB_PATH = os.environ.get("AIRFIELDOPS_DB_PATH", "/var/lib/airfieldops/airfieldops.sqlite")
    
    # Public exposure safety
    PUBLIC_READONLY_MODE = os.environ.get("PUBLIC_READONLY_MODE", "true").lower() == "true"
    ADMIN_API_TOKEN = os.environ.get("ADMIN_API_TOKEN", "")
    DEBUG_PUBLIC_ENDPOINTS = os.environ.get("DEBUG_PUBLIC_ENDPOINTS", "false").lower() == "true"

settings = Config()
