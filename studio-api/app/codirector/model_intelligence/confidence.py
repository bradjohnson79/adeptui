"""Confidence helpers for pack claims."""

from __future__ import annotations

from .schemas import ConfidenceLevel


LEVEL_WEIGHT = {
    ConfidenceLevel.OFFICIAL: 1.0,
    ConfidenceLevel.VERIFIED_INTERNAL: 0.85,
    ConfidenceLevel.HUMAN_APPROVED: 0.75,
    ConfidenceLevel.COMMUNITY_UNVERIFIED: 0.35,
    ConfidenceLevel.INFERRED: 0.25,
    ConfidenceLevel.UNKNOWN: 0.1,
}


def blend(levels: list[ConfidenceLevel], base: float = 0.5) -> float:
    if not levels:
        return base
    vals = [LEVEL_WEIGHT.get(level, 0.1) for level in levels]
    return round(sum(vals) / len(vals), 3)
