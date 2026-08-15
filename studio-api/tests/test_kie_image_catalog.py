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
    assert kie_image_model_id_for_dock("flux") is None
    assert kie_image_model_id_for_dock("flux-kie") == "flux"
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


def test_extract_kie_image_url_official_string_result_json():
    from app.hosted_providers.adapters.kie_adapter import extract_kie_image_url

    payload = {
        "code": 200,
        "msg": "success",
        "data": {
            "taskId": "8aa472a0a01bd1f141af2a689df3a12a",
            "state": "success",
            "resultJson": '{"resultUrls":["https://cdn.example/a.png"]}',
            "failCode": None,
            "failMsg": None,
        },
    }
    assert extract_kie_image_url(payload) == "https://cdn.example/a.png"
    assert extract_kie_image_url(payload["data"]) == "https://cdn.example/a.png"
    wrapped = {"ok": True, "state": "success", "payload": payload}
    assert extract_kie_image_url(wrapped) == "https://cdn.example/a.png"


def test_extract_kie_image_url_fail_state_has_no_url():
    from app.hosted_providers.adapters.kie_adapter import (
        extract_kie_image_url,
        kie_fail_message,
    )

    payload = {
        "code": 200,
        "msg": "success",
        "data": {
            "taskId": "abc",
            "state": "fail",
            "resultJson": None,
            "failCode": "422",
            "failMsg": "content policy",
        },
    }
    assert extract_kie_image_url(payload) is None
    msg = kie_fail_message(payload, "abc", "fail")
    assert "abc" in msg
    assert "code=422" in msg
    assert "content policy" in msg
    assert "Traceback" not in msg


def test_kie_poll_timeout_still_generating_message():
    from app.hosted_providers.adapters.kie_adapter import kie_poll_timeout_message

    msg = kie_poll_timeout_message("abc", "generating")
    assert "still generating" in msg
    assert "abc" in msg
    assert "state=generating" in msg
    assert "no image URL" not in msg
    waiting = kie_poll_timeout_message("abc", "waiting")
    assert "still generating" in waiting
    success_empty = kie_poll_timeout_message("abc", "success")
    assert "no image URL" in success_empty
    assert "still generating" not in success_empty


def test_poll_kie_task_fail_state_honest_message(monkeypatch):
    from app.hosted_providers.adapters.kie_adapter import poll_kie_task

    class _Resp:
        status_code = 200
        text = '{"code":200,"msg":"success","data":{"state":"fail","failCode":"422","failMsg":"content policy"}}'

        def json(self):
            return {
                "code": 200,
                "msg": "success",
                "data": {
                    "taskId": "abc",
                    "state": "fail",
                    "resultJson": None,
                    "failCode": "422",
                    "failMsg": "content policy",
                },
            }

    class _Client:
        def __init__(self, **_kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_a):
            return False

        async def get(self, *_a, **_k):
            return _Resp()

    monkeypatch.setattr(
        "app.hosted_providers.adapters.kie_adapter.httpx.AsyncClient",
        _Client,
    )
    out = asyncio.run(poll_kie_task("test-key", "abc"))
    assert out["ok"] is False
    assert out["state"] == "fail"
    assert out["failCode"] == "422"
    assert out["imageUrl"] is None
    assert "code=422" in (out.get("message") or "")
    assert "content policy" in (out.get("message") or "")
    assert "Traceback" not in (out.get("message") or "")

def test_seedream_create_task_requires_quality():
    """docs.kie.ai seedream/5-pro-*-image required: prompt, aspect_ratio, quality (+ image_urls for i2i)."""
    from app.hosted_providers.adapters.kie_adapter import build_kie_create_task_body

    t2i = build_kie_create_task_body(
        model="seedream/5-pro-text-to-image",
        prompt="a cafe storefront",
        aspect_ratio="1:1",
    )
    assert t2i["model"] == "seedream/5-pro-text-to-image"
    assert t2i["input"]["prompt"] == "a cafe storefront"
    assert t2i["input"]["aspect_ratio"] == "1:1"
    assert t2i["input"]["quality"] == "basic"
    assert "input_urls" not in t2i["input"]
    assert "1920:1080" not in str(t2i)

    i2i = build_kie_create_task_body(
        model="seedream/5-pro-image-to-image",
        prompt="keep identity, four-view sheet",
        input_urls=["https://example.com/ref.png"],
        aspect_ratio="16:9",
        quality="high",
    )
    assert i2i["input"]["quality"] == "high"
    assert i2i["input"]["image_urls"] == ["https://example.com/ref.png"]
    assert "input_urls" not in i2i["input"]

    gpt = build_kie_create_task_body(
        model="gpt-image-2-text-to-image",
        prompt="a cafe storefront",
        aspect_ratio="16:9",
    )
    assert "quality" not in gpt["input"]
    assert gpt["input"]["aspect_ratio"] == "16:9"

    gpt_i2i = build_kie_create_task_body(
        model="gpt-image-2-image-to-image",
        prompt="edit",
        input_urls=["https://example.com/ref.png"],
    )
    assert gpt_i2i["input"]["input_urls"] == ["https://example.com/ref.png"]
    assert "image_urls" not in gpt_i2i["input"]
    assert "quality" not in gpt_i2i["input"]

    nano = build_kie_create_task_body(
        model="nano-banana-2",
        prompt="sheet",
        input_urls=["https://example.com/ref.png"],
        aspect_ratio="1:1",
    )
    assert nano["input"]["image_input"] == ["https://example.com/ref.png"]
    assert "quality" not in nano["input"]


def test_four_view_intent_not_applied_to_tiles():
    from app.character_identity.four_view_sheet import (
        FOUR_VIEW_SHEET_PROMPT,
        is_sheet_tile_request,
        is_single_image_four_view,
        strengthen_four_view_prompt,
        four_view_sheet_intent,
        assess_four_view_layout,
    )

    tile = {"purpose": "character_sheet", "role": "hero_identity", "viewRole": "hero_identity"}
    assert is_sheet_tile_request(tile) is True
    assert is_single_image_four_view(tile) is False
    single = {"purpose": "character_sheet", "presetId": "builtin-character-sheet"}
    assert is_single_image_four_view(single) is True
    intent = four_view_sheet_intent()
    assert intent["purpose"] == "character_sheet"
    assert intent["layout"] == "four_view"
    assert intent["requiredViews"] == [
        "full_body_front",
        "full_body_side",
        "full_body_back",
        "head_shoulders_closeup",
    ]
    assert intent["referenceMode"] == "identity_preservation"
    strengthened = strengthen_four_view_prompt("Korri in black cloth")
    assert FOUR_VIEW_SHEET_PROMPT in strengthened
    assert "Korri in black cloth" in strengthened
    composed = assess_four_view_layout(view_count=4, composed=True)
    assert composed["compliant"] is True
    assert composed["layoutNoncompliant"] is False
    one = assess_four_view_layout(view_count=1, composed=False)
    assert one["layoutNoncompliant"] is True
    assert "single pose" in one["note"]

def test_bare_flux_is_not_a_kie_dock():
    from app.hosted_providers.adapters.kie_adapter import (
        is_kie_image_dock,
        kie_image_model_id_for_dock,
    )

    assert kie_image_model_id_for_dock("flux") is None
    assert kie_image_model_id_for_dock("flux-kie") == "flux"
    assert is_kie_image_dock("flux") is False
    assert is_kie_image_dock("flux-kie") is True

