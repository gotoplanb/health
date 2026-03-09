"""Tests for API and web routers."""

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth.api_key import _valid_keys


def _make_test_client(mock_data_dir: str) -> TestClient:
    """Create a test client with mock mode enabled."""
    with patch.dict("os.environ", {
        "MOCK_MODE": "true",
        "MOCK_AUTH": "true",
        "MOCK_DATA_DIR": mock_data_dir,
        "SESSION_SECRET_KEY": "test-secret",
    }):
        # Re-import to pick up env vars
        import importlib
        import app.config
        importlib.reload(app.config)
        import app.main
        importlib.reload(app.main)
        _valid_keys.clear()
        _valid_keys.add("test-key")
        return TestClient(app.main.app)


class TestHealthEndpoint:
    def test_health(self):
        with TemporaryDirectory() as tmpdir:
            client = _make_test_client(tmpdir)
            resp = client.get("/health")
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}


class TestApiDashboards:
    def test_list_dashboards_empty(self):
        with TemporaryDirectory() as tmpdir:
            Path(tmpdir, "dashboards").mkdir()
            client = _make_test_client(tmpdir)
            resp = client.get("/api/v1/dashboards", headers={"X-API-Key": "test-key"})
            assert resp.status_code == 200
            assert resp.json()["dashboards"] == []

    def test_list_dashboards_requires_api_key(self):
        with TemporaryDirectory() as tmpdir:
            client = _make_test_client(tmpdir)
            resp = client.get("/api/v1/dashboards")
            assert resp.status_code == 401
