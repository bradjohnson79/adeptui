"""Comfy catalogue cache must not poison readiness after a failed or empty fetch."""

from __future__ import annotations

import asyncio

import pytest

from app.comfy_client import RUNNING_WITHOUT_HISTORY_STALL_SEC, ComfyClient


def test_i2i_running_without_history_stall_is_not_180s():
    assert RUNNING_WITHOUT_HISTORY_STALL_SEC >= 900.0


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, handler):
        self._handler = handler

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def get(self, url):
        return self._handler(url)


def test_empty_catalogue_is_not_cached(monkeypatch):
    client = ComfyClient("http://127.0.0.1:8188")
    calls = {"n": 0}

    def handler(_url):
        calls["n"] += 1
        return _FakeResponse({})

    monkeypatch.setattr("app.comfy_client.httpx.AsyncClient", lambda **_k: _FakeClient(handler))
    with pytest.raises(RuntimeError, match="empty catalogue"):
        asyncio.run(client.get_object_info())
    assert client._object_info_cache is None
    with pytest.raises(RuntimeError, match="empty catalogue"):
        asyncio.run(client.get_object_info())
    assert calls["n"] == 2


def test_failed_catalogue_does_not_poison_recovery(monkeypatch):
    client = ComfyClient("http://127.0.0.1:8188")
    state = {"mode": "down"}

    def handler(_url):
        if state["mode"] == "down":
            raise RuntimeError("connection refused")
        return _FakeResponse({"LoadImage": {}, "KSampler": {}, "UNETLoader": {}})

    monkeypatch.setattr("app.comfy_client.httpx.AsyncClient", lambda **_k: _FakeClient(handler))
    known = asyncio.run(client._known_node_types())
    assert known is None
    assert client._object_info_cache is None
    state["mode"] = "up"
    known = asyncio.run(client._known_node_types())
    assert known == {"LoadImage", "KSampler", "UNETLoader"}


def test_stale_miss_does_not_keep_empty_cache(monkeypatch):
    client = ComfyClient("http://127.0.0.1:8188")
    client._object_info_cache = {}
    client._object_info_cached_at = 10**9

    def handler(_url):
        return _FakeResponse({"LoadImage": {}, "TextEncodeQwenImageEdit": {}})

    monkeypatch.setattr("app.comfy_client.httpx.AsyncClient", lambda **_k: _FakeClient(handler))
    data = asyncio.run(client.get_object_info())
    assert "LoadImage" in data
    assert "TextEncodeQwenImageEdit" in data


def test_known_types_stay_fail_closed_when_down(monkeypatch):
    client = ComfyClient("http://127.0.0.1:8188")

    def handler(_url):
        raise RuntimeError("timeout")

    monkeypatch.setattr("app.comfy_client.httpx.AsyncClient", lambda **_k: _FakeClient(handler))
    assert asyncio.run(client._known_node_types()) is None
