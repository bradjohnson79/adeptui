"""Library asset IDs on cinematic generate must reach compile intent."""

from __future__ import annotations

from app.image_product.compile import compile_image_request
from app.image_studio.contracts import CinematicControls, CinematicGenerateRequest, cinematic_to_image_product_body


def test_cinematic_body_copies_library_reference_asset_ids() -> None:
    req = CinematicGenerateRequest(
        prompt="korri tastes schnick coffee",
        projectId="proj-refs",
        controls=CinematicControls(category="general"),
        referenceAssetIds=["asset-korri", "asset-cup"],
    )
    body = cinematic_to_image_product_body(req)
    assert body["referenceAssetIds"] == ["asset-korri", "asset-cup"]
    assert body["creativeContext"]["reference_image_ids"] == ["asset-korri", "asset-cup"]


def test_compile_merges_reference_asset_ids_into_intent() -> None:
    compiled = compile_image_request(
        "test-ref-compile",
        {
            "prompt": "korri tastes schnick coffee",
            "purpose": "general",
            "referenceAssetIds": ["lib-aaa", "lib-bbb"],
            "lockModelFamily": True,
            "modelFamilyPreference": "zimage",
        },
    )
    intent = compiled["imageIntent"]
    assert "lib-aaa" in intent["referenceIds"]
    assert "lib-bbb" in intent["referenceIds"]
    assert intent["referenceIds"].index("lib-aaa") < intent["referenceIds"].index("lib-bbb")


def test_compile_does_not_drop_unsupported_family_library_refs() -> None:
    compiled = compile_image_request(
        "test-ref-compile-qwen",
        {
            "prompt": "korri tastes schnick coffee",
            "purpose": "general",
            "referenceAssetIds": ["lib-keep"],
            "lockModelFamily": True,
            "modelFamilyPreference": "qwen2512",
        },
    )
    assert "lib-keep" in compiled["imageIntent"]["referenceIds"]
