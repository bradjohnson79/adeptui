"""LTX 2.5 builder kwargs and preflight start-frame fail-close.

No live Comfy.
"""
from __future__ import annotations

from app.config import settings
from app.director_timeline_w46.contracts import (
    BatchBlock,
    DurationState,
    SceneTimelineMaster,
    TimelinePromptSegment,
    TimelineVisualAnchor,
)
from app.director_timeline_w46.orchestrator import run_preflight
from app.video_runtime.workflow_execute import build_leaf_graph
from app.video_runtime.workflow_resolver import resolve_from_scene_params


def _ltx25_contract():
    contract = resolve_from_scene_params(
        engine="ltx-2.5",
        start_asset_id="asset-start-frame",
        intent="scene_render",
        generator_id="ltx-2.5-distilled",
    )
    assert contract.leaf_workflow_key == "ltx_25.i2v"
    return contract


def test_build_leaf_graph_accepts_adapter_lora_kwargs_for_ltx25():
    contract = _ltx25_contract()
    graph = build_leaf_graph(
        contract,
        settings=settings,
        positive="a still camera on a rain-lit street",
        negative="",
        width=1280,
        height=704,
        length=121,
        fps=24,
        seed=11,
        start_image="start.png",
        steps=8,
        filename_prefix="studio/ltx_i2v_test",
        lora_name=None,
        lora_strength=0.8,
    )
    classes = {n["class_type"] for n in graph.values()}
    assert "LTXVImgToVideo" in classes


def test_build_leaf_graph_applies_turbo_lora_when_requested():
    contract = _ltx25_contract()
    graph = build_leaf_graph(
        contract,
        settings=settings,
        positive="a still camera on a rain-lit street",
        negative="",
        width=1280,
        height=704,
        length=121,
        fps=24,
        seed=11,
        start_image="start.png",
        steps=8,
        filename_prefix="studio/ltx_i2v_test",
        turbo_lora=True,
    )
    classes = {n["class_type"] for n in graph.values()}
    assert "LoraLoaderModelOnly" in classes


def _master(generator_id: str, *, start_id: str | None = None, prompt: str = "walk") -> SceneTimelineMaster:
    anchors = []
    if start_id:
        anchors.append(TimelineVisualAnchor(kind="image", assetId=start_id, label="start"))
    return SceneTimelineMaster(
        mode="video_finishing",
        batchBlocks=[
            BatchBlock(
                id="bb_test_ltx",
                sceneId="sc_test",
                order=0,
                label="Batch 1",
                generatorId=generator_id,
                duration=DurationState(plannedDuration=5.0),
                sourceAnchors=anchors,
                promptSegments=[
                    TimelinePromptSegment(text=prompt, productionPrompt=prompt, start=0.0, length=5.0)
                ],
            )
        ],
    )


def test_preflight_ltx_25_i2v_with_start_is_not_blocked():
    findings = run_preflight(_master("ltx-2.5-distilled", start_id="0dc48b4c-a8ae-49fa-bf14-3626db6fdc7a"))
    assert not any(f.get("code") == "empty_required_start_frame" for f in findings)


def test_preflight_minimax_seedance_kling_do_not_require_start_frame():
    for gen_id in ("minimax-h3-t2v-local", "seedance-api", "kling-api"):
        findings = run_preflight(_master(gen_id))
        assert not any(f.get("code") == "empty_required_start_frame" for f in findings)
        start_errors = [f for f in findings if "start" in str(f.get("code") or "").lower() and f.get("severity") == "error"]
        assert start_errors == []
