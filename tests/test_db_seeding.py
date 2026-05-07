import pytest
import sqlite3
import os
from app.services.runtime_db import get_connection, seed_reference_data_from_json, get_db_path

def test_seeding_each_table_independently(tmp_path):
    # Use a temporary database file
    db_file = tmp_path / "test_seeding.sqlite"
    
    # Mock settings.DB_PATH for this test
    import app.services.runtime_db
    original_db_path = app.services.runtime_db.get_db_path
    app.services.runtime_db.get_db_path = lambda: str(db_file)
    
    try:
        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
        
        # 1. Create schema
        from app.services.runtime_db import run_migrations
        run_migrations(conn)
        
        # Ensure tables are empty
        assert conn.execute("SELECT count(*) FROM airports").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM runways").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM frequencies").fetchone()[0] == 0
        
        # 2. Seed
        seed_reference_data_from_json(conn)
        
        # Verify all seeded
        assert conn.execute("SELECT count(*) FROM airports").fetchone()[0] > 0
        assert conn.execute("SELECT count(*) FROM runways").fetchone()[0] > 0
        assert conn.execute("SELECT count(*) FROM frequencies").fetchone()[0] > 0
        
        # 3. Clear only runways and re-seed
        conn.execute("DELETE FROM runways")
        conn.commit()
        assert conn.execute("SELECT count(*) FROM runways").fetchone()[0] == 0
        
        seed_reference_data_from_json(conn)
        assert conn.execute("SELECT count(*) FROM runways").fetchone()[0] > 0
        
    finally:
        app.services.runtime_db.get_db_path = original_db_path
        if db_file.exists():
            os.remove(db_file)
