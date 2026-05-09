"""
Session-scoped test database fixture.

Patches settings.STATE_DIR and settings.DB_PATH to a writable temp directory
for the entire pytest session.  This prevents PermissionError when tests spin
up TestClient(app) without their own DB patch — the app lifespan calls
ensure_state_dir() which would otherwise try to create /var/lib/airfieldops.

Tests that need a completely isolated DB (e.g. test_ops.py, test_runtime_db.py,
test_settings.py) apply their own mock.patch inside their fixtures.  Those
inner patches override this session patch while the test runs, and are
restored to the session value when the test finishes.

Production runtime behavior is unchanged: DEFAULT state dir and DB path are
still read from the environment / config at startup; this file only affects
the test session.
"""
import pytest
import tempfile
from pathlib import Path
from unittest import mock


@pytest.fixture(scope="session", autouse=True)
def _session_test_db():
    """
    Redirect all DB and state-dir operations to a writable temp directory
    for the full test session.  Initialises the schema and seeds reference
    data once so tests that use TestClient(app) without their own DB fixture
    see a populated database (KAGC, KPIT, etc.).
    """
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "airfieldops_test.sqlite")

        with mock.patch("app.core.config.settings.STATE_DIR", tmp), \
             mock.patch("app.core.config.settings.DB_PATH", db_path):

            from app.services.runtime_db import init_runtime_db_if_needed
            from app.services.ops_auth import bootstrap_default_admin

            init_runtime_db_if_needed()   # runs migrations + seeds reference data
            bootstrap_default_admin()     # creates default Meeks admin if absent

            yield db_path
