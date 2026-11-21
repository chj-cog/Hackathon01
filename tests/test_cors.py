from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def test_mock_headers_are_exposed_to_allowed_origin(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:8765")
    get_settings.cache_clear()
    try:
        client = TestClient(create_app())
        r = client.get("/health", headers={"Origin": "http://localhost:8765"})
        assert r.headers["access-control-allow-origin"] == "http://localhost:8765"
        exposed = r.headers["access-control-expose-headers"]
        assert "X-Is-Mock" in exposed and "X-Data-Source" in exposed
    finally:
        get_settings.cache_clear()


def test_unlisted_origin_gets_no_cors_headers(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:8765")
    get_settings.cache_clear()
    try:
        client = TestClient(create_app())
        r = client.get("/health", headers={"Origin": "https://evil.example"})
        assert "access-control-allow-origin" not in r.headers
    finally:
        get_settings.cache_clear()
