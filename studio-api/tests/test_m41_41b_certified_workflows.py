"""M41 4.1B — Certified Workflow Library unit tests."""

from __future__ import annotations

import pytest

from app.video_runtime.certified_registry import (
    get_workflow,
    list_workflows,
    production_ready_keys,
    reload_registry,
)
from app.video_runtime.compatibility_registry import get_entry, reload_catalog, validate_inputs
from app.video_runtime.failures import classify_exception
from app.video_runtime.fingerprints import (
    WorkflowGraphDriftError,
    assert_no_graph_drift,
    compute_fingerprints,
    graph_hash,
)
from app.video_runtime.graph_validation import validate_comfy_graph
from app.video_runtime.job_model import FailureClass
from app.video_runtime.workflow_resolver import resolve_from_scene_params, resolve_workflow
from app.workflows.ltx_25_builder import build_ltx_25_i2v, build_ltx_25_t2v


@pytest.fixture(autouse=True)
def _reload():
    reload_registry()
    reload_catalog()
    yield
    reload_registry()
    reload_catalog()


def test_certified_registry_has_production_pipeline_ids():
    keys = {w.workflow_key for w in list_workflows()}
    for required in {
        "ltx_25.t2v",
        "ltx_25.i2v",
        "director.shot_render",
        "director.scene_render",
        "director.timeline_render",
        "director.batch_timeline",
        "video.extend",
        "lipsync.latentsync",
        "fal.seedance",
        "video.upscale",
        "video.motion_transfer",
    }:
        assert required in keys, f"missing {required}"
    # Retired local video leaves were removed from the certified registry entirely.
    for removed in (
        "ltx.simple_i2v",
        "ltx.scene",
        "ltx.ingredients_ic_lora",
        "wan.first_last_frame",
        "wan.three_frame",
    ):
        assert get_workflow(removed) is None, removed


def test_no_false_production_ready_without_cert_record():
    """Honesty: Built/Blocked must not claim Production Ready."""
    for w in list_workflows():
        if w.status != "Certified":
            assert w.is_production_ready is False
    # Until live cert harness promotes, production_ready_keys may be empty
    for key in production_ready_keys():
        wf = get_workflow(key)
        assert wf is not None
        assert wf.certification_record is not None


def test_compatibility_projection_defers_upscale():
    entry = get_entry("video.upscale")
    assert entry is not None
    assert entry.capability_state == "deferred"


def test_wan_flf_is_absent_from_compatibility_catalog():
    wan = get_entry("wan.first_last_frame")
    assert wan is None


def test_resolver_wan_three_frame_when_middle_present():
    with pytest.raises(RuntimeError, match="RETIRED_LOCAL_GENERATOR|workflow_retired"):
        resolve_from_scene_params(
            engine="wan",
            start_asset_id="a",
            middle_asset_id="b",
            end_asset_id="c",
            intent="scene_render",
        )


def test_resolver_ltx_simple_i2v():
    with pytest.raises(RuntimeError, match="RETIRED_LOCAL_GENERATOR|workflow_retired"):
        resolve_from_scene_params(
            engine="ltx",
            start_asset_id="a",
            intent="scene_render",
        )


def test_resolver_ltx_25_distilled_selects_ltx_25_i2v():
    c = resolve_from_scene_params(
        engine="ltx",
        start_asset_id="a",
        intent="scene_render",
        generator_id="ltx-2.5-distilled",
    )
    assert c.leaf_workflow_key == "ltx_25.i2v"


def test_resolver_ltx_25_never_swaps_to_ingredients():
    c = resolve_from_scene_params(
        engine="ltx",
        start_asset_id="a",
        intent="scene_render",
        generator_id="ltx-2.5-distilled",
        wants_ingredients=True,
    )
    assert c.leaf_workflow_key == "ltx_25.i2v"
    disclosure_text = " ".join(c.disclosures)
    assert "Ingredients IC-LoRA (LTX 2.3) is retired" in disclosure_text
    assert "LTX 2.5 keeps character and place references" in disclosure_text


def test_resolver_ltx_25_without_start_selects_t2v():
    from app.video_runtime.workflow_resolver import _leaf_for_scene

    key, _ = _leaf_for_scene(
        engine="ltx",
        has_start=False,
        has_middle=False,
        has_end=False,
        has_audio=False,
        wants_ingredients=False,
        paid_fal=False,
        fal_engine=None,
        generator_id="ltx-2.5-full",
    )
    assert key == "ltx_25.t2v"


def test_local_video_identity_never_uses_minimax_for_ltx():
    from app.video_runtime.workflow_resolver import local_video_identity

    ident = local_video_identity(
        requested_model="ltx-2.5-distilled",
        leaf_workflow_key="ltx_25.i2v",
        ltx_25_checkpoint="ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors",
    )
    assert ident["requestedModel"] == "ltx-2.5-distilled"
    assert ident["resolvedRuntimeModel"].startswith("ltx-2.5-")
    assert "minimax" not in ident["videoModel"].lower()


