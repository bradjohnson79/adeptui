"""MiniMax Route A duration is 5 frames at 24 fps — not 5s and not 15s."""

from __future__ import annotations

from app.director_timeline_w46.generation.adapters.minimax_h3_i2v_local import MiniMaxH3I2VLocalAdapter
from app.director_timeline_w46.generation.adapters.minimax_h3_local import MiniMaxH3LocalAdapter
from app.minimax_h3.route_a_adapter import (
    EXPERIMENTAL_DURATION_SEC,
    EXPERIMENTAL_FPS,
    EXPERIMENTAL_LENGTH,
    measured_or_experimental_duration,
)


def test_experimental_duration_is_frames_over_fps():
    assert EXPERIMENTAL_LENGTH == 5
    assert EXPERIMENTAL_FPS == 24.0
    assert abs(EXPERIMENTAL_DURATION_SEC - (5 / 24)) < 1e-9
    assert EXPERIMENTAL_DURATION_SEC < 1.0


def test_adapters_advertise_r2v_and_inspector_max():
    t2v = MiniMaxH3LocalAdapter.capabilities
    i2v = MiniMaxH3I2VLocalAdapter.capabilities
    assert t2v.supportedDurations == []
    assert i2v.supportedDurations == []
    assert t2v.maxDurationSec == 15.0
    assert i2v.maxDurationSec == 15.0
    from app.workflows.h3_ref2v_builder import frames_for_duration
    from app.video_runtime.legal_canvas import snap_h3_timeline_duration

    assert frames_for_duration(8.0) == 192
    snap15 = snap_h3_timeline_duration(15.0)
    assert snap15["ok"] is True
    assert snap15["frames"] == 362
    blob = str(t2v.notes or "")
    assert "Reference-to-Video" in blob
    assert "first-frame" in blob
    assert "15s" in blob


def test_measured_media_wins_over_profile_default():
    assert measured_or_experimental_duration({"durationSeconds": 0.208}) == 0.208
    assert measured_or_experimental_duration({}) == EXPERIMENTAL_DURATION_SEC
    assert measured_or_experimental_duration(None) == EXPERIMENTAL_DURATION_SEC
