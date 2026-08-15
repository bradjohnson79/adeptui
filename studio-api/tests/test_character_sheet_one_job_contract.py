"""One-job Character Sheet contract + ImageIntent metadata + layout stamp."""

from __future__ import annotations

import json

from app.character_identity.four_view_sheet import (
    REQUIRED_VIEWS,
    assess_four_view_layout,
    attach_four_view_sheet_intent,
    is_sheet_tile_request,
    is_single_image_four_view,
)
from app.hosted_providers.adapters.kie_adapter import (
    build_kie_create_task_body,
    strengthen_kie_character_sheet_prompt,
)
from app.image_product.compile import compile_image_request


def test_one_job_sheet_intent_on_compile_metadata():
    body = attach_four_view_sheet_intent(
        {
            "prompt": "Korri in black cloth",
            "purpose": "character_sheet",
            "presetId": "builtin-character-sheet",
            "lockModelFamily": True,
            "modelFamilyPreference": "qwen2512",
        }
    )
    compiled = compile_image_request("proj-sheet", body)
    intent = compiled["imageIntent"]
    meta = intent.get("metadata") or {}
    assert meta["purpose"] == "character_sheet"
    assert meta["layout"] == "four_view"
    assert meta["requiredViews"] == list(REQUIRED_VIEWS)
    assert meta["referenceMode"] == "identity_preservation"


def test_one_job_payload_is_not_a_tile():
    body = attach_four_view_sheet_intent(
        {"purpose": "character_sheet", "role": "hero_identity", "viewRole": "hero_identity"}
    )
    assert is_sheet_tile_request(body) is False
    assert is_single_image_four_view(body) is True


def test_coverage_tile_is_still_a_tile():
    tile = {"purpose": "character_sheet", "role": "full_body_front", "viewRole": "full_body_front"}
    assert is_sheet_tile_request(tile) is True
    assert is_single_image_four_view(tile) is False


def test_single_pose_layout_noncompliant_true(tmp_path):
    from PIL import Image

    tall = tmp_path / "tall.png"
    Image.new("RGB", (512, 1024), (20, 20, 20)).save(tall)
    out = assess_four_view_layout(tall)
    assert out["layoutNoncompliant"] is True
    assert out["compliant"] is False

    square = tmp_path / "square.png"
    Image.new("RGB", (1024, 1024), (20, 20, 20)).save(square)
    unverified = assess_four_view_layout(square)
    assert unverified["layoutNoncompliant"] is False
    assert unverified["verified"] is False


def test_adapters_strengthen_four_view_prompt():
    text = strengthen_kie_character_sheet_prompt("a person", model="nano-banana-2")
    assert "professional four-panel character turnaround sheet" in text
    assert "Do not generate a single standalone character image" in text


def test_seedream_payload_has_required_quality():
    payload = build_kie_create_task_body(
        model="seedream/5-pro-text-to-image",
        prompt="four-panel character turnaround sheet",
        aspect_ratio="1:1",
    )
    assert payload["input"]["quality"] == "basic"
    assert payload["input"]["aspect_ratio"] == "1:1"
    assert payload["input"]["prompt"]
    assert "1920:1080" not in json.dumps(payload)
