"""CIS compile must bind library refs as real pixels — never silent txt2img."""

from __future__ import annotations

import pytest

from app.image_product.compile import compile_image_request
from app.image_studio.contracts import CinematicControls, CinematicGenerateRequest, cinematic_to_image_product_body


def test_cinematic_body_stamps_image_i2i_task_type() -> None:
    req = CinematicGenerateRequest(
        prompt="korri tastes schnick coffee",
        projectId="proj-refs",
        modelFamilyPreference="zimage",
        controls=CinematicControls(category="general"),
        referenceAssetIds=["asset-korri"],
    )
    body = cinematic_to_image_product_body(req)
    assert body["taskType"] == "IMAGE_I2I"
    assert body["lockModelFamily"] is True
    assert body["referenceAssetIds"] == ["asset-korri"]
    assert body["authorityReferences"]
    assert body["authorityReferences"][0]["assetId"] == "asset-korri"


def test_cinematic_body_preserves_typed_authority_kinds() -> None:
    req = CinematicGenerateRequest(
        prompt="@Cami in #Corridor",
        projectId="proj-refs",
        modelFamilyPreference="qwen2512",
        controls=CinematicControls(category="general"),
        referenceAssetIds=["cami-id", "corridor-id"],
        authorityReferences=[
            {
                "key": "character:cami-id",
                "kind": "character",
                "assetId": "cami-id",
                "name": "Cami",
                "chip": "@Cami",
            },
            {
                "key": "environment:corridor-id",
                "kind": "environment",
                "assetId": "corridor-id",
                "name": "Corridor",
                "chip": "#Corridor",
            },
        ],
    )
    body = cinematic_to_image_product_body(req)
    kinds = [r["kind"] for r in body["authorityReferences"]]
    assert kinds == ["character", "environment"]
    assert body["taskType"] == "IMAGE_I2I"


def test_compile_zimage_refs_pins_ref_edit() -> None:
    compiled = compile_image_request(
        "test-cis-i2i",
        {
            "prompt": "korri tastes schnick coffee",
            "purpose": "general",
            "referenceAssetIds": ["lib-aaa"],
            "lockModelFamily": True,
            "modelFamilyPreference": "zimage",
            "taskType": "IMAGE_I2I",
        },
    )
    intent = compiled["imageIntent"]
    runtime = compiled["imageRuntime"]
    assert intent["operation"] == "image.edit"
    assert intent["sourceAssetId"] == "lib-aaa"
    assert runtime.get("workflowKey") == "zimage.ref_edit"
    assert (intent.get("metadata") or {}).get("taskType") == "IMAGE_I2I"


def test_compile_qwen2512_single_ref_pins_qwen_ref() -> None:
    compiled = compile_image_request(
        "test-cis-qwen-ref",
        {
            "prompt": "korri tastes schnick coffee",
            "purpose": "general",
            "referenceAssetIds": ["lib-keep"],
            "lockModelFamily": True,
            "modelFamilyPreference": "qwen2512",
            "taskType": "IMAGE_I2I",
        },
    )
    intent = compiled["imageIntent"]
    runtime = compiled["imageRuntime"]
    assert runtime.get("workflowKey") == "qwen2512.ref"
    assert runtime.get("workflowKey") != "qwen2512.txt2img"
    assert "lib-keep" in (intent.get("referenceIds") or [])
    assert (intent.get("metadata") or {}).get("taskType") == "IMAGE_I2I"


def test_compile_qwen2512_dual_char_env_routes_edit_2509_multi() -> None:
    compiled = compile_image_request(
        "test-cis-qwen-dual",
        {
            "prompt": "@Cami walking the #Corridor",
            "purpose": "general",
            "referenceAssetIds": ["cami-id", "corridor-id"],
            "authorityReferences": [
                {
                    "key": "character:cami-id",
                    "kind": "character",
                    "assetId": "cami-id",
                    "name": "Cami",
                    "chip": "@Cami",
                },
                {
                    "key": "environment:corridor-id",
                    "kind": "environment",
                    "assetId": "corridor-id",
                    "name": "Corridor",
                    "chip": "#Corridor",
                },
            ],
            "lockModelFamily": True,
            "modelFamilyPreference": "qwen2512",
            "taskType": "IMAGE_I2I",
        },
    )
    intent = compiled["imageIntent"]
    runtime = compiled["imageRuntime"]
    assert runtime.get("workflowKey") == "qwen_edit_2509.edit"
    assert runtime.get("workflowKey") != "qwen2512.txt2img"
    assert intent.get("sourceAssetId") == "cami-id"
    meta = intent.get("metadata") or {}
    assert meta.get("sceneReferenceAssetId") == "corridor-id"
    bind = meta.get("referenceBinding") or {}
    assert bind.get("strategy") == "qwen_edit_2509.multi_ref"
    assert bind.get("identityAssetId") == "cami-id"
    assert bind.get("sceneAssetId") == "corridor-id"


def test_compile_qwen2512_refs_never_silent_txt2img() -> None:
    compiled = compile_image_request(
        "test-cis-no-t2i",
        {
            "prompt": "two refs must not txt2img",
            "purpose": "general",
            "referenceAssetIds": ["a", "b"],
            "lockModelFamily": True,
            "modelFamilyPreference": "qwen2512",
            "taskType": "IMAGE_I2I",
        },
    )
    key = compiled["imageRuntime"].get("workflowKey")
    assert not str(key).endswith(".txt2img")


def test_compile_illustrious_locked_refs_fail_closed() -> None:
    with pytest.raises(RuntimeError, match="cannot use an attached picture"):
        compile_image_request(
            "test-cis-illustrious-ref",
            {
                "prompt": "locked text-only family with refs",
                "purpose": "general",
                "referenceAssetIds": ["lib-x"],
                "lockModelFamily": True,
                "modelFamilyPreference": "illustrious",
                "taskType": "IMAGE_I2I",
            },
        )


def test_compile_scene_shot_refs_do_not_flip_to_edit() -> None:
    compiled = compile_image_request(
        "test-scene-no-flip",
        {
            "prompt": "wide street at dusk",
            "purpose": "scene_shot",
            "referenceAssetIds": ["lib-ers"],
            "lockModelFamily": True,
            "modelFamilyPreference": "zimage",
        },
    )
    intent = compiled["imageIntent"]
    assert intent["operation"] == "image.generate"
    assert not intent.get("sourceAssetId")
