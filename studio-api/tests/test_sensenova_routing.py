"""SenseNova routing stays on native CRS/ERS. Flux/Qwen stay on 4-view / qwen2512.ref."""

from app.character_identity.visual_sheet import (
    _build_stage1_route,
    _reference_workflow_key,
    _txt2img_workflow_key,
)
from app.image_core.capability import i2i_workflow_key
from app.image_product.compile import _ERS_I2I_WORKFLOW_KEYS
from app.image_product.resolve import resolve_image_capability
from app.config import settings
from app.image_runtime.workflow_execute import build_leaf_graph


def test_character_creator_sensenova_uses_native_crs() -> None:
    assert _txt2img_workflow_key("sensenova") == "sensenova.crs"
    assert _reference_workflow_key("sensenova") == "sensenova.crs"
    route = _build_stage1_route(
        family="sensenova",
        reference_asset_id=None,
        provider_kind="local",
    )
    assert route["workflowKey"] == "sensenova.crs"
    ref = _build_stage1_route(
        family="sensenova",
        reference_asset_id="asset-1",
        provider_kind="local",
    )
    assert ref["workflowKey"] == "sensenova.crs"
    assert ref["source_asset_id"] == "asset-1"


def test_flux_and_qwen_crs_keys_unchanged() -> None:
    assert _txt2img_workflow_key("flux") == "flux.txt2img"
    assert _txt2img_workflow_key("qwen2512") == "qwen2512.txt2img"


def test_ers_i2i_keys_include_sensenova_without_stealing_qwen() -> None:
    assert "sensenova.ers" in _ERS_I2I_WORKFLOW_KEYS
    assert "qwen2512.ref" in _ERS_I2I_WORKFLOW_KEYS
    assert i2i_workflow_key("sensenova", purpose="environment_reference_sheet") == "sensenova.ers"
    assert i2i_workflow_key("qwen2512", purpose="environment_reference_sheet") == "qwen2512.ref"


def test_resolve_pins_sensenova_ers_when_pixels_exist() -> None:
    cap = resolve_image_capability(
        {
            "purpose": "environment_reference_sheet",
            "modelFamilyPreference": "sensenova",
            "sourceAssetId": "atlas-1",
            "source": "local",
        }
    )
    assert cap.get("canExecute") is True
    assert cap.get("workflowKey") == "sensenova.ers"


def test_resolve_still_refuses_t2i_ers() -> None:
    cap = resolve_image_capability(
        {
            "purpose": "environment_reference_sheet",
            "modelFamilyPreference": "sensenova",
            "source": "local",
        }
    )
    assert cap.get("canExecute") is False


def test_execute_dispatches_sensenova_crs() -> None:
    graph = build_leaf_graph(
        {"workflowKey": "sensenova.crs"},
        settings=settings,
        prompt="native sheet",
        negative="",
        width=2720,
        height=1536,
        seed=3,
        steps=50,
        cfg=4.0,
    )
    types = {node["class_type"] for node in graph.values()}
    assert "SenseNovaU1LocalLoader" in types
    assert "KSampler" not in types
