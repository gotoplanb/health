"""Tests for auth dependencies."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from app.auth.api_key import _valid_keys, is_valid_api_key
from app.auth.dependencies import require_api_key, require_google_session


class TestIsValidApiKey:
    def test_valid_key(self):
        _valid_keys.clear()
        _valid_keys.add("test-key-123")
        assert is_valid_api_key("test-key-123") is True

    def test_invalid_key(self):
        _valid_keys.clear()
        _valid_keys.add("test-key-123")
        assert is_valid_api_key("wrong-key") is False

    def test_empty_key(self):
        _valid_keys.clear()
        assert is_valid_api_key("") is False


class TestRequireGoogleSession:
    def _make_app(self):
        app = FastAPI()
        app.add_middleware(SessionMiddleware, secret_key="test-secret")

        @app.get("/protected")
        async def protected(user: dict = pytest.importorskip("fastapi").Depends(require_google_session)):
            return {"email": user["email"]}

        return app

    def test_unauthenticated_returns_401(self):
        app = self._make_app()
        client = TestClient(app)
        resp = client.get("/protected")
        assert resp.status_code == 401


class TestRequireApiKey:
    def _make_app(self):
        from app.auth.api_key import _valid_keys
        _valid_keys.clear()
        _valid_keys.add("valid-key")

        app = FastAPI()

        @app.get("/api-protected")
        async def api_protected(key: str = pytest.importorskip("fastapi").Depends(require_api_key)):
            return {"key": key}

        return app

    def test_valid_api_key(self):
        app = self._make_app()
        client = TestClient(app)
        resp = client.get("/api-protected", headers={"X-API-Key": "valid-key"})
        assert resp.status_code == 200

    def test_missing_api_key(self):
        app = self._make_app()
        client = TestClient(app)
        resp = client.get("/api-protected")
        assert resp.status_code == 401

    def test_invalid_api_key(self):
        app = self._make_app()
        client = TestClient(app)
        resp = client.get("/api-protected", headers={"X-API-Key": "bad-key"})
        assert resp.status_code == 401
