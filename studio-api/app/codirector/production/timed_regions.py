"""Explicit timed prompt regions — independent of generation batch count.

Multiple Timed Prompts are created only when the creator writes temporal
sections (0–10: … / 10–20: …). Batch count never infers regions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TimedPromptRegion:
    start: float
    end: float
    text: str

    @property
    def length(self) -> float:
        return max(0.0, float(self.end) - float(self.start))


_REGION_RE = re.compile(
    r"(?:^|\n)\s*(\d+(?:\.\d+)?)\s*[-–—to]+\s*(\d+(?:\.\d+)?)\s*"
    r"(?:s(?:ec(?:onds?)?)?)?\s*[:\n]\s*"
    r"(.+?)(?=(?:\n\s*\d+(?:\.\d+)?\s*[-–—to]+\s*\d+)|\Z)",
    re.I | re.S,
)


def parse_explicit_timed_regions(message: str) -> list[TimedPromptRegion]:
    """Return 2+ explicit temporal prompt regions, else []."""
    text = message or ""
    found: list[TimedPromptRegion] = []
    for match in _REGION_RE.finditer(text):
        start = float(match.group(1))
        end = float(match.group(2))
        body = re.sub(r"\s+", " ", (match.group(3) or "").strip())
        if end <= start or not body:
            continue
        found.append(TimedPromptRegion(start=start, end=end, text=body))
    if len(found) < 2:
        return []
    found.sort(key=lambda item: item.start)
    return found


def region_intersects_window(
    region_start: float,
    region_end: float,
    window_start: float,
    window_end: float,
) -> bool:
    """True when [region_start, region_end) overlaps [window_start, window_end)."""
    return float(region_start) < float(window_end) and float(region_end) > float(window_start)


def project_regions_for_execution_window(
    regions: list[TimedPromptRegion],
    *,
    window_start: float,
    window_end: float,
) -> tuple[list[TimedPromptRegion], list[str]]:
    """PRIMARY (start in window) + OVERLAP CARRY continue lines (never re-fire)."""
    from .execution_windows import project_timed_regions_two_tier

    primary, carry = project_timed_regions_two_tier(
        regions, window_start=window_start, window_end=window_end
    )
    return list(primary), list(carry)

