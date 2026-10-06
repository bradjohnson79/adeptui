"""v1.1 legal canvas, duration fidelity, VRAM viability, 3 Frame honesty."""

from __future__ import annotations

import pytest

from app.production_control.generator_authority import list_create_engines
from app.video_runtime.legal_canvas import (
    SpecFidelityError,
    assert_legal_canvas,
    check_duration,
    list_legal_canvases,
    preflight_spec,
    resolve_legal_canvas,
)
from app.video_runtime.vram_viability import estimate_peak_gb, evaluate
from app.video_runtime.workflow_capabilities import surface_workflow_status
from app.workflows.ltx_25_builder import build_ltx_25_t2v


def test_create_engines_are_single_authority():
    rows = list_create_engines()
    ids = [r["id"] for r in rows]
    assert ids == [
        "auto",
        "minimax-h3",
        "ltx-2.5",
        "seedance-2.0",
        "seedance-2.0-mini",
        "seedance-2.5",
        "fal_kling",
        "fal_veo",
        "fal_runway",
    ]
    assert "ltx" not in ids
    assert "wan" not in ids
    assert "seedance-fal" not in ids


def test_seedance_versions_stay_distinct():
    from app.production_control.video_readiness import canonical_product_id

    assert canonical_product_id("seedance-fal") == "seedance-2.0"
    assert canonical_product_id("fal_seedance_25") == "seedance-2.5"
    assert canonical_product_id("seedance-2.5") == "seedance-2.5"


def test_720p_class_is_1280x704_not_720():
    canvas = resolve_legal_canvas("ltx-2.5", tier="720p", aspect="16:9", surface="t2v")
    assert canvas.width == 1280
    assert canvas.height == 704
    assert canvas.honesty_label == "Native 720p"
    h3 = resolve_legal_canvas("minimax-h3", tier="720p", aspect="16:9", surface="i2v")
    assert (h3.width, h3.height) == (1280, 704)


def test_480p_through_2k_and_no_native_4k():
    assert resolve_legal_canvas("minimax-h3", tier="480p", aspect="16:9").width == 832
    assert resolve_legal_canvas("ltx-2.5", tier="1080p", aspect="16:9").height == 1088
    ltx_2k = resolve_legal_canvas("ltx-2.5", tier="2K", aspect="16:9")
    assert (ltx_2k.width, ltx_2k.height) == (2560, 1440)
    assert ltx_2k.honesty_label == "Native 2K"
    # MiniMax H3: 2K not certified; 4K not native/certified (capability supports2k=False).
    with pytest.raises(SpecFidelityError, match="not certified"):
        resolve_legal_canvas("minimax-h3", tier="2K", aspect="16:9")
    with pytest.raises(SpecFidelityError, match="not native/certified"):
        resolve_legal_canvas("minimax-h3", tier="4K", aspect="16:9")
    with pytest.raises(SpecFidelityError, match="Native 4K"):
        resolve_legal_canvas("ltx-2.5", tier="4K", aspect="16:9")
    rows = list_legal_canvases("ltx-2.5", aspect="16:9", surface="t2v")
    four_k = next(r for r in rows if r["tier"] == "4K")
    assert four_k["available"] is False
    h3_rows = list_legal_canvases("minimax-h3", aspect="16:9", surface="t2v")
    assert next(r for r in h3_rows if r["tier"] == "2K")["available"] is False
    assert next(r for r in h3_rows if r["tier"] == "4K")["available"] is False


def test_illegal_canvas_blocked_no_snap():
    with pytest.raises(SpecFidelityError, match="will not change"):
        assert_legal_canvas("minimax-h3", 1280, 720)
    assert assert_legal_canvas("minimax-h3", 1280, 704) == (1280, 704)


def test_stale_1280x720_maps_to_720p_class_without_snapping_pixels():
    from app.video_runtime.legal_canvas import infer_tier_from_pixels

    assert infer_tier_from_pixels(1280, 720) == "720p"
    assert infer_tier_from_pixels(1280, 704) == "720p"
    canvas = resolve_legal_canvas("minimax-h3", tier="720p", aspect="16:9")
    assert (canvas.width, canvas.height) == (1280, 704)
    with pytest.raises(SpecFidelityError):
        assert_legal_canvas("minimax-h3", 1280, 720)


