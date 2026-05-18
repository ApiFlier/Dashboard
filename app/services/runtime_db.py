import sqlite3
import os
import json
import logging
from pathlib import Path
from datetime import datetime, timezone

from app.core.config import settings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

SCHEMA_VERSION = 9

def get_db_path() -> str:
    return settings.DB_PATH

def ensure_state_dir():
    state_dir = Path(settings.STATE_DIR)
    if not state_dir.exists():
        logger.info(f"Creating state directory: {state_dir}")
        state_dir.mkdir(parents=True, exist_ok=True)

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn

def get_schema_version(conn: sqlite3.Connection) -> int:
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM schema_meta WHERE key = 'version'")
        row = cursor.fetchone()
        return int(row["value"]) if row else 0
    except sqlite3.OperationalError:
        return 0

def set_schema_version(conn: sqlite3.Connection, version: int):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO schema_meta (key, value, updated_at) VALUES (?, ?, ?)",
        ("version", str(version), now)
    )

def run_migrations(conn: sqlite3.Connection):
    current_version = get_schema_version(conn)
    if current_version < 1:
        logger.info("Running schema migration to version 1")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS airports (
                ident TEXT PRIMARY KEY,
                name TEXT,
                city TEXT,
                state TEXT,
                country TEXT,
                lat REAL,
                lon REAL,
                elevation_ft INTEGER,
                source TEXT,
                updated_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS runways (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                airport_ident TEXT NOT NULL,
                surface_id TEXT,
                le_ident TEXT,
                he_ident TEXT,
                le_heading_deg REAL,
                he_heading_deg REAL,
                le_latitude_deg REAL,
                le_longitude_deg REAL,
                he_latitude_deg REAL,
                he_longitude_deg REAL,
                length_ft INTEGER,
                width_ft INTEGER,
                surface TEXT,
                lighted INTEGER,
                closed INTEGER,
                source TEXT,
                updated_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS frequencies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                airport_ident TEXT NOT NULL,
                type TEXT,
                description TEXT,
                frequency_mhz REAL,
                source TEXT,
                updated_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS recent_airports (
                ident TEXT PRIMARY KEY,
                last_viewed_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_cache (
                cache_key TEXT PRIMARY KEY,
                source TEXT,
                payload_json TEXT,
                fetched_at TEXT,
                expires_at TEXT
            )
        """)
        set_schema_version(conn, 1)
        current_version = 1

    if current_version < 2:
        logger.info("Running schema migration to version 2")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                ident TEXT PRIMARY KEY,
                created_at TEXT NOT NULL
            )
        """)
        set_schema_version(conn, 2)

    if current_version < 3:
        logger.info("Running schema migration to version 3")
        try:
            conn.execute("ALTER TABLE runways ADD COLUMN le_latitude_deg REAL")
            conn.execute("ALTER TABLE runways ADD COLUMN le_longitude_deg REAL")
            conn.execute("ALTER TABLE runways ADD COLUMN he_latitude_deg REAL")
            conn.execute("ALTER TABLE runways ADD COLUMN he_longitude_deg REAL")
        except sqlite3.OperationalError as e:
            # Column might already exist if schema was partially updated
            logger.warning(f"Migration to v3 warning: {e}")
        set_schema_version(conn, 3)

    if current_version < 4:
        logger.info("Running schema migration to version 4")
        try:
            conn.execute("ALTER TABLE airports ADD COLUMN iata_code TEXT")
            conn.execute("ALTER TABLE airports ADD COLUMN type TEXT")
            
            # Create search indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_airports_ident ON airports(ident)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_airports_name ON airports(name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_airports_city ON airports(city)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_airports_iata ON airports(iata_code)")
        except sqlite3.OperationalError as e:
            logger.warning(f"Migration to v4 warning: {e}")
        set_schema_version(conn, 4)
        current_version = 4

    if current_version < 5:
        logger.info("Running schema migration to version 5")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_sessions (
                token TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ops_log_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                airport_ident TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'General',
                severity TEXT NOT NULL DEFAULT 'Info',
                entry_text TEXT NOT NULL,
                created_by TEXT NOT NULL,
                source_context_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ops_log_airport ON ops_log_entries(airport_ident)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ops_log_created_at ON ops_log_entries(created_at)")
        set_schema_version(conn, 5)

    if current_version < 6:
        logger.info("Running schema migration to version 6")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ops_handoffs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                airport_ident TEXT NOT NULL,
                shift_name TEXT NOT NULL,
                outgoing_operator TEXT,
                incoming_operator TEXT,
                weather_summary TEXT,
                operations_summary TEXT,
                open_items TEXT,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ops_handoffs_airport ON ops_handoffs(airport_ident)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ops_handoffs_created_at ON ops_handoffs(created_at)")
        set_schema_version(conn, 6)

    if current_version < 7:
        logger.info("Running schema migration to version 7")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ops_inspections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                airport_ident TEXT NOT NULL,
                inspection_type TEXT NOT NULL,
                completed_by TEXT,
                checklist_json TEXT NOT NULL,
                notes TEXT,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ops_inspections_airport ON ops_inspections(airport_ident)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ops_inspections_created_at ON ops_inspections(created_at)")
        set_schema_version(conn, 7)

    if current_version < 8:
        logger.info("Running schema migration to version 8")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ops_maintenance_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                airport_ident TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                priority TEXT NOT NULL DEFAULT 'Medium',
                status TEXT NOT NULL DEFAULT 'Open',
                due_date TEXT,
                assigned_to TEXT,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                closed_at TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ops_maint_airport ON ops_maintenance_items(airport_ident)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ops_maint_status ON ops_maintenance_items(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ops_maint_due_date ON ops_maintenance_items(due_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ops_maint_created_at ON ops_maintenance_items(created_at)")
        set_schema_version(conn, 8)

    if current_version < 9:
        logger.info("Running schema migration to version 9")
        admin_user_columns = {
            "operator_mode": "TEXT NOT NULL DEFAULT 'airport'",
            "airport_ident": "TEXT",
            "organization_name": "TEXT",
            "display_name": "TEXT",
            "is_active": "INTEGER NOT NULL DEFAULT 1",
        }
        for column_name, column_definition in admin_user_columns.items():
            try:
                conn.execute(f"ALTER TABLE admin_users ADD COLUMN {column_name} {column_definition}")
            except sqlite3.OperationalError as e:
                # Column may already exist if a previous v9 attempt partially ran.
                logger.warning(f"Migration to v9 warning for admin_users.{column_name}: {e}")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS ops_shared_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                airport_ident TEXT NOT NULL,
                category TEXT NOT NULL,
                affected_asset TEXT,
                severity TEXT NOT NULL,
                visibility TEXT NOT NULL DEFAULT 'shared_airline_station',
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                source_label TEXT NOT NULL DEFAULT 'Airport Ops',
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                cancelled_at TEXT,
                cancelled_by TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ops_shared_alerts_airport ON ops_shared_alerts(airport_ident)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ops_shared_alerts_expires ON ops_shared_alerts(expires_at)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ops_shared_alerts_active "
            "ON ops_shared_alerts(airport_ident, expires_at, cancelled_at)"
        )

        conn.execute("""
            CREATE TABLE IF NOT EXISTS ops_shared_alert_acknowledgements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                acknowledged_at TEXT NOT NULL,
                FOREIGN KEY(alert_id) REFERENCES ops_shared_alerts(id),
                UNIQUE(alert_id, username)
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ops_alert_ack_user "
            "ON ops_shared_alert_acknowledgements(username)"
        )
        set_schema_version(conn, 9)

def seed_default_settings(conn: sqlite3.Connection):
    now = datetime.now(timezone.utc).isoformat()
    defaults = {
        "default_airport": os.environ.get("DEFAULT_AIRPORT", ""),
        "alternate_radius_nm": "75",
        "refresh_interval_seconds": "300",
        "theme_mode": "system",
        "monitor_mode": "0",
        "show_raw_weather_default": "1",
        "accent_color": "blue"
    }
    
    for key, val in defaults.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
            (key, val, now)
        )

def seed_reference_data_from_json(conn: sqlite3.Connection):
    now = datetime.now(timezone.utc).isoformat()
    data_dir = Path(__file__).parent.parent / "data"
    
    # Check if we have already imported from an external source
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM schema_meta WHERE key = 'ref_data_source'")
    row = cursor.fetchone()
    if row and row[0] == "OurAirports":
        logger.info("Database has been imported from OurAirports. Skipping JSON seed to prevent data downgrade.")
        return

    # Simple versioning for reference data
    REF_DATA_VERSION = "1.1.0"
    
    with open(data_dir / "airports_seed.json") as f:
        airports = json.load(f)
    
    with open(data_dir / "runways_seed.json") as f:
        runways = json.load(f)
        
    with open(data_dir / "frequencies_seed.json") as f:
        frequencies = json.load(f)
        
    cursor = conn.cursor()
    
    logger.info(f"Seeding reference data version {REF_DATA_VERSION}...")

    # 1. Seed Airports (Insert or Update if changed)
    for apt in airports:
        icao = apt["icao"]
        cursor.execute("SELECT name, lat, lon, elevation_ft, type FROM airports WHERE ident = ?", (icao,))
        existing = cursor.fetchone()

        if not existing:
            conn.execute(
                "INSERT INTO airports (ident, name, lat, lon, elevation_ft, type, source, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (icao, apt["name"], apt.get("lat"), apt.get("lon"), apt.get("elevation_ft"), apt.get("type"), "seed_json", now)
            )
        else:
            # Update if name, location, or type changed (also backfills NULL type from older seeds)
            type_changed = existing["type"] != apt.get("type")
            if existing["name"] != apt["name"] or abs(existing["lat"] - apt["lat"]) > 0.0001 or abs(existing["lon"] - apt["lon"]) > 0.0001 or type_changed:
                conn.execute(
                    "UPDATE airports SET name = ?, lat = ?, lon = ?, elevation_ft = ?, type = ?, updated_at = ? WHERE ident = ?",
                    (apt["name"], apt["lat"], apt["lon"], apt.get("elevation_ft"), apt.get("type"), now, icao)
                )

    # 2. Seed Runways (Clear and re-seed for simplicity as they aren't user-editable)
    # We only clear runways for airports present in our seed data to avoid wiping external data if any
    seed_airport_idents = list(runways.keys())
    placeholders = ",".join(["?"] * len(seed_airport_idents))
    conn.execute(f"DELETE FROM runways WHERE airport_ident IN ({placeholders})", seed_airport_idents)
    
    for apt_id, rwys in runways.items():
        for rwy in rwys:
            conn.execute(
                "INSERT INTO runways (airport_ident, surface_id, le_heading_deg, le_latitude_deg, le_longitude_deg, he_latitude_deg, he_longitude_deg, length_ft, width_ft, source, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    apt_id, 
                    rwy.get("id"), 
                    rwy.get("heading"),
                    rwy.get("le_latitude_deg"),
                    rwy.get("le_longitude_deg"),
                    rwy.get("he_latitude_deg"),
                    rwy.get("he_longitude_deg"),
                    rwy.get("length_ft"), 
                    rwy.get("width_ft"), 
                    "seed_json", 
                    now
                )
            )

    # 3. Seed Frequencies (Clear and re-seed for simplicity)
    seed_freq_idents = list(frequencies.keys())
    placeholders = ",".join(["?"] * len(seed_freq_idents))
    conn.execute(f"DELETE FROM frequencies WHERE airport_ident IN ({placeholders})", seed_freq_idents)
    
    for apt_id, freqs in frequencies.items():
        for freq in freqs:
            conn.execute(
                "INSERT INTO frequencies (airport_ident, type, frequency_mhz, source, updated_at) VALUES (?, ?, ?, ?, ?)",
                (apt_id, freq.get("type"), freq.get("frequency"), "seed_json", now)
            )

    # Track reference data version and last seed time
    conn.execute("INSERT OR REPLACE INTO schema_meta (key, value, updated_at) VALUES (?, ?, ?)", ("ref_data_version", REF_DATA_VERSION, now))
    conn.execute("INSERT OR REPLACE INTO schema_meta (key, value, updated_at) VALUES (?, ?, ?)", ("last_seeded_at", now, now))

def ensure_reference_data_seeded():
    """External helper to ensure reference data is populated without wiping settings."""
    with get_connection() as conn:
        seed_reference_data_from_json(conn)
        conn.commit()

def init_runtime_db_if_needed():
    ensure_state_dir()
    db_path = get_db_path()
    is_new = not Path(db_path).exists()
    
    logger.info(f"Initializing runtime DB at {db_path}. New: {is_new}")
    
    with get_connection() as conn:
        run_migrations(conn)
        seed_reference_data_from_json(conn)
        seed_default_settings(conn)
        conn.commit()
