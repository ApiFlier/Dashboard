import os

class Config:
    USER_AGENT = os.environ.get("USER_AGENT", "AirfieldOps-Core/1.0 (+http://localhost)")
    TIMEOUT_SEC = float(os.environ.get("HTTP_TIMEOUT_SECONDS", "10.0"))
    STATE_DIR = os.environ.get("AIRFIELDOPS_STATE_DIR", "/var/lib/airfieldops")
    DB_PATH = os.environ.get("AIRFIELDOPS_DB_PATH", "/var/lib/airfieldops/airfieldops.sqlite")

settings = Config()
