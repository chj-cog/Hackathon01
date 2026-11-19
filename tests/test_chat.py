import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import ollama

client = TestClient(app)


def _patch_transport(monkeypatch, handler):
    real = httpx.AsyncClient

    def factory(*a, **kw):
        kw["transport"] = httpx.MockTransport(handler)
        kw["base_url"] = "http://test"
        return real(*a, **kw)

    monkeypatch.setattr(ollama.httpx, "AsyncClient", factory)


def test_chat_ok(monkeypatch):
    def handler(req):
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "안녕하세요"}})

    _patch_transport(monkeypatch, handler)
    r = client.post("/api/chat", json={"message": "안녕"})
    assert r.status_code == 200
    assert r.json()["reply"] == "안녕하세요"


def test_chat_model_not_found(monkeypatch):
    _patch_transport(monkeypatch, lambda req: httpx.Response(404, json={"error": "model not found"}))
    r = client.post("/api/chat", json={"message": "x", "model": "nope"})
    assert r.status_code == 404
    assert "nope" in r.json()["detail"]


def test_chat_unavailable(monkeypatch):
    def handler(req):
        raise httpx.ConnectError("refused")

    _patch_transport(monkeypatch, handler)
    assert client.post("/api/chat", json={"message": "x"}).status_code == 503


def test_chat_timeout(monkeypatch):
    def handler(req):
        raise httpx.ReadTimeout("slow")

    _patch_transport(monkeypatch, handler)
    assert client.post("/api/chat", json={"message": "x"}).status_code == 504


def test_chat_validation():
    assert client.post("/api/chat", json={"message": ""}).status_code == 422