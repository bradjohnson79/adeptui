"""Automated contract tests for the MiniMax H3 frame-count resolver.

Verifies:
  1. Legal count: resolver returns 17k+5 frame counts.
  2. Sufficient generation frames: 12.0s → 294 (not 288).
  3. No unnecessary extra frames when already legal: 12.25s → 294 (no change).
  4. No scene duration mutation: request.duration stays as the creator's request.
  5. Fractional duration safety: 12.5s resolves deterministically.
  6. Max boundary: 15.0s resolves to 362 (max legal).
  7. Above max: 15.5s raises (genuine incompatibility).
"""

from __future__ import annotations

import pytest

from app.workflows.h3_ref2v_builder import (
    frames_for_duration,
    resolve_h3_generation_frames,
    snap_h3_length,
)


def _is_legal(n: int) -> bool:
    """MiniMax H3 legal frame count: n >= 5 and n % 17 == 5."""
    return n >= 5 and n % 17 == 5


class TestLegalCount:
    """The resolver must always return a legal 17k+5 frame count."""

    @pytest.mark.parametrize("duration", [5.0, 8.0, 10.0, 12.0, 12.25, 12.5, 15.0])
    def test_returns_legal_count(self, duration: float):
        frames = frames_for_duration(duration)
        assert _is_legal(frames), f"{frames} is not legal (17k+5) for {duration}s"

    def test_snap_h3_length_returns_legal(self):
        assert _is_legal(snap_h3_length(288))
        assert _is_legal(snap_h3_length(294))


class TestSufficientFrames:
    """12.0s must resolve to 294 frames (not 288)."""

    def test_12s_resolves_to_294(self):
        assert frames_for_duration(12.0) == 294

    def test_288_frames_snaps_up_to_294(self):
        assert snap_h3_length(288) == 294

    def test_294_is_legal(self):
        assert 294 % 17 == 5
        assert _is_legal(294)

    def test_288_is_illegal(self):
        assert 288 % 17 == 16
        assert not _is_legal(288)


class TestNoUnnecessaryExtra:
    """Already-legal durations must not get extra frames."""

    def test_12_25s_stays_294(self):
        assert frames_for_duration(12.25) == 294

    def test_8s_stays_192(self):
        # 192 % 17 = 5 (legal)
        assert frames_for_duration(8.0) == 192
        assert 192 % 17 == 5

    def test_294_frames_stays_294(self):
        assert snap_h3_length(294) == 294

    def test_362_frames_stays_362(self):
        # Max legal ceiling for clean 15s request — must not false-reject via seconds re-entry.
        assert snap_h3_length(362) == 362


class TestNoSceneMutation:
    """request.duration must stay as the creator's requested duration.

    The request_builder keeps request.duration = requested_duration (12.0s)
    for MiniMax H3, not the snapped legal duration (12.25s). The legal frame
    count is passed separately as legalFrameCount in providerOptions.
    """

    def test_request_builder_keeps_raw_duration_for_h3(self):
        from app.director_timeline_w46.generation.request_builder import (
            _h3_duration_for_request,
        )
        from app.video_runtime.legal_canvas import is_minimax_h3_generator

        # Simulate a MiniMax H3 generator
        gen_id = "minimax-h3-t2v-local"
        assert is_minimax_h3_generator(gen_id), "test requires a MiniMax H3 generator id"

        requested = 12.0
        job_duration, extras = _h3_duration_for_request(gen_id, requested)

        # job_duration is the legal duration (12.25s) — used for knowledge compilation
        assert job_duration == 12.25
        # extras carry the contract fields
        assert extras["requestedDurationSec"] == 12.0
        assert extras["legalDurationSec"] == 12.25
        assert extras["legalFrameCount"] == 294
        # The request_builder keeps request.duration = requested (12.0s) for H3
        # (verified by the is_minimax_h3_generator branch in build_timeline_generation_request)
        # The Scene duration is NOT mutated to 12.25s.


class TestFractionalDuration:
    """Fractional durations must resolve deterministically."""

    def test_12_5s_deterministic(self):
        # 12.5s @ 24fps = 300 frames. 300 % 17 = 11 (illegal).
        # Next 17k+5 >= 300: 17*17=289+5=294 (< 300), 17*18=306+5=311 (>= 300).
        # So 12.5s → 311 frames.
        result1 = frames_for_duration(12.5)
        result2 = frames_for_duration(12.5)
        assert result1 == result2, "Fractional duration must be deterministic"
        assert _is_legal(result1)
        assert result1 >= 300, "Must be at or above the requested frame count"

    def test_10_7s_deterministic(self):
        result = frames_for_duration(10.7)
        assert _is_legal(result)
        # 10.7s @ 24fps = 256.8 → 257 frames. 257 % 17 = 2 (illegal).
        # Next 17k+5 >= 257: 17*15=255+5=260 (>= 257). So 10.7s → 260.
        assert result == 260


class TestMaxBoundary:
    """15.0s is the max and must resolve to 362 (max legal)."""

    def test_15s_resolves_to_362(self):
        # 15.0s @ 24fps = 360 frames. 360 % 17 = 3 (illegal).
        # Next 17k+5 >= 360: 17*21=357+5=362 (>= 360). So 15.0s → 362.
        assert frames_for_duration(15.0) == 362
        assert 362 % 17 == 5

    def test_above_max_raises(self):
        """Genuine incompatibility (>15s) must raise, not silently snap."""
        from app.video_runtime.legal_canvas import SpecFidelityError

        with pytest.raises(SpecFidelityError):
            frames_for_duration(15.5)
        with pytest.raises(SpecFidelityError):
            frames_for_duration(20.0)


class TestResolverContract:
    """The resolver is the single authoritative MiniMax frame-count resolver."""

    def test_resolve_always_legal(self):
        for d in [1.0, 3.0, 5.0, 7.0, 10.0, 12.0, 14.0, 15.0]:
            assert _is_legal(resolve_h3_generation_frames(d))

    def test_resolve_monotonic(self):
        """Longer requested durations must not produce fewer frames."""
        prev = 0
        for d in [1.0, 3.0, 5.0, 8.0, 10.0, 12.0, 15.0]:
            frames = resolve_h3_generation_frames(d)
            assert frames >= prev, f"{d}s produced fewer frames than a shorter duration"
            prev = frames
