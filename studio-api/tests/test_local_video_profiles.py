"""H3 Base Optimized and HunyuanVideo 1.5 Distilled stay distinct from Standard H3 and LTX."""

from __future__ import annotations

from app.director_timeline_w46.generation.registry import get_registry
from app.film_timeline.availability import list_generator_status
from app.film_timeline.h3_fast_renderer import STEPS, build_h3_fast_workflow
from app.video_runtime.local_video_profiles import (
    BO_DEFAULT_STEPS,
    BO_LORA_NAME,
    H3_BO_CONTINUATION_SAFE,
    H3_BO_FRESH_FAST,
    bo_execution_profile,
)
from app.workflows.hunyuan15_distilled_builder import (
    I2V_STEPS,
    I2V_UNET,
    T2V_STEPS,
    T2V_UNET,
    build_hunyuan_distilled_workflow,
    hunyuan_frames,
    hunyuan_size,
)
from app.codirector.durable.bind import requested_engine
from app.codirector.routing.situational_replies import canonical_generator_id


def test_standard_h3_graph_has_no_turbo_lora() -> None:
    graph = build_h3_fast_workflow(
        prompt="Renkoka turns",
        filename_prefix="std",
        seed=1,
        width=1152,
        height=640,
        duration_sec=5,
        image_names=["ref.png"],
    )
    assert all(node["class_type"] != "LoraLoaderModelOnly" for node in graph.values())
    assert graph["7"]["inputs"]["steps"] == STEPS == 20
    assert graph["5"]["inputs"]["model"] == ["1", 0]


def test_base_optimized_graph_adds_lora_and_shorter_steps() -> None:
    graph = build_h3_fast_workflow(
        prompt="Renkoka turns",
        filename_prefix="bo",
        seed=1,
        width=1152,
        height=640,
        duration_sec=5,
        image_names=["ref.png"],
        steps=BO_DEFAULT_STEPS,
        lora_name=BO_LORA_NAME,
    )
    assert graph["18"]["class_type"] == "LoraLoaderModelOnly"
    assert graph["18"]["inputs"]["lora_name"] == BO_LORA_NAME
    assert graph["5"]["inputs"]["model"] == ["18", 0]
    assert graph["7"]["inputs"]["steps"] == 6
    assert BO_DEFAULT_STEPS != 4
    assert graph["6"]["inputs"]["sage_attention"] == "auto"


def test_base_optimized_continuation_uses_the_safe_profile() -> None:
    profile = bo_execution_profile(has_ending_clip=True)
    assert profile["profile"] == H3_BO_CONTINUATION_SAFE
    graph = build_h3_fast_workflow(
        prompt="Renkoka turns",
        filename_prefix="bo-next",
        seed=1,
        width=1728,
        height=736,
        duration_sec=15,
        image_names=["ref.png"],
        video_names=["ending.mp4"],
        video_labels=["Ending"],
        continuation=True,
        steps=BO_DEFAULT_STEPS,
        lora_name=BO_LORA_NAME,
        sage_attention=profile["sageAttention"],
    )
    assert graph["6"]["inputs"]["sage_attention"] == "disabled"
    assert graph["18"]["inputs"]["lora_name"] == BO_LORA_NAME
    assert graph["7"]["inputs"]["steps"] == BO_DEFAULT_STEPS
    fresh = bo_execution_profile(has_ending_clip=False)
    assert fresh == {"profile": H3_BO_FRESH_FAST, "sageAttention": "auto"}


