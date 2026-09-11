"""Tests for the windowed media retake planner."""

from __future__ import annotations

import pytest

from app.lipsync_tracks import LipSyncClip, LipSyncTrack, LipSyncTracks
from app.media_retake.planner import (
    MediaRetakeDonorError,
    MediaRetakeFitError,
    MediaRetakeOverlapError,
    WindowPlan,
    pick_donor_span,
    plan_windows,
)


def _tracks(
    enabled: bool = True,
    clips: list[tuple[float, float]] | None = None,
    audio_asset_id: str = "audio-1",
    character_id: str | None = "char-1",
    character_name: str | None = "Korri",
    track_audio_asset_id: str | None = None,
    slot: int = 1,
    disabled: bool = False,
) -> LipSyncTracks:
    clip_objs = []
    for i, (start, length) in enumerate(clips or [(0.0, 2.0)]):
        clip_objs.append(
            LipSyncClip(
                id=f"c{i}",
                start=start,
                length=length,
                audio_asset_id=audio_asset_id,
                character_id=character_id,
                character_name=character_name,
            )
        )
    track = LipSyncTrack(
        id="t0",
        slot=slot,
        enabled=enabled,
        audio_asset_id=track_audio_asset_id,
        clips=clip_objs,
    )
    if disabled:
        track.enabled = False
    return LipSyncTracks(tracks=[track])


def _audio_durations(durations: dict[str, float]) -> callable:
    def lookup(asset_id: str) -> float:
        return durations[asset_id]
    return lookup


def test_two_window_happy_path_sorted():
    tracks = _tracks(
        clips=[(1.0, 2.0), (5.0, 2.0)],
        audio_asset_id="audio-1",
    )
    durations = {"audio-1": 1.9}
    windows = plan_windows(tracks, scene_duration_sec=10.0, audio_duration=durations.get)
    assert len(windows) == 2
    assert [w.start for w in windows] == [1.0, 5.0]
    assert windows[0].clip_id == "c0"
    assert windows[1].clip_id == "c1"
    assert windows[0].character_id == "char-1"


def test_cross_track_overlap_rejected():
    track_a = LipSyncTrack(
        id="ta",
        slot=1,
        enabled=True,
        clips=[LipSyncClip(id="a1", start=1.0, length=2.0, audio_asset_id="a", character_id="x")],
    )
    track_b = LipSyncTrack(
        id="tb",
        slot=2,
        enabled=True,
        clips=[LipSyncClip(id="b1", start=2.5, length=2.0, audio_asset_id="b", character_id="y")],
    )
    tracks = LipSyncTracks(tracks=[track_a, track_b])
    durations = {"a": 1.0, "b": 1.0}
    with pytest.raises(MediaRetakeOverlapError, match="a1.*b1"):
        plan_windows(tracks, scene_duration_sec=10.0, audio_duration=durations.get)


def test_out_of_bounds_rejected():
    tracks = _tracks(clips=[(8.0, 5.0)], audio_asset_id="audio-1")
    durations = {"audio-1": 1.0}
    with pytest.raises(ValueError, match="c0"):
        plan_windows(tracks, scene_duration_sec=10.0, audio_duration=durations.get)


def test_fit_error_names_clip_and_durations():
    tracks = _tracks(clips=[(1.0, 1.0)], audio_asset_id="audio-1")
    durations = {"audio-1": 1.2}
    with pytest.raises(MediaRetakeFitError, match=r"c0.*1\.200.*1\.000"):
        plan_windows(tracks, scene_duration_sec=10.0, audio_duration=durations.get)


def test_disabled_track_skipped():
    tracks = _tracks(enabled=False, clips=[(1.0, 1.0)], audio_asset_id="audio-1")
    durations = {"audio-1": 0.5}
    windows = plan_windows(tracks, scene_duration_sec=10.0, audio_duration=durations.get)
    assert windows == []


def test_audio_less_clip_skipped():
    clip_with = LipSyncClip(id="cw", start=1.0, length=1.0, audio_asset_id="audio-1", character_id="c")
    clip_without = LipSyncClip(id="cx", start=3.0, length=1.0, audio_asset_id=None, character_id="c")
    track = LipSyncTrack(id="t0", slot=1, enabled=True, clips=[clip_with, clip_without])
    tracks = LipSyncTracks(tracks=[track])
    durations = {"audio-1": 0.8}
    windows = plan_windows(tracks, scene_duration_sec=10.0, audio_duration=durations.get)
    assert len(windows) == 1
    assert windows[0].clip_id == "cw"


def test_track_audio_fallback():
    clip = LipSyncClip(id="cf", start=1.0, length=1.0, audio_asset_id=None, character_id="c")
    track = LipSyncTrack(
        id="t0",
        slot=1,
        enabled=True,
        audio_asset_id="track-audio",
        clips=[clip],
    )
    tracks = LipSyncTracks(tracks=[track])
    durations = {"track-audio": 0.8}
    windows = plan_windows(tracks, scene_duration_sec=10.0, audio_duration=durations.get)
    assert len(windows) == 1
    assert windows[0].audio_asset_id == "track-audio"


def test_donor_before_first_window():
    windows = [WindowPlan("c1", "t", 1, None, None, "a", 3.0, 5.0)]
    span = pick_donor_span(windows, scene_duration_sec=10.0, desired=1.0)
    assert span == pytest.approx((1.95, 2.95))


def test_donor_after_last_window_when_before_is_short():
    windows = [WindowPlan("c1", "t", 1, None, None, "a", 0.5, 1.5)]
    span = pick_donor_span(windows, scene_duration_sec=10.0, desired=1.0)
    assert span == pytest.approx((1.55, 2.55))


def test_donor_impossible_raises():
    windows = [WindowPlan("c1", "t", 1, None, None, "a", 0.0, 10.0)]
    with pytest.raises(MediaRetakeDonorError):
        pick_donor_span(windows, scene_duration_sec=10.0, desired=1.0)
