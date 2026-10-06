"""Same-track no-overlap law (Python twin of timelineMaster/sameTrackNoOverlap.ts).

Hard law: no temporal intersection on the same track.
Adjacent boundaries are legal (A.end == B.start).
Epsilon ~1e-9 matches the TypeScript twin.
Music/ambience are aliased to the Audio lane until a separate Music lane exists.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

SAME_TRACK_EPS = 1e-9

_CLIP_ID_KEYS = ("id",)
_START_KEYS = ("start",)
_LENGTH_KEYS = ("length",)


class SameTrackOverlapError(ValueError):
    code = "SAME_TRACK_OVERLAP"


def ranges_intersect(a_start: float, a_len: float, b_start: float, b_len: float) -> bool:
    try:
        a0 = float(a_start)
        a1 = a0 + float(a_len)
        b0 = float(b_start)
        b1 = b0 + float(b_len)
    except (TypeError, ValueError):
        return False
    return a0 < b1 - SAME_TRACK_EPS and b0 < a1 - SAME_TRACK_EPS


def _clip_get(clip: Any, keys: Iterable[str], default: Any = None) -> Any:
    if clip is None:
        return default
    if isinstance(clip, Mapping):
        for key in keys:
            if key in clip and clip[key] is not None:
                return clip[key]
        return default
    for key in keys:
        if hasattr(clip, key):
            value = getattr(clip, key)
            if value is not None:
                return value
    return default


def _clip_id(clip: Any) -> str | None:
    value = _clip_get(clip, _CLIP_ID_KEYS)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clip_start(clip: Any) -> float:
    try:
        return float(_clip_get(clip, _START_KEYS, 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _clip_length(clip: Any) -> float:
    try:
        return float(_clip_get(clip, _LENGTH_KEYS, 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def find_same_track_intersection(clips: Iterable[Any] | None, candidate: Any) -> Any | None:
    cand_id = _clip_id(candidate)
    c_start = _clip_start(candidate)
    c_len = _clip_length(candidate)
    for clip in clips or []:
        other_id = _clip_id(clip)
        if cand_id and other_id and other_id == cand_id:
            continue
        if ranges_intersect(c_start, c_len, _clip_start(clip), _clip_length(clip)):
            return clip
    return None


def find_same_track_overlap_pair(clips: Iterable[Any] | None) -> tuple[Any, Any] | None:
    items = list(clips or [])
    for index, clip in enumerate(items):
        hit = find_same_track_intersection(items[index + 1 :], clip)
        if hit is not None:
            return clip, hit
    return None


def same_track_overlap_error(clips: Iterable[Any] | None, candidate: Any, track: str = "track") -> str | None:
    hit = find_same_track_intersection(clips, candidate)
    if hit is None:
        return None
    cand = _clip_id(candidate) or "(new)"
    other = _clip_id(hit) or "(other)"
    return f"SAME_TRACK_OVERLAP: clip {cand} intersects {other} on the {track} track"


def assert_no_same_track_overlap(clips: Iterable[Any] | None, candidate: Any, track: str = "track") -> None:
    message = same_track_overlap_error(clips, candidate, track)
    if message:
        raise SameTrackOverlapError(message)


def assert_track_array_no_overlap(clips: Iterable[Any] | None, track: str = "track") -> None:
    pair = find_same_track_overlap_pair(clips)
    if pair is None:
        return
    left, right = pair
    cand = _clip_id(left) or "(new)"
    other = _clip_id(right) or "(other)"
    raise SameTrackOverlapError(
        f"SAME_TRACK_OVERLAP: clip {cand} intersects {other} on the {track} track"
    )



# Creator / CD user-facing copy (Law #39 — no raw timing codes in chat).
USER_FACING_TRACK_OCCUPIED = "That part of the track is already occupied."
CD_LAYMAN_TRACK_OCCUPIED = (
    "That section of the track is already in use. Choose another time range."
)

_CLIP_TRACK_FIELDS = ("visualClips", "audioClips", "sfxClips", "cameraInstructions")


def flatten_master_prompts(master: Any) -> list[Any]:
    """Scene-absolute Timed Prompt track across all execution windows."""
    blocks = sorted(
        list(getattr(master, "batchBlocks", None) or []),
        key=lambda b: int(getattr(b, "order", 0) or 0),
    )
    out: list[Any] = []
    for batch in blocks:
        out.extend(list(getattr(batch, "promptSegments", None) or []))
    return out


def assert_prompt_segments_no_overlap(
    segments: Iterable[Any] | None,
    *,
    other_segments: Iterable[Any] | None = None,
    track: str = "prompt",
) -> None:
    """Reject any open intersection on the Timed Prompt track (edges may touch)."""
    items = list(segments or [])
    assert_track_array_no_overlap(items, track)
    others = list(other_segments or [])
    if not others:
        return
    for seg in items:
        assert_no_same_track_overlap(others, seg, track)


def assert_master_prompt_candidate_fits(master: Any, candidate: Any, track: str = "prompt") -> None:
    """Refuse a Timed Prompt that would intersect any existing Master prompt."""
    assert_no_same_track_overlap(flatten_master_prompts(master), candidate, track)


def audit_master_same_track_overlaps(master: Any) -> list[dict[str, Any]]:
    """Report existing same-track overlaps. Never deletes or mutates Master."""
    findings: list[dict[str, Any]] = []
    pair = find_same_track_overlap_pair(flatten_master_prompts(master))
    if pair is not None:
        left, right = pair
        findings.append(
            {
                "track": "prompt",
                "batchId": None,
                "aId": _clip_id(left),
                "bId": _clip_id(right),
                "aStart": _clip_start(left),
                "aLength": _clip_length(left),
                "bStart": _clip_start(right),
                "bLength": _clip_length(right),
                "message": same_track_overlap_error([left], right, "prompt"),
            }
        )
    for batch in getattr(master, "batchBlocks", None) or []:
        batch_id = str(getattr(batch, "id", "") or "") or None
        for field in _CLIP_TRACK_FIELDS:
            clips = list(getattr(batch, field, None) or [])
            hit = find_same_track_overlap_pair(clips)
            if hit is None:
                continue
            left, right = hit
            findings.append(
                {
                    "track": field,
                    "batchId": batch_id,
                    "aId": _clip_id(left),
                    "bId": _clip_id(right),
                    "aStart": _clip_start(left),
                    "aLength": _clip_length(left),
                    "bStart": _clip_start(right),
                    "bLength": _clip_length(right),
                    "message": same_track_overlap_error([left], right, field),
                }
            )
    return findings


def audio_lane_kind(kind: str | None) -> str:
    return "sfx" if kind == "sfx" else "audio"
