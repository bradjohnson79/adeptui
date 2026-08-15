"""Kie image discovery includes official GPT Image 2 and Seedream rows."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from app.hosted_providers import discovery as discovery_mod
from app.hosted_providers.adapters.kie_adapter import kie_image_model_id_for_dock
from app.hosted_providers.model_store import load_catalog


@pytest.fixture()
def isolated_catalog(tmp_path, monkeypatch):
    path = tmp_path / "discovered_models.json"
    monkeypatch.setattr("app.hosted_providers.model_store._STORE_PATH", path)
    yield path


def test_kie_image_catalog_includes_official_models_when_probe_ok(isolated_catalog, monkeypatch):
    monkeypatch.setattr("app.hosted_providers.discovery.get_secret", lambda _name: "test-key")
    probe_ok = AsyncMock(return_value={"valid": True, "message": "ok", "httpStatus": 200})
    monkeypatch.setattr("app.hosted_providers.discovery.probe_kie", probe_ok)
    monkeypatch.setitem(discovery_mod._PROBES, "kie", probe_ok)
    result = asyncio.run(discovery_mod.discover_provider("kie", persist_as_active=True))
    assert result["ok"] is True
    assert result.get("mock") is False
    images = [m for m in result["discovery"]["models"] if m["modality"] == "image"]
    by_id = {m["id"]: m for m in images}
    assert "nano-banana-kie" in by_id
    assert "gpt-image-2-kie" in by_id
    assert "seedream-kie" in by_id
    assert by_id["gpt-image-2-kie"]["providerModelId"] == "gpt-image-2-text-to-image"
    assert by_id["seedream-kie"]["providerModelId"] == "seedream/5-pro-text-to-image"
    assert by_id["gpt-image-2-kie"]["displayName"] == "GPT Image 2"
    assert by_id["seedream-kie"]["displayName"] == "Seedream"
    for mid in ("nano-banana-kie", "gpt-image-2-kie", "seedream-kie"):
        assert by_id[mid]["readiness"] == "Ready"
        assert by_id[mid]["selectable"] is True
    cat = load_catalog()
    ready_ids = {m["id"] for m in cat["models"] if m["modality"] == "image" and m["readiness"] == "Ready"}
    assert {"gpt-image-2-kie", "seedream-kie", "nano-banana-kie"} <= ready_ids


def test_kie_official_model_strings_for_new_docks():
    assert kie_image_model_id_for_dock("gpt-image-2-kie") == "gpt-image-2-text-to-image"
    assert kie_image_model_id_for_dock("seedream-kie") == "seedream/5-pro-text-to-image"
    assert kie_image_model_id_for_dock("gpt-image-2-kie", image_to_image=True) == "gpt-image-2-image-to-image"
    assert kie_image_model_id_for_dock("seedream-kie", image_to_image=True) == "seedream/5-pro-image-to-image"
    assert kie_image_model_id_for_dock("nano-banana-kie") == "nano-banana-2"
    assert kie_image_model_id_for_dock("flux-kie") == "flux"


def test_kie_image_model_id_for_dock_aliases():
    from app.hosted_providers.adapters.kie_adapter import (
        extract_kie_image_url,
        kie_image_model_id_for_dock,
    )

    assert kie_image_model_id_for_dock("nano-banana-kie") == "nano-banana-2"
    assert kie_image_model_id_for_dock("nano-banana") == "nano-banana-2"
    assert kie_image_model_id_for_dock("gpt-image-2-kie") == "gpt-image-2-text-to-image"
    assert kie_image_model_id_for_dock("gpt-image-2") == "gpt-image-2-text-to-image"
    assert kie_image_model_id_for_dock("seedream-kie") == "seedream/5-pro-text-to-image"
    assert kie_image_model_id_for_dock("unknown-dock") is None
    url = extract_kie_image_url(
        {"data": {"state": "success", "resultJson": '{"resultUrls":["https://cdn.example/a.png"]}'}}
    )
    assert url == "https://cdn.example/a.png"


def test_kie_aspect_from_pixels_nearest_enum():
    from app.hosted_providers.adapters.kie_adapter import (
        kie_aspect_from_pixels,
        normalize_kie_aspect,
    )

    assert kie_aspect_from_pixels(1920, 1080) == "16:9"
    assert kie_aspect_from_pixels(1080, 1920) == "9:16"
    assert kie_aspect_from_pixels(1024, 1024) == "1:1"
    assert normalize_kie_aspect("16:9") == "16:9"
    assert normalize_kie_aspect("1920:1080") == "16:9"
    assert normalize_kie_aspect("auto") == "auto"
    assert normalize_kie_aspect(None, width=1920, height=1080) == "16:9"


def test_submit_kie_image_task_surfaces_body_msg(monkeypatch):
    from app.hosted_providers.adapters.kie_adapter import submit_kie_image_task

    class _Resp:
        status_code = 200
        text = '{"code":422,"msg":"aspect_ratio enum invalid"}'

        def json(self):
            return {"code": 422, "msg": "aspect_ratio enum invalid", "data": {}}

    class _Client:
        def __init__(self, **_kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_a):
            return False

        async def post(self, *_a, **_k):
            return _Resp()

    monkeypatch.setattr(
        "app.hosted_providers.adapters.kie_adapter.httpx.AsyncClient",
        _Client,
    )
    out = asyncio.run(
        submit_kie_image_task(
            "test-key",
            model="gpt-image-2-text-to-image",
            prompt="test liveness one frame",
            aspect_ratio="16:9",
        )
    )
    assert out["ok"] is False
    assert out["httpStatus"] == 200
    assert out["taskId"] is None
    assert "httpStatus=200" in out["message"]
    assert "code=422" in out["message"]
    assert "aspect_ratio enum invalid" in out["message"]
