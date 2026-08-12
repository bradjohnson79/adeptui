"""Independent per-section readiness for Logline / Short / Long.

A project can earn a strong logline while the Long Summary is still omitted.
Readiness is computed from `StorySummarySource` evidence volume and shape.
"""

from __future__ import annotations

from .contracts import Coverage, StorySummarySource

_RENDER_THRESHOLD: Coverage = "PARTIAL"


def _score(src: StorySummarySource) -> int:
    """Coarse evidence score: facts + script summaries + character roles."""
    return (
        len(src.confirmedFacts)
        + len(src.approvedScriptSummaries) * 2
        + len(src.confirmedCharacterRoles)
        + len(src.confirmedTimelineEvents)
    )


def logline_readiness(src: StorySummarySource) -> Coverage:
    """Logline needs a protagonist + central situation (1-2 facts can suffice)."""
    has_subject = bool(src.confirmedCharacterRoles) or any(
        "barnes" in f.lower() or "kyung" in f.lower() for f in src.confirmedFacts
    )
    has_situation = bool(src.confirmedFacts) or bool(src.approvedScriptSummaries)
    if not has_subject or not has_situation:
        return "MINIMAL"
    if _score(src) >= 4:
        return "MATURE"
    if _score(src) >= 2:
        return "SUBSTANTIAL"
    return "PARTIAL"


def short_summary_readiness(src: StorySummarySource) -> Coverage:
    """Short summary needs a few established facts + a frame."""
    score = _score(src)
    if score >= 6:
        return "MATURE"
    if score >= 3:
        return "SUBSTANTIAL"
    if score >= 1 and (src.confirmedFacts or src.approvedScriptSummaries):
        return "PARTIAL"
    return "MINIMAL"


def long_summary_readiness(src: StorySummarySource) -> Coverage:
    """Long summary needs multiple established story movements / installments."""
    score = _score(src)
    has_movements = (
        len(src.approvedScriptSummaries) >= 1
        or len(src.confirmedTimelineEvents) >= 2
        or len(src.confirmedFacts) >= 4
    )
    if score >= 8 and has_movements:
        return "MATURE"
    if score >= 5 and has_movements:
        return "SUBSTANTIAL"
    if score >= 3 and (src.approvedScriptSummaries or src.confirmedTimelineEvents):
        return "PARTIAL"
    return "MINIMAL"


def should_render(coverage: Coverage) -> bool:
    """A section renders only when readiness reaches the render threshold."""
    order = {"MINIMAL": 0, "PARTIAL": 1, "SUBSTANTIAL": 2, "MATURE": 3}
    return order[coverage] >= order[_RENDER_THRESHOLD]


__all__ = [
    "logline_readiness",
    "short_summary_readiness",
    "long_summary_readiness",
    "should_render",
]
