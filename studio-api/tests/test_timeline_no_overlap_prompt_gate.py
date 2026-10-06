"""Smoke: touch_batch_config rejects overlapping promptSegments."""
from types import SimpleNamespace
from app.director_timeline_w46.same_track_no_overlap import (
    SameTrackOverlapError,
    assert_prompt_segments_no_overlap,
    audit_master_same_track_overlaps,
    CD_LAYMAN_TRACK_OCCUPIED,
)


def test_cd_layman_has_no_raw_code():
    assert "SAME_TRACK" not in CD_LAYMAN_TRACK_OCCUPIED
    assert "Choose another time range" in CD_LAYMAN_TRACK_OCCUPIED


def test_prompt_patch_logic_mirrors_orchestrator():
    """Same assertion the orchestrator now runs before assigning promptSegments."""
    next_prompts = [
        {"id": "a", "start": 0, "length": 5},
        {"id": "b", "start": 4.9, "length": 5},
    ]
    try:
        assert_prompt_segments_no_overlap(next_prompts, other_segments=[], track="prompt")
        raise AssertionError("expected reject")
    except SameTrackOverlapError as exc:
        assert "SAME_TRACK_OVERLAP" in str(exc)


def test_adjacent_prompts_accepted_with_foreign_batch():
    assert_prompt_segments_no_overlap(
        [{"id": "b", "start": 5, "length": 5}],
        other_segments=[{"id": "a", "start": 0, "length": 5}],
        track="prompt",
    )