def test_resolve_scene_dims_keeps_stored_legal_canvas():
    from types import SimpleNamespace

    from app.aspect_fps import resolve_scene_dims

    scene = SimpleNamespace(width=1920, height=1088, aspect_ratio="16:9")
    project = SimpleNamespace(width=1280, height=720)
    assert resolve_scene_dims(project, scene) == (1920, 1088)
    empty_scene = SimpleNamespace(width=0, height=0, aspect_ratio="16:9")
    assert resolve_scene_dims(project, empty_scene) == (1280, 720)
    fallback = SimpleNamespace(width=0, height=0)
    empty_project = SimpleNamespace(width=0, height=0)
    assert resolve_scene_dims(empty_project, fallback) == (1280, 704)


def test_ltx_builder_does_not_silent_snap():
    class Settings:
        ltx_2_5_checkpoint = "x.safetensors"
        ltx_2_5_video_vae = "v.safetensors"
        ltx_2_5_audio_vae = "a.safetensors"
        ltx_2_5_text_encoder = "t.safetensors"

    with pytest.raises(SpecFidelityError):
        build_ltx_25_t2v(Settings(), "e1", "prompt", width=1280, height=720, length_seconds=5.0, fps=24)


def test_ltx_duration_not_padded():
    bad = check_duration("ltx-2.5", 5.0, 24, surface="t2v")
    assert bad["ok"] is False
    assert "8n+1" in bad["message"]
    good = check_duration("ltx-2.5", 121 / 24, 24, surface="t2v")
    assert good["ok"] is True
    assert good["frames"] == 121


def test_three_frame_not_inferred_from_i2v():
    status = surface_workflow_status("ltx-2.5-distilled", "multiFrame")
    assert status["supported"] is False
    assert status["workflowKey"] is None


def test_preflight_blocks_before_queue():
    spec = preflight_spec("ltx-2.5", width=1280, height=720, length_seconds=5.0, fps=24, surface="t2v")
    assert spec["ok"] is False
    assert spec["suggestions"]


def test_viability_does_not_mutate_request():
    result = evaluate("ltx-2.5", width=1280, height=704, fps=24, duration_sec=121 / 24, surface="t2v")
    assert result["mutatesRequest"] is False
    assert result["width"] == 1280
    assert result["height"] == 704
    peak_4k = estimate_peak_gb("ltx-2.5", width=3840, height=2176, frames=121)
    peak_720 = estimate_peak_gb("ltx-2.5", width=1280, height=704, frames=121)
    assert peak_4k > peak_720


def test_retired_certified_leaves_are_not_required():
    from app.video_runtime.certified_registry import get_workflow
    from app.video_runtime.production_gate import reload_production_gate, required_local_keys

    # Retired local video leaves were removed from the certified registry entirely.
    for key in ("ltx.simple_i2v", "ltx.scene", "wan.first_last_frame", "wan.three_frame"):
        assert get_workflow(key) is None, key
    reload_production_gate()
    required = required_local_keys()
    assert "ltx.simple_i2v" not in required
    assert "wan.three_frame" not in required
    assert "ltx_25.t2v" in required


def test_frames_for_scene_does_not_pad():
    from types import SimpleNamespace

    from app.queue_worker import JobQueue

    worker = JobQueue()
    scene = SimpleNamespace(duration_sec=5.0)
    assert worker._frames_for_scene(scene, 24) == 120


def test_hosted_duration_does_not_snap():
    from app.fal_catalog import nearest_duration
    from app.video_runtime.legal_canvas import SpecFidelityError

    assert nearest_duration(5.0, (4, 5, 6, 7, 8), 5) == 5
    with pytest.raises(SpecFidelityError, match="will not change"):
        nearest_duration(5.3, (4, 5, 6, 7, 8), 5)


def test_ltx_25_knowledge_is_not_ltx_local():
    from app.codirector.generator_knowledge.resolver import canonical_profile_id, resolve_profile

    assert canonical_profile_id("ltx-2.5-distilled") == "ltx-2.5"
    assert resolve_profile("ltx-2.5-distilled").workflow.adapterId == "ltx-2.5-distilled"
    # LTX 2.3 (ltx-local) is retired in v1.1 — resolve_profile must NOT map it.
    assert canonical_profile_id("ltx-local") is None
    try:
        resolve_profile("ltx-local")
        raise AssertionError("ltx-local is retired and must not resolve to a profile")
    except Exception as exc:
        assert "GENERATOR_KNOWLEDGE_UNAVAILABLE" in str(exc)
