"""Refresh triggers for the Story Summary Editor.

Decides whether to recompile summaries based on the nature of the new
evidence versus the previous evidence. Avoids recompiling on every trivial
turn. Honors SUMMARY_REVISION_SHOULD_BE_MINIMAL_WHEN_NEW_EVIDENCE_IS_MINOR.
"""

from __future__ import annotations

from .contracts import StorySummarySource
from .evidence import evidence_hash


def should_recompile_summary(
    prev_source: StorySummarySource | None, new_source: StorySummarySource
) -> bool:
    """Return True when the summary should be recompiled."""
    if prev_source is None:
        # First compile or no prior evidence recorded.
        return bool(new_source.confirmedFacts or new_source.approvedScriptSummaries)
    prev_hash = evidence_hash(prev_source)
    new_hash = evidence_hash(new_source)
    if prev_hash == new_hash:
        return False
    # Major change: a new approved script summary or new installment.
    if len(new_source.approvedScriptSummaries) != len(prev_source.approvedScriptSummaries):
        return True
    # Major change: a new character role or timeline event added.
    if len(new_source.confirmedCharacterRoles) > len(prev_source.confirmedCharacterRoles):
        return True
    if len(new_source.confirmedTimelineEvents) > len(prev_source.confirmedTimelineEvents):
        return True
    # Otherwise: minor evidence change → recompile but the stability law
    # ensures the editor revises minimally rather than rewriting.
    return True


def is_minor_evidence_change(
    prev_source: StorySummarySource | None, new_source: StorySummarySource
) -> bool:
    """Classify the change as minor (for the stability law)."""
    if prev_source is None:
        return False
    if len(new_source.approvedScriptSummaries) != len(prev_source.approvedScriptSummaries):
        return False
    if len(new_source.confirmedCharacterRoles) > len(prev_source.confirmedCharacterRoles):
        return False
    if len(new_source.confirmedTimelineEvents) > len(prev_source.confirmedTimelineEvents):
        return False
    # Only fact/interpretation text changed → minor.
    return evidence_hash(prev_source) != evidence_hash(new_source)


__all__ = ["should_recompile_summary", "is_minor_evidence_change"]
