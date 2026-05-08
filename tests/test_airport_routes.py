import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

def test_search_airports(client):
    response = client.get("/api/airports/search?q=KAGC")
    assert response.status_code == 200
    assert len(response.json()) > 0
    assert response.json()[0]["ident"] == "KAGC"

def test_airport_directory(client):
    response = client.get("/api/airport/KAGC/directory")
    assert response.status_code == 200
    data = response.json()
    assert data["icao"] == "KAGC"
    assert "frequencies" in data
