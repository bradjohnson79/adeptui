"""Stable Timeline shot numbers.

A shot number is the creator-facing identity of one generated unit. It is
assigned when that unit is created and does not follow track position.
Re-Take pieces keep the parent number. Deleted numbers are not reused.

This module is the only allocator. Co-Director reads the stored number.
"""

from __future__ import annotations

from .contracts import FilmTimeline, Segment


def creator_shot_label(number: int) -> str:
    n = int(number or 0)
    return f"Shot {n}" if n > 0 else ""


def creator_shot_tag(number: int) -> str:
    n = int(number or 0)
    return f"#Shot{n}" if n > 0 else ""


def _high_water(film: FilmTimeline) -> int:
    high = int(film.highestShotNumber or 0)
    for shot in film.shots:
        for segment in shot.segments:
            high = max(high, int(segment.shotNumber or 0))
    return high


_TERMINAL_UNCOMMITTED = {"failed", "cancelled", "interrupted"}
_ACTIVE_HOLD = {"queued", "generating", "processing", "downloading"}


def _retake_piece(segment: Segment) -> bool:
    if str(segment.sourceSegmentId or "").strip():
        return True
    meta = segment.generationMetadata if isinstance(segment.generationMetadata, dict) else {}
    return isinstance(meta.get("segmentedRetake"), dict)


def _segments(film: FilmTimeline) -> list[Segment]:
    return [segment for shot in film.shots for segment in shot.segments]


def release_uncommitted_shot_numbers(film: FilmTimeline) -> bool:
    """A failed attempt is not a shot. Its number goes back to the high-water mark.

    Completed shots keep their numbers, including after one of them is deleted.
    A number is released only when every piece that carried it has no picture
    and is failed, cancelled, or interrupted. Re-Take pieces are left alone.
    """

    changed = False
    releasable: set[int] = set()
    for segment in _segments(film):
        number = int(segment.shotNumber or 0)
        if number <= 0 or segment.assetId or _retake_piece(segment):
            continue
        if segment.status in _TERMINAL_UNCOMMITTED:
            releasable.add(number)
    for number in list(releasable):
        holders = [segment for segment in _segments(film) if int(segment.shotNumber or 0) == number]
        if any(segment.assetId or segment.status in _ACTIVE_HOLD for segment in holders):
            releasable.discard(number)
    if not releasable:
        return False
    for segment in _segments(film):
        number = int(segment.shotNumber or 0)
        if number not in releasable or segment.assetId or _retake_piece(segment):
            continue
        meta = dict(segment.generationMetadata) if isinstance(segment.generationMetadata, dict) else {}
        meta["releasedShotNumber"] = number
        meta["generationAttemptReleased"] = True
        segment.generationMetadata = meta
        segment.shotNumber = 0
        changed = True
    held = 0
    for segment in _segments(film):
        held = max(held, int(segment.shotNumber or 0))
    old = int(film.highestShotNumber or 0)
    if old in releasable and old > held:
        film.highestShotNumber = held
        changed = True
    return changed


def drop_released_attempts(film: FilmTimeline, *, keep_failed_notice: bool = False) -> bool:
    """Remove an attempt that already gave its number back.

    The failed row can stay so the creator still sees why it stopped. The next
    Continue drops it and uses that same number.
    """

    changed = False
    for shot in film.shots:
        kept: list[Segment] = []
        for segment in shot.segments:
            meta = segment.generationMetadata if isinstance(segment.generationMetadata, dict) else {}
            released = bool(meta.get("generationAttemptReleased")) and not segment.assetId and not _retake_piece(segment)
            if released and not (keep_failed_notice and segment.status == "failed"):
                changed = True
                continue
            kept.append(segment)
        if len(kept) != len(shot.segments):
            shot.segments = kept
    return changed


def allocate_shot_number(film: FilmTimeline) -> int:
    """Next number from the scene high-water mark, not from position or count."""

    number = _high_water(film) + 1
    film.highestShotNumber = number
    return number


def backfill_shot_numbers(film: FilmTimeline) -> bool:
    """One-time numbers for scenes that predate shot identity.

    Canonical pieces are numbered in current composition order, once.
    Re-Take head, replacement, and tail share the parent number.
    Already assigned numbers are left alone.
    """

    changed = False
    high = _high_water(film)

    def remember(number: int) -> None:
        nonlocal high, changed
        if int(film.highestShotNumber or 0) < number or high < number:
            high = max(high, number)

    canonical: list[Segment] = []
    children: dict[str, list[Segment]] = {}
    for shot in sorted(film.shots, key=lambda item: int(item.order or 0)):
        for segment in sorted(shot.segments, key=lambda item: int(item.order or 0)):
            parent = str(segment.sourceSegmentId or "").strip()
            spec = segment.generationMetadata.get("segmentedRetake") if isinstance(segment.generationMetadata, dict) else None
            if not parent and isinstance(spec, dict):
                parent = str(spec.get("sourceSegmentId") or "").strip()
            role = str(segment.compositionRole or "generated")
            if parent and (role in {"source", "retake"} or isinstance(spec, dict)):
                children.setdefault(parent, []).append(segment)
            else:
                canonical.append(segment)

    for segment in canonical:
        meta = segment.generationMetadata if isinstance(segment.generationMetadata, dict) else {}
        if meta.get("generationAttemptReleased"):
            continue
        if int(segment.shotNumber or 0) > 0:
            remember(int(segment.shotNumber))
            continue
        high += 1
        segment.shotNumber = high
        changed = True

    by_id = {segment.id: segment for shot in film.shots for segment in shot.segments}
    for parent_id, group in children.items():
        parent = by_id.get(parent_id)
        number = int(parent.shotNumber or 0) if parent is not None else 0
        if number <= 0:
            existing = [int(item.shotNumber or 0) for item in group if int(item.shotNumber or 0) > 0]
            number = min(existing) if existing else 0
        if number <= 0:
            high += 1
            number = high
        for item in group:
            if int(item.shotNumber or 0) != number:
                item.shotNumber = number
                changed = True
            remember(number)

    if int(film.highestShotNumber or 0) != high:
        film.highestShotNumber = high
        changed = True
    return changed
