"""Tests for live Comfy progress mapping (no stage-ceiling freeze)."""

from __future__ import annotations

from app.video_runtime.progress import (
    ProgressNormalizer,
    extract_progress_state_fraction,
    live_fraction_from_comfy,
    route_a_progress_from_executing,
    route_a_progress_from_step,
)


def test_live_fraction_from_comfy():
    assert live_fraction_from_comfy(0, 20) == 0.0
    assert abs(live_fraction_from_comfy(5, 20) - 0.25) < 1e-9
    assert live_fraction_from_comfy(20, 20) == 1.0
    assert live_fraction_from_comfy(3, 0) == 1.0


def test_progress_normalizer_does_not_clamp_live_encoding_fraction():
    n = ProgressNormalizer(min_interval_sec=0)
    stage, prog = n.map_comfy_message(
        "Encoding motion from the first frame", 0.72, live=True
    )
    assert stage.value == "encoding"
    assert abs(prog - 0.72) < 1e-9


def test_progress_normalizer_coarse_running_not_pinned_mid_bar():
    n = ProgressNormalizer(min_interval_sec=0)
    stage, prog = n.map_comfy_message("running in ComfyUI", 0.15, live=False)
    assert stage.value == "sampling"
    assert abs(prog - 0.15) < 1e-9


def test_progress_normalizer_coarse_running_does_not_invent_percent():
    n = ProgressNormalizer(min_interval_sec=0)
    stage, prog = n.map_comfy_message("running in ComfyUI", 0.0, live=False)
    assert stage.value == "sampling"
    assert prog == 0.0


def test_route_a_executing_floor_is_monotonic():
    prog, label = route_a_progress_from_executing("5", last_live=0.0)
    assert abs(prog - 0.22) < 1e-9
    assert "Encoding" in label
    prog2, _ = route_a_progress_from_executing("5", last_live=0.41)
    assert abs(prog2 - 0.41) < 1e-9


def test_route_a_step_progress_advances_past_encode_floor():
    p0, _ = route_a_progress_from_step(0, 20, last_live=0.22, node="10")
    p1, label = route_a_progress_from_step(10, 20, last_live=p0, node="10")
    p2, _ = route_a_progress_from_step(20, 20, last_live=p1, node="10")
    assert "Sampling step" in label
    assert p1 > p0
    assert p2 > p1
    assert p2 >= 0.80


def test_extract_progress_state_fraction():
    data = {
        "nodes": {
            "10": {"value": 4, "max": 8, "state": "running"},
            "11": {"value": 0, "max": 1, "state": "pending"},
        }
    }
    got = extract_progress_state_fraction(data)
    assert got is not None
    frac, label = got
    assert abs(frac - 0.5) < 1e-9
    assert "10" in label