def test_hunyuan_graphs_use_480p_checkpoints_and_skip_sr() -> None:
    t2v = build_hunyuan_distilled_workflow(
        mode="t2v",
        prompt="A quiet alley",
        filename_prefix="hy",
        seed=3,
        width=848,
        height=480,
        duration_sec=5,
    )
    i2v = build_hunyuan_distilled_workflow(
        mode="i2v",
        prompt="She steps forward",
        filename_prefix="hyi",
        seed=3,
        width=848,
        height=480,
        duration_sec=5,
        start_image="start.png",
    )
    classes = {node["class_type"] for node in list(t2v.values()) + list(i2v.values())}
    assert "HunyuanVideo15SuperResolution" not in classes
    assert "LatentUpscaleModelLoader" not in classes
    assert t2v["2"]["inputs"]["unet_name"] == T2V_UNET
    assert "480p" in T2V_UNET and "720p" not in T2V_UNET
    assert i2v["2"]["inputs"]["unet_name"] == I2V_UNET
    assert t2v["8"]["inputs"]["cfg"] == 1
    assert t2v["9"]["inputs"]["steps"] == T2V_STEPS == 50
    assert i2v["9"]["inputs"]["steps"] == I2V_STEPS == 8
    assert t2v["6"]["inputs"]["shift"] == 5
    assert i2v["6"]["inputs"]["shift"] == 7
    assert t2v["7"]["inputs"]["width"] == 848
    assert t2v["15"]["inputs"]["format.codec"] == "auto"
    assert hunyuan_size("16:9") == (848, 480)
    from app.video_runtime.legal_canvas import resolve_legal_canvas

    canvas = resolve_legal_canvas("hunyuan-video-1.5-distilled", tier="720p", aspect="16:9")
    assert (canvas.width, canvas.height, canvas.tier, canvas.honesty_label) == (848, 480, "480p", "480p-class")
    assert hunyuan_frames(5) == 121
    assert i2v["19"]["inputs"]["start_image"] == ["18", 0]


def test_timeline_capabilities_keep_four_local_rows(monkeypatch) -> None:
    monkeypatch.setattr("app.film_timeline.availability._comfy_reachable", lambda: True)
    rows = [row for row in list_generator_status() if row.get("local")]
    labels = [row["label"] for row in rows]
    assert labels[:4] == [
        "MiniMax H3 — Local",
        "MiniMax H3 Base Optimized",
        "LTX 2.5",
        "HunyuanVideo 1.5 Distilled",
    ]
    by_id = {row["id"]: row for row in rows}
    standard = by_id["minimax-h3-i2v-local"]
    optimized = by_id["minimax-h3-base-optimized"]
    ltx = by_id["ltx-2.5-distilled"]
    hunyuan = by_id["hunyuan-video-1.5-distilled"]
    assert standard["supportsReferenceToVideo"] is True
    assert standard["supportsTextToVideo"] is False
    assert optimized["supportsReferenceToVideo"] is True
    assert optimized["supportsTextToVideo"] is False
    assert optimized["supportsStartFrame"] is False
    assert ltx["supportsTextToVideo"] is True
    assert ltx["supportsEndFrame"] is True
    assert hunyuan["supportsTextToVideo"] is True
    assert hunyuan["supportsStartFrame"] is True
    assert hunyuan["supportsEndFrame"] is False
    assert hunyuan["supportsReferenceToVideo"] is False
    registry = get_registry()
    for retired in ("hunyuan-video-1.5-local", "hunyuan", "hunyuan-video-13b-local"):
        try:
            registry.resolve_id(retired)
        except Exception:
            continue
        raise AssertionError(retired)


def test_codirector_phrases_select_the_named_local_model() -> None:
    assert requested_engine("Use H3 Base Optimized.") == "minimax-h3-base-optimized"
    assert requested_engine("Use the faster local H3.") == "minimax-h3-base-optimized"
    assert requested_engine("Use Standard H3.") == "minimax-h3"
    assert requested_engine("Use LTX 2.5.") == "ltx-2.5"
    assert requested_engine("Use HunyuanVideo 1.5 Distilled.") == "hunyuan-video-1.5-distilled"
    assert canonical_generator_id("h3 base optimized") == "minimax-h3-base-optimized"
    assert canonical_generator_id("standard h3") == "minimax-h3-i2v-local"
    assert canonical_generator_id("hunyuanvideo 1.5 distilled") == "hunyuan-video-1.5-distilled"
    assert canonical_generator_id("ltx 2.5") == "ltx-2.5-distilled"
    assert canonical_generator_id("hunyuan") == "hunyuan-video-1.5-local"
