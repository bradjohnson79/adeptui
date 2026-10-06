"""Co-Director Vision is fal-only. No Kie fallback."""

from __future__ import annotations

import asyncio
from pathlib import Path

from PIL import Image

from app.codirector.vision.vision_review import chat_vision, resolve_vision_model
from app.hosted_providers.models import resolve_model_mapping


def test_vision_authority_is_fal_nested_model():
    mapping = resolve_model_mapping("Co-Director Vision", "fal")
    assert mapping is not None
    assert mapping["providerModelId"] == "fal-ai/any-llm/vision"
    assert mapping["nestedModelId"] == "google/gemini-2.5-flash-lite"
    assert resolve_vision_model("gemini-3-pro") == "google/gemini-2.5-flash-lite"
    assert resolve_vision_model("google/gemini-2.5-flash") == "google/gemini-2.5-flash"


def test_chat_vision_missing_fal_key(monkeypatch):
    monkeypatch.setattr("app.secrets_store.get_secret", lambda _name: None)
    result = asyncio.run(chat_vision(instructions="look", parts=[]))
    assert result == {"ok": False, "error": "no_vlm_configured", "reason": "no_vlm_configured"}


def test_chat_vision_never_calls_kie(monkeypatch, tmp_path):
    called = {"kie": 0, "fal": 0, "upload": 0}

    async def _fake_upload(path, _key):
        called["upload"] += 1
        return f"https://fal.media/files/{Path(path).name}"

    async def _fake_run(model_id, args, _key, **_kw):
        called["fal"] += 1
        assert model_id == "fal-ai/any-llm/vision"
        assert args["model"] == "google/gemini-2.5-flash-lite"
        assert str(args["image_url"]).startswith("https://fal.media/")
        return {"output": '{"hair":"blonde","wardrobe":"silver suit"}'}

    async def _fake_kie(*_a, **_k):
        called["kie"] += 1
        raise AssertionError("chat_kie must not run on the Vision path")

    monkeypatch.setattr("app.secrets_store.get_secret", lambda name: "fal-key" if name == "fal_api_key" else None)
    monkeypatch.setattr("app.fal_client.upload_file_to_fal", _fake_upload)
    monkeypatch.setattr("app.fal_client.run_fal_model", _fake_run)
    monkeypatch.setattr("app.hosted_providers.adapters.kie_adapter.chat_kie", _fake_kie)
    front = tmp_path / "front.png"
    Image.new("RGB", (8, 8), (10, 20, 30)).save(front)
    result = asyncio.run(chat_vision(instructions="describe", image_paths=[front]))
    assert result["ok"] is True
    assert result["provider"] == "fal"
    assert result["model"] == "google/gemini-2.5-flash-lite"
    assert "blonde" in result["output"]
    assert called["fal"] == 1
    assert called["upload"] == 1
    assert called["kie"] == 0


def test_chat_vision_fal_single_image_uses_image_url_only(monkeypatch, tmp_path):
    seen: dict[str, object] = {}

    async def _fake_upload(path, _key):
        return f"https://fal.media/files/{Path(path).name}"

    async def _fake_run(_model_id, args, _key, **_kw):
        seen.update(args)
        return {"output": "ok"}

    monkeypatch.setattr("app.secrets_store.get_secret", lambda name: "fal-key" if name == "fal_api_key" else None)
    monkeypatch.setattr("app.fal_client.upload_file_to_fal", _fake_upload)
    monkeypatch.setattr("app.fal_client.run_fal_model", _fake_run)
    front = tmp_path / "front.png"
    Image.new("RGB", (8, 8), (10, 20, 30)).save(front)
    result = asyncio.run(chat_vision(instructions="look", image_paths=[front]))
    assert result["ok"] is True
    assert "image_url" in seen
    assert "image_urls" not in seen


def test_chat_vision_fal_multi_image_uses_image_urls_only(monkeypatch, tmp_path):
    seen: dict[str, object] = {}

    async def _fake_upload(path, _key):
        return f"https://fal.media/files/{Path(path).name}"

    async def _fake_run(_model_id, args, _key, **_kw):
        seen.update(args)
        return {"output": "ok"}

    monkeypatch.setattr("app.secrets_store.get_secret", lambda name: "fal-key" if name == "fal_api_key" else None)
    monkeypatch.setattr("app.fal_client.upload_file_to_fal", _fake_upload)
    monkeypatch.setattr("app.fal_client.run_fal_model", _fake_run)
    paths = []
    for name in ("a", "b", "c", "d"):
        p = tmp_path / f"{name}.png"
        Image.new("RGB", (8, 8), (10, 20, 30)).save(p)
        paths.append(p)
    result = asyncio.run(chat_vision(instructions="look", image_paths=paths))
    assert result["ok"] is True
    assert "image_urls" in seen
    assert "image_url" not in seen
    assert len(seen["image_urls"]) == 4


def test_chat_vision_surfaces_fal_error(monkeypatch, tmp_path):
    async def _fake_upload(_path, _key):
        return "https://fal.media/files/front.png"

    async def _fake_run(*_a, **_k):
        raise RuntimeError("fal submit failed (401): unauthorized model")

    monkeypatch.setattr("app.secrets_store.get_secret", lambda name: "fal-key" if name == "fal_api_key" else None)
    monkeypatch.setattr("app.fal_client.upload_file_to_fal", _fake_upload)
    monkeypatch.setattr("app.fal_client.run_fal_model", _fake_run)
    front = tmp_path / "front.png"
    Image.new("RGB", (8, 8), (10, 20, 30)).save(front)
    result = asyncio.run(chat_vision(instructions="look", image_paths=[front]))
    assert result["ok"] is False
    assert "unauthorized model" in result["error"]
    assert result["error"] != "vlm_error"
    assert result["provider"] == "fal"


def test_run_vision_persists_fal_facts(monkeypatch, tmp_path):
    from app.character_identity import cc_v2

    async def _fake_chat_vision(**_kwargs):
        return {
            "ok": True,
            "output": '{"hair":"light blonde","wardrobe":"metallic silver"}',
            "provider": "fal",
            "model": "google/gemini-2.5-flash-lite",
        }

    monkeypatch.setattr("app.codirector.vision.vision_review.chat_vision", _fake_chat_vision)
    front = tmp_path / "front.png"
    Image.new("RGB", (8, 8), (10, 20, 30)).save(front)
    result = asyncio.run(cc_v2._run_vision([front], "describe"))
    assert result["ok"] is True
    assert result["facts"]["hair"] == "light blonde"
    assert result["provider"] == "fal"
    assert result["model"] == "google/gemini-2.5-flash-lite"
