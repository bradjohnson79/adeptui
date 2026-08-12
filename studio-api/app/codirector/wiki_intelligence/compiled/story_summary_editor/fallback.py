"""Conservative deterministic fallback — basic factual synopsis or omit.

Never imitates full editorial prose. Produces only a basic factual synopsis
from confirmed facts, or omits the section entirely when it cannot be done
safely. Honors DETERMINISTIC_FALLBACK_MUST_PREFER_OMISSION_OVER_MECHANICAL_PROSE.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .contracts import CompiledStorySummary, StorySummarySource
from .readiness import (
    logline_readiness,
    long_summary_readiness,
    short_summary_readiness,
    should_render,
)


def _factual_synopsis(source: StorySummarySource) -> str:
    """One or two sentences stating only confirmed facts, no editorial flourish."""
    facts = source.confirmedFacts[:3]
    if not facts:
        return ""
    # Join with semicolons; keep it dry and factual.
    return "; ".join(f.rstrip(".") for f in facts).strip() + "."


def conservative_fallback(source: StorySummarySource) -> CompiledStorySummary:
    logline_cov = logline_readiness(source)
    short_cov = short_summary_readiness(source)
    long_cov = long_summary_readiness(source)

    logline = ""
    short = ""
    long_summary = ""

    if should_render(logline_cov):
        # Logline: a single factual sentence from the strongest fact.
        if source.confirmedFacts:
            logline = source.confirmedFacts[0].rstrip(".") + "."
            if len(logline) > 220:
                logline = logline[:217].rstrip() + "…"

    if should_render(short_cov):
        short = _factual_synopsis(source)

    # Long summary: deliberately omitted unless substantial evidence.
    if should_render(long_cov) and long_cov in {"SUBSTANTIAL", "MATURE"}:
        facts = source.confirmedFacts[:6]
        if len(facts) >= 4:
            long_summary = " ".join(f.rstrip(".") + "." for f in facts)

    return CompiledStorySummary(
        logline=logline,
        shortSummary=short,
        longSummary=long_summary,
        themes=list(source.inferredThemes),
        centralConflicts=[],
        narrativeFrame="",
        unresolvedQuestions=list(source.unresolvedQuestions),
        sourceRecordIds=list(source.sourceIds),
        lastCompiledAt=datetime.now(timezone.utc).isoformat(),
        loglineCoverage=logline_cov,
        shortSummaryCoverage=short_cov,
        longSummaryCoverage=long_cov,
        requiresCreatorReview=False,
        editorMode="deterministic",
        revisionDelta="deterministic factual synopsis",
    )


__all__ = ["conservative_fallback"]
