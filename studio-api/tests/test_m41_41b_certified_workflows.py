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
from app.workflows.wan_builder import build_wan_three_frame_workflow


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
        "ltx.simple_i2v",
        "ltx.scene",
        "ltx.ingredients_ic_lora",
        "wan.first_last_frame",
        "wan.three_frame",
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
        assert required in keys
    wan3 = get_workflow("wan.three_frame")
    assert wan3 is not None
    assert wan3.workflow_id == "WF-WAN-002"
    assert wan3.status in {"Built", "Blocked", "SmokeTested", "Certified"}


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


def test_wan_flf_still_rejects_middle_input():
    wan = get_entry("wan.first_last_frame")
    assert wan is not None
    bad = validate_inputs(wan, ["first_frame", "middle_frame", "prompt"])
    assert "middle_frame" in bad


def test_resolver_wan_three_frame_when_middle_present():
    c = resolve_from_scene_params(
        engine="wan",
        start_asset_id="a",
        middle_asset_id="b",
        end_asset_id="c",
        intent="scene_render",
    )
    assert c.leaf_workflow_key == "wan.three_frame"
    assert c.workflow_id in {"WF-SCENE-001", "WF-WAN-002"}


def test_resolver_ltx_simple_i2v():
    c = resolve_from_scene_params(
        engine="ltx",
        start_asset_id="a",
        intent="scene_render",
    )
    assert c.leaf_workflow_key == "ltx.simple_i2v"


def test_resolver_ltx_25_distilled_selects_ltx_25_i2v():
    c = resolve_from_scene_params(
        engine="ltx",
        start_asset_id="a",
        intent="scene_render",
        generator_id="ltx-2.5-distilled",
    )
    assert c.leaf_workflow_key == "ltx_25.i2v"


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
        ltx_23_checkpoint="ltx-2.3-22b-distilled-fp8.safetensors",
        ltx_25_checkpoint="ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors",
    )
    assert ident["requestedModel"] == "ltx-2.5-distilled"
    assert ident["resolvedRuntimeModel"].startswith("ltx-2.5-")
    assert "minimax" not in ident["videoModel"].lower()


def test_resolver_extend_local_i2v():
    c = resolve_workflow("extend", engine="ltx", present_inputs={"start_frame": True})
    assert c.workflow_key == "video.extend"
    assert c.leaf_workflow_key == "ltx.simple_i2v"


def test_resolver_deferred_upscale_raises():
    with pytest.raises(RuntimeError, match="workflow_deferred|workflow_not_certified"):
        resolve_workflow("scene_render", force_workflow_key="video.upscale")


def test_resolver_blocked_fal_raises():
    with pytest.raises(RuntimeError, match="workflow_not_certified"):
        resolve_workflow("scene_render", force_workflow_key="fal.seedance")


def test_resolver_contract_exposes_wave6_consumer_fields():
    c = resolve_from_scene_params(
        engine="ltx", start_asset_id="a", intent="scene_render"
    )
    d = c.to_dict()
    assert d["workflowId"]
    assert d["workflowVersion"]
    assert d["leafWorkflowKey"] == "ltx.simple_i2v"
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
            workflow_key="ltx.simple_i2v",
            workflow_version="1.0.0",
        )
    assert classify_exception(WorkflowGraphDriftError("WORKFLOW_GRAPH_DRIFT")) == FailureClass.WORKFLOW_GRAPH_DRIFT


def test_wan_three_frame_builder_requires_all_frames():
    with pytest.raises(ValueError):
        build_wan_three_frame_workflow(
            high_noise="h.safetensors",
            low_noise="l.safetensors",
            vae_name="v.safetensors",
            text_encoder="t.safetensors",
            positive="p",
            negative="n",
            width=832,
            height=480,
            length=33,
            fps=16,
            seed=1,
            start_image="a.png",
            middle_image="",
            end_image="c.png",
        )


def test_wan_three_frame_builder_graph_valid():
    wf = build_wan_three_frame_workflow(
        high_noise="h.safetensors",
        low_noise="l.safetensors",
        vae_name="v.safetensors",
        text_encoder="umt5_xxl_fp8_e4m3fn_scaled.safetensors",
        positive="p",
        negative="n",
        width=832,
        height=480,
        length=33,
        fps=16,
        seed=1,
        start_image="a.png",
        middle_image="b.png",
        end_image="c.png",
        segment="start_mid",
    )
    result = validate_comfy_graph(wf, workflow_key="wan.three_frame")
    assert result.valid, result.issues
    fp = compute_fingerprints(
        graph=wf,
        builder_path="app.workflows.wan_builder:build_wan_three_frame_workflow",
        required_nodes=["WanFirstLastFrameToVideo", "LoadImage", "VHS_VideoCombine"],
        required_models=["wan_models"],
    )
    assert fp["graphHash"] and fp["graphHash"].startswith("sha256:")
