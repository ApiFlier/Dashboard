import pytest
import sqlite3
from unittest import mock
from app.services.airport_data import search_airports


@pytest.fixture
def test_db(tmp_path):
    db_path = tmp_path / "test_search.sqlite"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE airports (
            ident TEXT PRIMARY KEY,
            name TEXT,
            iata_code TEXT,
            type TEXT,
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

    airports = [
        ('KLAX', 'Los Angeles International Airport', 'LAX', 'large_airport', 'Los Angeles', 'CA', 'US', 33.94, -118.40, 125, 'test', 'now'),
        ('KJFK', 'John F. Kennedy International Airport', 'JFK', 'large_airport', 'New York', 'NY', 'US', 40.63, -73.77, 13, 'test', 'now'),
        ('KAGC', 'Allegheny County Airport', 'AGC', 'medium_airport', 'Pittsburgh', 'PA', 'US', 40.35, -79.93, 1252, 'test', 'now'),
        ('KPIT', 'Pittsburgh International Airport', 'PIT', 'large_airport', 'Pittsburgh', 'PA', 'US', 40.49, -80.23, 1203, 'test', 'now'),
        ('KAVP', 'Wilkes-Barre Scranton Intl', 'AVP', 'large_airport', 'Wilkes-Barre', 'PA', 'US', 41.33, -75.72, 962, 'test', 'now'),
    ]

    cursor.executemany("INSERT INTO airports VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", airports)
    conn.commit()
    conn.close()
    return str(db_path)


@pytest.fixture(autouse=True)
def _use_test_db(test_db):
    """
    Point settings.DB_PATH at the isolated test_db for every test in this
    module.  monkeypatch.setenv("AIRFIELDOPS_DB_PATH", ...) has no effect
    because settings.DB_PATH is a class attribute fixed at import time.
    """
    with mock.patch("app.core.config.settings.DB_PATH", test_db):
        yield


def test_exact_ident_match_ranks_first(test_db):
    results = search_airports("KLAX")
    assert len(results) > 0
    assert results[0]["ident"] == "KLAX"
    assert results[0]["rank"] == 1


def test_iata_match_works(test_db):
    results = search_airports("LAX")
    assert len(results) > 0
    assert results[0]["ident"] == "KLAX"
    assert results[0]["iata_code"] == "LAX"
    assert results[0]["rank"] == 2


def test_city_search_works(test_db):
    results = search_airports("Pittsburgh")
    idents = [r["ident"] for r in results]
    assert "KAGC" in idents
    assert "KPIT" in idents


def test_search_limit(test_db):
    results = search_airports("K", limit=2)
    assert len(results) == 2


def test_display_label_format(test_db):
    results = search_airports("KLAX")
    assert results[0]["display_label"] == "KLAX (LAX) Los Angeles International Airport - Los Angeles, CA"
