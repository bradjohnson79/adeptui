"""Story Summary Editor package — editorial prose for the Wiki Story page."""

from .contracts import (
    CompiledStorySummary,
    PreviousApprovedSummary,
    StorySummarySource,
)
from .editor import edit_story_summary
from .evidence import build_story_summary_source, evidence_hash
from .fallback import conservative_fallback
from .laws import validate
from .readiness import (
    logline_readiness,
    long_summary_readiness,
    short_summary_readiness,
    should_render,
)
from .theme_normalizer import normalize_theme, normalize_themes
from .triggers import is_minor_evidence_change, should_recompile_summary

__all__ = [
    "CompiledStorySummary",
    "PreviousApprovedSummary",
    "StorySummarySource",
    "build_story_summary_source",
    "conservative_fallback",
    "edit_story_summary",
    "evidence_hash",
    "is_minor_evidence_change",
    "logline_readiness",
    "long_summary_readiness",
    "normalize_theme",
    "normalize_themes",
    "short_summary_readiness",
    "should_recompile_summary",
    "should_render",
    "validate",
]
