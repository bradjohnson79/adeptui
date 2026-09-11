"""Pure window planning for a non-destructive media retake."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..lipsync_tracks import LipSyncTracks


class MediaRetakeError(RuntimeError):
    """Base class for windowed media retake planning errors."""


class MediaRetakeOverlapError(MediaRetakeError):
    """Two planned windows overlap in time."""


class MediaRetakeFitError(MediaRetakeError):
    """Replacement audio does not fit inside its window."""


class MediaRetakeDonorError(MediaRetakeError):
    """Could not find a usable room-tone donor span."""


@dataclass
class WindowPlan:
    """A single lip-sync replacement window.

    ``start`` and ``end`` are seconds on the master scene timeline.
    ``roi`` is the owning track's mouth region (normalized x, y, w, h) used
    to crop the segment around the target face so LatentSync — which always
    animates the FIRST detected face — can only select the bound speaker.
    """

    clip_id: str
    track_id: str
    slot: int
    character_id: str | None
    character_name: str | None
    audio_asset_id: str
    start: float
    end: float
    roi: tuple[float, float, float, float] | None = None

    @property
    def length(self) -> float:
        return self.end - self.start


def _windows_overlap(a: WindowPlan, b: WindowPlan) -> bool:
    """Return True if the two closed intervals share any time."""
    return not (a.end <= b.start or b.end <= a.start)


def _validate_bounds(clip_id: str, start: float, end: float, scene_duration_sec: float) -> None:
    if start < 0.0:
        raise ValueError(f"Clip {clip_id}: start {start} is negative")
    if end > scene_duration_sec + 1e-9:
        raise ValueError(
            f"Clip {clip_id}: end {end} exceeds scene duration {scene_duration_sec}"
        )
    if start >= end:
        raise ValueError(f"Clip {clip_id}: start {start} is not before end {end}")


def _clip_identity(
    clip,
    track,
) -> tuple[str | None, str | None]:
    """Resolve character identity from clip or its parent track."""
    character_id = (clip.character_id or "").strip() or (track.character_id or "").strip() or None
    character_name = (
        (clip.character_name or "").strip() or (track.character_name or "").strip() or None
    )
    return character_id, character_name


def plan_windows(
    tracks: LipSyncTracks,
    scene_duration_sec: float,
    audio_duration: Callable[[str], float],
) -> list[WindowPlan]:
    """Build a sorted, non-overlapping list of replacement windows.

    - Only enabled tracks are considered.
    - Clips without a usable ``audio_asset_id`` are skipped.
    - The fallback audio asset on a track is used when a clip has none.
    - Windows are fit-checked against the real replacement line duration.
    """
    windows: list[WindowPlan] = []

    for track in tracks.tracks or []:
        if not track.enabled:
            continue
        for clip in track.clips or []:
            audio_asset_id = (clip.audio_asset_id or "").strip() or (
                track.audio_asset_id or ""
            ).strip()
            if not audio_asset_id:
                continue

            start = float(clip.start)
            end = float(clip.start + clip.length)
            _validate_bounds(clip.id, start, end, scene_duration_sec)

            line_duration = audio_duration(audio_asset_id)
            window_duration = end - start
            tolerance = 0.05
            if line_duration > window_duration + tolerance:
                raise MediaRetakeFitError(
                    f"Clip {clip.id}: line duration {line_duration:.3f}s does not fit "
                    f"in window duration {window_duration:.3f}s"
                )

            character_id, character_name = _clip_identity(clip, track)
            roi = getattr(track, "roi", None)
            roi_tuple = (
                (float(roi.x), float(roi.y), float(roi.w), float(roi.h))
                if roi is not None
                else None
            )
            windows.append(
                WindowPlan(
                    clip_id=clip.id,
                    track_id=track.id,
                    slot=track.slot,
                    character_id=character_id,
                    character_name=character_name,
                    audio_asset_id=audio_asset_id,
                    start=start,
                    end=end,
                    roi=roi_tuple,
                )
            )

    # Overlap is forbidden, even across different tracks (one speaker per window).
    sorted_windows = sorted(windows, key=lambda w: (w.start, w.end))
    for i in range(len(sorted_windows) - 1):
        a, b = sorted_windows[i], sorted_windows[i + 1]
        if _windows_overlap(a, b):
            raise MediaRetakeOverlapError(
                f"Clips {a.clip_id} and {b.clip_id} overlap in time ({a.start:.3f}-{a.end:.3f} vs {b.start:.3f}-{b.end:.3f})"
            )

    return sorted_windows


def pick_donor_span(
    windows: list[WindowPlan],
    scene_duration_sec: float,
    desired: float = 1.0,
) -> tuple[float, float]:
    """Choose a non-overlapping room-tone donor span of up to ``desired`` seconds.

    Strategy:
      1. Use the gap immediately before the first window.
      2. If that yields < 0.5s, try the gap immediately after the last window.
      3. If still < 0.5s, raise MediaRetakeDonorError.
    """
    min_donor = 0.5
    gap = 0.05

    candidates: list[tuple[float, float]] = []

    first_start = min((w.start for w in windows), default=0.0)
    candidate_end = max(0.0, first_start - gap)
    candidate_start = max(0.0, candidate_end - desired)
    candidates.append((candidate_start, candidate_end))

    last_end = max((w.end for w in windows), default=scene_duration_sec)
    candidate_start2 = min(scene_duration_sec, last_end + gap)
    candidate_end2 = min(scene_duration_sec, candidate_start2 + desired)
    candidates.append((candidate_start2, candidate_end2))

    for start, end in candidates:
        if end - start >= min_donor - 1e-9:
            # Ensure it does not overlap any window.
            donor = WindowPlan(
                clip_id="__donor__",
                track_id="",
                slot=0,
                character_id=None,
                character_name=None,
                audio_asset_id="",
                start=start,
                end=end,
            )
            if not any(_windows_overlap(donor, w) for w in windows):
                return (start, end)

    raise MediaRetakeDonorError(
        "Could not find a usable room-tone donor span of at least 0.5s"
    )
