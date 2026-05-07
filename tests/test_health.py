from fastapi.testclient import TestClient
from app.main import app
from app.core.disclaimers import ADVISORY_DISCLAIMER

client = TestClient(app)

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["disclaimer"] == ADVISORY_DISCLAIMER
