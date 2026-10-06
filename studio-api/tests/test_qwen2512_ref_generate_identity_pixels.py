"""qwen2512.ref generate-with-reference loads identity pixels, never CRS-as-canvas.

Binding law:
- referenceIds / referenceImage = identity (CRS)
- sourceAssetId stays null on generate-with-reference
- worker loads pixels from identity refs; adapter accepts them as reference_image
- no source + no reference still errors
- zimage.ref_edit must not steal CRS as the edit canvas
"""

from __future__ import annotations

import pytest

from app.config import settings
from app.image_runtime.intent import ImageIntent
from app.image_runtime.ref_generate_pixels import (
    choose_imagegen_pixel_asset,
    identity_refs_from_intent,
    is_certified_ref_generate,
)
from app.image_runtime.workflow_execute import build_leaf_graph

CRS = "b6ab91dd-9d0a-4e4b-98b4-b26d268950dc"


def _generate_intent(*, reference_ids=None, source_asset_id=None) -> ImageIntent:
    return ImageIntent(
        projectId="proj-identity-pin",
        operation="image.generate",
        purpose="scene_shot_final",
        prompt="Korri in the clearing",
        referenceIds=list(reference_ids or []),
        sourceAssetId=source_asset_id,
        enginePreference="qwen2512",
    )


def test_qwen2512_ref_is_certified_ref_generate() -> None:
    assert is_certified_ref_generate("qwen2512.ref") is True
    assert is_certified_ref_generate("zimage.ref_edit") is False
    assert is_certified_ref_generate("qwen2512.txt2img") is False


def test_generate_reference_ids_crs_source_null_loads_identity_not_source() -> None:
    intent = _generate_intent(reference_ids=[CRS], source_asset_id=None)
    ref_ids, ref_image = identity_refs_from_intent(intent, {})
    choice = choose_imagegen_pixel_asset(
        workflow_key="qwen2512.ref",
        source_asset_id=intent.sourceAssetId,
        reference_ids=ref_ids,
        reference_image=ref_image,
    )
    assert choice.is_ref_generate is True
    assert choice.load_asset_id == CRS
    assert choice.source_asset_id is None
    assert intent.sourceAssetId is None
    assert choice.missing_required_pixels is False


def test_generate_reference_image_param_loads_identity_without_writing_source() -> None:
    intent = _generate_intent(reference_ids=[], source_asset_id=None)
    ref_ids, ref_image = identity_refs_from_intent(
        intent, {"referenceImage": CRS}
    )
    choice = choose_imagegen_pixel_asset(
        workflow_key="qwen2512.ref",
        source_asset_id=intent.sourceAssetId,
        reference_ids=ref_ids,
        reference_image=ref_image,
    )
    assert choice.load_asset_id == CRS
    assert choice.source_asset_id is None
    assert intent.sourceAssetId is None


def test_generate_no_source_no_reference_still_errors() -> None:
    intent = _generate_intent(reference_ids=[], source_asset_id=None)
    ref_ids, ref_image = identity_refs_from_intent(intent, {})
    choice = choose_imagegen_pixel_asset(
        workflow_key="qwen2512.ref",
        source_asset_id=intent.sourceAssetId,
        reference_ids=ref_ids,
        reference_image=ref_image,
    )
    assert choice.missing_required_pixels is True
    assert choice.load_asset_id is None
    assert choice.source_asset_id is None
    assert intent.sourceAssetId is None
    with pytest.raises(RuntimeError, match="requires a source/reference image"):
        build_leaf_graph(
            {"workflowKey": "qwen2512.ref"},
            settings=settings,
            prompt="empty",
            reference_image=None,
            source_image=None,
        )


def test_adapter_receives_identity_pixels_without_source_image() -> None:
    graph = build_leaf_graph(
        {"workflowKey": "qwen2512.ref"},
        settings=settings,
        prompt="same character, new scene",
        reference_image="crs_identity.png",
        source_image=None,
    )
    load = next(n for n in graph.values() if n.get("class_type") == "LoadImage")
    assert load["inputs"]["image"] == "crs_identity.png"


def test_zimage_ref_edit_does_not_steal_crs_as_canvas() -> None:
    choice = choose_imagegen_pixel_asset(
        workflow_key="zimage.ref_edit",
        source_asset_id=None,
        reference_ids=[CRS],
        reference_image=CRS,
    )
    assert choice.is_ref_generate is False
    assert choice.load_asset_id is None
    assert choice.source_asset_id is None


def test_real_canvas_source_is_kept_and_not_replaced_by_crs() -> None:
    canvas = "prior-canvas-asset"
    intent = _generate_intent(reference_ids=[CRS], source_asset_id=canvas)
    choice = choose_imagegen_pixel_asset(
        workflow_key="qwen2512.ref",
        source_asset_id=intent.sourceAssetId,
        reference_ids=intent.referenceIds,
        reference_image=None,
    )
    assert choice.load_asset_id == canvas
    assert choice.source_asset_id == canvas
    assert choice.source_asset_id != CRS
    assert intent.sourceAssetId == canvas
