import pytest
from fastapi.testclient import TestClient
from unittest import mock
from app.main import app
from app.core.config import settings

client = TestClient(app)

def test_get_dashboard_remains_public():
    """GET endpoints should remain public even in read-only mode."""
    with mock.patch("app.core.config.settings.PUBLIC_READONLY_MODE", True):
        # We don't need a real airport for this, just checking if it's blocked by the auth layer
        # Actually, let's use a known one if possible, but the route itself shouldn't have the dependency
        response = client.get("/api/airport/KAVP/dashboard")
        # Should not be 403. Might be 404 if data missing, but that's fine for this test.
        assert response.status_code != 403

def test_mutating_endpoint_blocked_in_readonly_no_token():
    """Mutating endpoints should return 403 in read-only mode if no token is provided."""
    with mock.patch("app.core.config.settings.PUBLIC_READONLY_MODE", True):
        with mock.patch("app.core.config.settings.ADMIN_API_TOKEN", "secret-token"):
            response = client.put("/api/settings", json={})
            assert response.status_code == 403
            assert "read-only" in response.json()["detail"].lower()

def test_mutating_endpoint_blocked_in_readonly_invalid_token():
    """Mutating endpoints should return 403 in read-only mode if invalid token is provided."""
    with mock.patch("app.core.config.settings.PUBLIC_READONLY_MODE", True):
        with mock.patch("app.core.config.settings.ADMIN_API_TOKEN", "secret-token"):
            response = client.put("/api/settings", json={}, headers={"X-Admin-Token": "wrong-token"})
            assert response.status_code == 403
            assert "invalid admin token" in response.json()["detail"].lower()

def test_mutating_endpoint_allowed_with_valid_token():
    """Mutating endpoints should work in read-only mode if valid token is provided."""
    # We mock the DB to avoid errors during the actual execution of the endpoint
    with mock.patch("app.core.config.settings.PUBLIC_READONLY_MODE", True):
        with mock.patch("app.core.config.settings.ADMIN_API_TOKEN", "secret-token"):
            with mock.patch("app.api.routes.settings.update_settings") as mock_update:
                mock_update.return_value = {"status": "ok"}
                # We need to mock the dependency check, or just let it pass
                response = client.put("/api/settings", json={"default_airport": "KPHL"}, headers={"X-Admin-Token": "secret-token"})
                # If it reached the endpoint and we mocked update_settings, it should not be 403.
                # Actually, PUT /settings has validation. 
                assert response.status_code != 403

def test_local_mode_allows_mutation_without_token():
    """In local mode (PUBLIC_READONLY_MODE=False), mutations should be allowed without token."""
    with mock.patch("app.core.config.settings.PUBLIC_READONLY_MODE", False):
        # We don't need a token here
        response = client.put("/api/settings", json={"default_airport": "KPHL"})
        assert response.status_code != 403

def test_debug_endpoint_hidden_by_default():
    """Debug endpoints should return 403 if DEBUG_PUBLIC_ENDPOINTS is False."""
    with mock.patch("app.core.config.settings.DEBUG_PUBLIC_ENDPOINTS", False):
        response = client.get("/api/debug/weather/KPHL")
        assert response.status_code == 403
        assert "disabled" in response.json()["detail"].lower()

def test_debug_endpoint_visible_when_enabled():
    """Debug endpoints should be accessible if DEBUG_PUBLIC_ENDPOINTS is True."""
    with mock.patch("app.core.config.settings.DEBUG_PUBLIC_ENDPOINTS", True):
        with mock.patch("app.api.routes.debug.aw_client.get_metar") as mock_metar:
            mock_metar.return_value = []
            with mock.patch("app.api.routes.debug.aw_client.get_taf") as mock_taf:
                mock_taf.return_value = []
                response = client.get("/api/debug/weather/KPHL")
                assert response.status_code == 200

def test_favorites_protection():
    with mock.patch("app.core.config.settings.PUBLIC_READONLY_MODE", True):
        # POST
        response = client.post("/api/favorites/KPHL")
        assert response.status_code == 403
        # DELETE
        response = client.delete("/api/favorites/KPHL")
        assert response.status_code == 403

def test_recent_protection():
    with mock.patch("app.core.config.settings.PUBLIC_READONLY_MODE", True):
        # POST
        response = client.post("/api/recent/KPHL")
        assert response.status_code == 403
        # DELETE single
        response = client.delete("/api/recent/KPHL")
        assert response.status_code == 403
        # DELETE all
        response = client.delete("/api/recent")
        assert response.status_code == 403
