from fastapi import APIRouter
from app.services.runtime_db import get_connection, SCHEMA_VERSION
from app.core.config import settings
import os

router = APIRouter()

@router.get("/status")
async def get_reference_status():
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM airports")
        airport_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM runways")
        runway_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM frequencies")
        frequency_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT value FROM schema_meta WHERE key = 'ref_data_version'")
        row = cursor.fetchone()
        data_version = row[0] if row else "unknown"
        
        cursor.execute("SELECT value FROM schema_meta WHERE key = 'last_seeded_at'")
        row = cursor.fetchone()
        last_seeded_at = row[0] if row else "unknown"
        
        cursor.execute("SELECT value FROM schema_meta WHERE key = 'ref_data_source'")
        row = cursor.fetchone()
        source = row[0] if row else "seed_json"

        cursor.execute("SELECT value FROM schema_meta WHERE key = 'last_imported_at'")
        row = cursor.fetchone()
        last_imported_at = row[0] if row else "unknown"

        cursor.execute("SELECT count(*) FROM airports WHERE source = 'seed_json'")
        curated_preserved_count = cursor.fetchone()[0]

        cursor.execute("SELECT value FROM schema_meta WHERE key = 'version'")
        row = cursor.fetchone()
        current_schema_version = int(row[0]) if row else 0
        
        warnings = []
        if airport_count == 0:
            warnings.append("No airports seeded.")
        if runway_count == 0:
            warnings.append("No runways seeded.")
        
        return {
            "airport_count": airport_count,
            "runway_count": runway_count,
            "frequency_count": frequency_count,
            "data_version": data_version,
            "source": source,
            "import_source_name": "OurAirports" if source == "OurAirports" else source,
            "last_seeded_at": last_seeded_at,
            "last_imported_at": last_imported_at,
            "curated_preserved_count": curated_preserved_count,
            "schema_version": current_schema_version,
            "target_schema_version": SCHEMA_VERSION,
            "db_path": settings.DB_PATH,
            "state_dir": settings.STATE_DIR,
            "db_exists": os.path.exists(settings.DB_PATH),
            "public_readonly_mode": settings.PUBLIC_READONLY_MODE,
            "debug_public_endpoints": settings.DEBUG_PUBLIC_ENDPOINTS,
            "warnings": warnings
        }