def test_resolver_extend_uses_ltx_25_i2v():
    contract = resolve_workflow("extend", engine="ltx", present_inputs={"start_frame": True}, generator_id="ltx-2.5-distilled")
    assert contract.leaf_workflow_key == "ltx_25.i2v"
    assert contract.intent == "extend"


def test_resolver_deferred_upscale_raises():
    with pytest.raises(RuntimeError, match="workflow_deferred|workflow_not_certified"):
        resolve_workflow("scene_render", force_workflow_key="video.upscale")


def test_resolver_blocked_fal_raises():
    with pytest.raises(RuntimeError, match="workflow_not_certified"):
        resolve_workflow("scene_render", force_workflow_key="fal.seedance")


def test_resolver_contract_exposes_wave6_consumer_fields():
    c = resolve_from_scene_params(
        engine="ltx",
        start_asset_id="a",
        intent="scene_render",
        generator_id="ltx-2.5-distilled",
    )
    d = c.to_dict()
    assert d["workflowId"]
    assert d["workflowVersion"]
    assert d["leafWorkflowKey"] == "ltx_25.i2v"
    assert d["leafWorkflowVersion"]
    assert d.get("provider") or d.get("provider_kind")
    assert isinstance(d["requiredInputs"], list)
    assert "supported" in d["cancellationPolicy"]
    assert "supportedOutputs" in d["outputContract"]
    assert d.get("concurrencyClass") or d.get("concurrency_class")


def test_fingerprint_drift_detected():
    # Structural drift (node class change) — volatile image names are redacted by design
    g1 = {"1": {"class_type": "LoadImage", "inputs": {"image": "a.png"}}}
    g2 = {"1": {"class_type": "SaveVideo", "inputs": {"image": "a.png"}}}
    h1 = graph_hash(g1)
    assert graph_hash(g1) == graph_hash(
        {"1": {"class_type": "LoadImage", "inputs": {"image": "other.png"}}}
    )
    with pytest.raises(WorkflowGraphDriftError):
        assert_no_graph_drift(
            built_graph=g2,
            expected_graph_hash=h1,
            workflow_key="ltx_25.i2v",
            workflow_version="1.0.0",
        )
    assert classify_exception(WorkflowGraphDriftError("WORKFLOW_GRAPH_DRIFT")) == FailureClass.WORKFLOW_GRAPH_DRIFT


def test_ltx_25_t2v_builder_graph_valid():
    from types import SimpleNamespace

    settings = SimpleNamespace(
        ltx_2_5_checkpoint="c.safetensors",
        ltx_2_5_video_vae="v.safetensors",
        ltx_2_5_text_encoder="t.safetensors",
        ltx_2_5_audio_vae="a.safetensors",
    )
    wf = build_ltx_25_t2v(
        settings=settings,
        execution_id="e1",
        prompt="a cinematic shot",
        negative_prompt="",
        width=1280,
        height=704,
        length_seconds=121 / 24,
        fps=24,
        seed=1,
    )
    classes = {n["class_type"] for n in wf.values()}
    assert "UNETLoader" in classes
    assert "CLIPTextEncode" in classes
    assert "SaveVideo" in classes


def test_ltx_25_i2v_builder_requires_start_image():
    from types import SimpleNamespace

    settings = SimpleNamespace(
        ltx_2_5_checkpoint="c.safetensors",
        ltx_2_5_video_vae="v.safetensors",
        ltx_2_5_text_encoder="t.safetensors",
        ltx_2_5_audio_vae="a.safetensors",
    )
    wf = build_ltx_25_i2v(
        settings=settings,
        execution_id="e1",
        prompt="a cinematic shot",
        negative_prompt="",
        start_image_path="start.png",
        width=1280,
        height=704,
        length_seconds=121 / 24,
        fps=24,
        seed=1,
    )
    classes = {n["class_type"] for n in wf.values()}
    assert "LoadImage" in classes
    assert "LTXVImgToVideo" in classes
    assert "SaveVideo" in classes
    guided = build_ltx_25_i2v(
        settings=settings,
        execution_id="e2",
        prompt="she turns toward camera",
        negative_prompt="",
        start_image_path="start.png",
        end_image_path="end.png",
        width=1280,
        height=704,
        length_seconds=97 / 24,
        fps=24,
        seed=1,
        generate_audio=True,
    )
    guided_nodes = list(guided.values())
    guided_classes = {node["class_type"] for node in guided_nodes}
    assert "LTXVAddGuide" in guided_classes
    assert "LTXVCropGuides" in guided_classes
    assert "LTXVPreprocess" in guided_classes
    assert "LTXVImgToVideoInplace" not in guided_classes
    assert "LTXVDualCFGGuider" in guided_classes
    assert "STGGuiderNode" not in guided_classes
    indexes = [
        node["inputs"]["frame_idx"]
        for node in guided_nodes
        if node["class_type"] == "LTXVAddGuide"
    ]
    assert indexes == [0, -1]
    reload_registry()
    guided_check = validate_comfy_graph(guided, workflow_key="ltx_25.i2v")
    assert guided_check.valid, guided_check.issues
    start_only_check = validate_comfy_graph(wf, workflow_key="ltx_25.i2v")
    assert start_only_check.valid, start_only_check.issues
