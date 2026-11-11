"""Provider adapter unit checks that do not contact real services."""
import asyncio
from types import SimpleNamespace

import httpx
import pytest

from app.core.config import settings
from app.services.posting import adapters


class _AccountQuery:
    def __init__(self, account):
        self._account = account

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._account


class _FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"response": {"post_id": 123}}


class _FakeClient:
    def __init__(self, **kwargs):
        self.request = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url, data=None, json=None):
        self.request = {"url": url, "data": data, "json": json}
        return _FakeResponse()


def test_vk_adapter_uses_wall_post(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr(adapters.httpx, "AsyncClient", lambda **kwargs: client)
    monkeypatch.setattr(settings, "VK_ACCESS_TOKEN", "test-token")
    db = SimpleNamespace(query=lambda model: _AccountQuery(SimpleNamespace(username="456")))
    content = SimpleNamespace(body="Demo copy")

    result = asyncio.run(adapters.VKAdapter(db, project_id=1).publish_live(content))

    assert client.request["url"].endswith("/wall.post")
    assert client.request["data"]["owner_id"] == "-456"
    assert client.request["data"]["message"] == "Demo copy"
    assert result == {"id": 123}


def test_provider_errors_redact_configured_secrets(monkeypatch):
    secret = "123456:telegram-test-secret"
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", secret)
    request = httpx.Request("POST", f"https://api.telegram.org/bot{secret}/sendMessage")
    error = httpx.HTTPStatusError(f"provider rejected token {secret}", request=request,
                                  response=httpx.Response(401, request=request))

    message = adapters._safe_error(error)

    assert secret not in message
    assert "[REDACTED]" in message


def test_instagram_live_publish_requires_media_url(monkeypatch):
    monkeypatch.setattr(settings, "IG_ACCESS_TOKEN", "test-token")
    db = SimpleNamespace(query=lambda model: _AccountQuery(SimpleNamespace(username="123456")))
    content = SimpleNamespace(body="Demo copy", meta={})

    with pytest.raises(ValueError, match="media_url"):
        asyncio.run(adapters.InstagramAdapter(db, project_id=1).publish_live(content))
