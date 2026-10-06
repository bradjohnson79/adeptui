"""CLEAR P2+ — Execution Window planning + two-tier Timed Prompt projection."""

from __future__ import annotations

from types import SimpleNamespace

from app.codirector.production.contracts import SceneBeat, TimedBeat
from app.codirector.production.execution_windows import (
    generator_switch_plan_delta,
    plan_execution_windows,
    project_beats_two_tier,
    project_timed_regions_two_tier,
    region_intersects_window,
)
from app.codirector.production.timed_regions import TimedPromptRegion


def test_h3_30s_auto_plan_is_two_windows_ignores_requested():
    windows = plan_execution_windows(
        duration_seconds=30.0,
        generator_id="minimax-h3",
        requested_batch_count=1,  # ignored
    )
    assert len(windows) == 2
    assert windows[0].start == 0.0 and windows[0].end == 15.0
    assert windows[1].start == 15.0 and windows[1].end == 30.0


def test_primary_start_in_window_only():
    beats = [SceneBeat(index=0, description="enter"), SceneBeat(index=1, description="turn")]
    timed = [
        TimedBeat(start_sec=2.0, end_sec=18.0, description="enter corridor"),
        TimedBeat(start_sec=16.0, end_sec=28.0, description="turn corner"),
    ]
    # Window 0: 0-15 — PRIMARY beat 0 only
    p0 = project_beats_two_tier(
        scene_beats=beats,
        timed_beats=timed,
        window_start=0.0,
        window_end=15.0,
        scene_duration=30.0,
        batch_index=0,
        batch_count=2,
    )
    assert p0.primary_beat_indices == [0]
    assert p0.carry_beat_indices == []

    # Window 1: 15-30 — PRIMARY beat 1; CARRY beat 0 (spans across cut)
    p1 = project_beats_two_tier(
        scene_beats=beats,
        timed_beats=timed,
        window_start=15.0,
        window_end=30.0,
        scene_duration=30.0,
        batch_index=1,
        batch_count=2,
    )
    assert p1.primary_beat_indices == [1]
    assert p1.carry_beat_indices == [0]
    assert any("Continue in progress" in line for line in p1.carry_lines)
    assert any("enter corridor" in line for line in p1.carry_lines)
    # HARD LOCK: carry must not list beat 0 as primary (no re-fire)
    assert 0 not in p1.primary_beat_indices


def test_span_across_cut_never_double_primary():
    beats = [SceneBeat(index=0, description="steam")]
    timed = [TimedBeat(start_sec=10.0, end_sec=25.0, description="steam rises")]
    p0 = project_beats_two_tier(
        scene_beats=beats,
        timed_beats=timed,
        window_start=0.0,
        window_end=15.0,
        scene_duration=30.0,
        batch_index=0,
        batch_count=2,
    )
    p1 = project_beats_two_tier(
        scene_beats=beats,
        timed_beats=timed,
        window_start=15.0,
        window_end=30.0,
        scene_duration=30.0,
        batch_index=1,
        batch_count=2,
    )
    assert p0.primary_beat_indices == [0]
    assert p1.primary_beat_indices == []
    assert p1.carry_beat_indices == [0]
    # Beat must not be PRIMARY in both windows
    assert not (0 in p0.primary_beat_indices and 0 in p1.primary_beat_indices)


def test_timed_region_overlap_carry():
    regions = [
        TimedPromptRegion(start=0.0, end=18.0, text="walk corridor"),
        TimedPromptRegion(start=15.0, end=30.0, text="reach door"),
    ]
    primary, carry = project_timed_regions_two_tier(
        regions, window_start=15.0, window_end=30.0
    )
    assert len(primary) == 1 and primary[0].text == "reach door"
    assert any("walk corridor" in c for c in carry)
    assert region_intersects_window(0.0, 18.0, 15.0, 30.0)


def test_generator_switch_requires_new_scene_take():
    delta = generator_switch_plan_delta(
        previous_generator_id="minimax-h3",
        new_generator_id="ltx-2.5",  # may differ max window
        duration_seconds=30.0,
        previous_windows=[{"start": 0.0, "end": 15.0}, {"start": 15.0, "end": 30.0}],
    )
    assert delta.requires_new_scene_take is True
    assert delta.requires_revision_bump is True
    assert delta.new_batch_count >= 1
