"""Stable @ImageN display tags for timeline image clips."""

from __future__ import annotations

import re
from typing import Iterable

from ..director_timeline import DirectorTimeline, ImageClip

_TAG_RE = re.compile(r"^@Image(\d+)$")


def parse_tag_number(tag: str | None) -> int | None:
    if not tag:
        return None
    m = _TAG_RE.match(str(tag).strip())
    return int(m.group(1)) if m else None


def format_display_tag(n: int) -> str:
    return f"@Image{int(n)}"


def allocate_display_tag(tl: DirectorTimeline) -> str:
    """Allocate the next monotonic @ImageN tag and advance the counter."""
    n = max(1, int(tl.next_image_tag_number or 1))
    # Ensure we never collide with an existing tag number.
    used = {parse_tag_number(c.display_tag) for c in tl.image_clips}
    used.discard(None)
    while n in used:
        n += 1
    tl.next_image_tag_number = n + 1
    return format_display_tag(n)


def ensure_tags(tl: DirectorTimeline) -> DirectorTimeline:
    """Assign missing display_tag values; never renumber existing tags."""
    used_nums: set[int] = set()
    for clip in tl.image_clips:
        num = parse_tag_number(clip.display_tag)
        if num is not None:
            used_nums.add(num)

    # Advance counter past any already-present tags.
    next_n = max(1, int(tl.next_image_tag_number or 1))
    if used_nums:
        next_n = max(next_n, max(used_nums) + 1)
    tl.next_image_tag_number = next_n

    for clip in tl.image_clips:
        if parse_tag_number(clip.display_tag) is None:
            clip.display_tag = allocate_display_tag(tl)
    return tl


def find_clip_by_tag(clips: Iterable[ImageClip], tag: str) -> ImageClip | None:
    needle = str(tag or "").strip()
    if not needle.startswith("@"):
        needle = f"@{needle}" if needle.lower().startswith("image") else needle
    for clip in clips:
        if (clip.display_tag or "").strip() == needle:
            return clip
    return None
