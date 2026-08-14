"""M42 Wave 3 — Image Product Integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.image_product.collections import add_assets, create_collection, list_collections
from app.image_product.compile import compile_image_request
from app.image_product.presets import BUILTIN_PRESETS, apply_preset_to_request, list_presets
from app.image_product.production_gate import evaluate_image_wave3_gate
from app.image_product.prompt_intel import expand_prompt
from app.image_product.recommend import recommend_image_family
from app.image_product.references import bridge_from_asset, create_reference, normalize_ui_refs
from app.image_product.history import append_history, list_history
from app.image_runtime.job_model import ImageJobStage
from app.image_runtime.production_gate import evaluate_image_wave2_gate


def test_builtin_presets_seeded():
    names = {p["name"] for p in BUILTIN_PRESETS}
    for n in (
        "Concept Art",
        "Storyboard",
        "Character Sheet",
        "Environment Sheet",
        "Marketing Artwork",
        "YouTube Thumbnail",
        "Poster",
        "Matte Painting",
    ):
        assert n in names
    presets = list_presets("test-w3-presets")
    assert len(presets) >= 8


def test_recommend_why_and_cost():
    photo = recommend_image_family(prompt="cinematic photorealistic production still", purpose="concept_art")
    assert photo["recommendedFamily"] == "flux"
    assert photo["whyThisModel"]
    assert "estimates" in photo
    assert photo["estimates"]["costLabel"]
    assert photo["overridable"] is True

    anime = recommend_image_family(prompt="anime cel-shaded character", purpose="character_sheet")
    assert anime["recommendedFamily"] == "qwen"

    # Execution falls back to certified zimage when flux not Certified
    assert photo["executionFamily"] == "zimage" or photo["executable"]


def test_prompt_intel_expand():
    info = expand_prompt("hero on bridge", purpose="storyboard", cinematography={"lens": "35mm"})
    assert info["originalPrompt"] == "hero on bridge"
    assert "hero on bridge" in info["expandedPrompt"]
    assert info["expandedPrompt"] != info["originalPrompt"] or info.get("constraints")


def test_compile_no_workflow_preference():
    compiled = compile_image_request(
        "test-w3-compile",
        {
            "prompt": "cinematic still of a bridge at dusk",
            "purpose": "concept_art",
            "aspectRatio": "16:9",
            "modelFamilyPreference": "flux",
        },
    )
    intent = compiled["imageIntent"]
    assert intent["workflowPreference"] is None
    assert compiled["imageRuntime"]["workflowKey"] in {"zimage.txt2img", "flux.txt2img"}
    # Production path: certified only → zimage fallback when flux Deferred
    assert compiled["imageRuntime"]["workflowKey"] == "zimage.txt2img"
    assert compiled["recommendation"]["whyThisModel"]
    assert compiled["recommendation"]["estimates"]["costLabel"]


def test_compile_refs_normalize():
    compiled = compile_image_request(
        "test-w3-refs",
        {
            "prompt": "character sheet front view",
            "purpose": "character_sheet",
            "presetId": "builtin-character-sheet",
            "refs": [{"assetId": "asset-abc", "role": "character"}],
        },
    )
    assert compiled["imageIntent"]["referenceIds"]
    assert compiled["imageRuntime"]["workflowKey"] == "zimage.txt2img"


def test_compile_preserves_spatial_metadata():
    compiled = compile_image_request(
        "test-w3-spatial",
        {
            "prompt": "cinematic alley confrontation",
            "purpose": "storyboard",
            "aspectRatio": "16:9",
            "spatialMapId": "map-42",
            "spatialMapVersion": "2026-08-01T20:00:00Z",
            "spatialCameraId": "cam-hero",
            "creativeContext": {
                "spatial": {
                    "summary": "Environment: rain-slick alley. Camera: Hero Cam, wide, 35mm lens.",
                    "promptHints": [
                        "Environment: rain-slick alley.",
                        "Camera: Hero Cam, wide, 35mm lens.",
                    ],
                }
            },
        },
    )
    intent = compiled["imageIntent"]
    metadata = intent["metadata"]
    assert metadata["spatialMapId"] == "map-42"
    assert metadata["spatialMapVersion"] == "2026-08-01T20:00:00Z"
    assert metadata["spatialCameraId"] == "cam-hero"
    assert "Spatial: Environment: rain-slick alley." in intent["prompt"]


def test_collections_and_references():
    pid = "test-w3-collections"
    cols = list_collections(pid)
    assert len(cols) >= 5
    col = create_collection(pid, "Unit Test Collection", ["a1"])
    updated = add_assets(pid, col["collectionId"], ["a2"])
    assert "a1" in updated["assetIds"] and "a2" in updated["assetIds"]
    ref = create_reference(pid, type="character", display_name="Hero", source_images=["a1"])
    assert ref["referenceId"]
    bridged = bridge_from_asset(pid, asset_id="a9", role="environment")
    assert bridged["type"] == "environment"
    ids = normalize_ui_refs(pid, [{"assetId": "a1", "role": "character"}])
    assert ids


def test_history_persist():
    pid = "test-w3-history"
    append_history(pid, {"jobId": "j1", "prompt": "hello still", "workflowKey": "zimage.txt2img"})
    data = list_history(pid)
    assert data["entries"]
    assert "hello still" in data["prompts"]


def test_apply_preset():
    preset = next(p for p in BUILTIN_PRESETS if p["presetId"] == "builtin-storyboard")
    applied = apply_preset_to_request(preset, subject="wide establishing")
    assert applied["aspectRatio"] == "16:9"
    assert "wide establishing" in applied["prompt"]


def test_image_job_stages_enum():
    stages = [s.value for s in ImageJobStage]
    for required in (
        "Queued",
        "LoadingModels",
        "Sampling",
        "Validating",
        "RegisteringAsset",
        "Completed",
        "Failed",
    ):
        assert required in stages


def test_wave2_preserved():
    g2 = evaluate_image_wave2_gate()
    assert g2.get("wave2Go") is True


def test_no_product_builder_imports():
    root = Path(__file__).resolve().parents[1] / "app" / "image_product"
    banned = ("build_leaf_graph", "from ..comfy", "workflow_execute")
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in banned:
            assert token not in text, f"{path.name} imports builder surface: {token}"


def test_wave3_gate_structure():
    gate = evaluate_image_wave3_gate()
    assert gate["phase"] == "M42-W3"
    assert "wave3Go" in gate
    assert "missingRequirements" in gate
    assert isinstance(gate["missingRequirements"], list)


def test_forced_illustrious_workflow_does_not_silent_fallback_to_zimage(monkeypatch):
    import app.image_runtime.contract as contract

    def boom(*_args, **_kwargs):
        raise RuntimeError("Image workflow not Certified: illustrious.txt2img")

    monkeypatch.setattr(contract, "resolve_image_workflow", boom)
    with pytest.raises(RuntimeError, match="illustrious"):
        compile_image_request(
            "test-w3-force-illustrious",
            {
                "prompt": "anime character sheet",
                "purpose": "character_sheet",
                "modelFamilyPreference": "illustrious",
                "forceWorkflowKey": "illustrious.txt2img",
                "allow_force_workflow_key": True,
                "width": 1024,
                "height": 1024,
            },
        )


def test_forced_zimage_ref_edit_keeps_engine_preference_against_qwen_recommend():
    compiled = compile_image_request(
        "test-w3-force-zimage-ref",
        {
            "prompt": "character sheet from reference",
            "purpose": "character_sheet",
            "modelFamilyPreference": "zimage",
            "lockModelFamily": True,
            "forceWorkflowKey": "zimage.ref_edit",
            "allow_force_workflow_key": True,
            "source_asset_id": "ref-asset-1",
            "width": 1024,
            "height": 1024,
        },
    )
    intent = compiled["imageIntent"]
    runtime = compiled["imageRuntime"]
    assert runtime["workflowKey"] == "zimage.ref_edit"
    assert intent["enginePreference"] == "zimage"
    assert intent["sourceAssetId"] == "ref-asset-1"
