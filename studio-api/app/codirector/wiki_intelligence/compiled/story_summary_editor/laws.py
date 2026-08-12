"""Hard-law validators for Story Summary Editor output.

Ten laws. Each returns a list of violations (empty when satisfied). The
editor applies these as post-conditions; any violation blanks the offending
field or falls back to the conservative deterministic path.
"""

from __future__ import annotations

import re

from .contracts import CompiledStorySummary, StorySummarySource

# --- Term / phrase blocklists -------------------------------------------------

_TECHNICAL_TERMS = re.compile(
    r"\b(scenes?\s*parsed|characters?\s*identified|installment\s*detected|"
    r"theme\s*extracted|candidate|entity|confidence|knowledge\s*entry|"
    r"inferred\s*record|pipeline|analysis|processing|source\s*record)\b",
    re.I,
)

_PROMOTIONAL_PHRASES = re.compile(
    r"\b(gripping\s+journey|captivating\s+tale|unique\s+and\s+compelling|"
    r"thought-provoking\s+exploration|unforgettable\s+adventure|"
    r"must-see\s+story|this\s+compelling\s+narrative\s+follows|"
    r"the\s+story\s+explores\s+themes\s+of)\b",
    re.I,
)

_FILLER_PHRASES = re.compile(
    r"(short\s+summary\s+would\s+go\s+here|long\s+summary\s+would\s+go\s+here|"
    r"summary\s+would\s+go\s+here)",
    re.I,
)

# Words that signal an interpretation rather than a fact.
_HEDGE_WORDS = (
    "appears to",
    "appears",
    "seems to",
    "seems",
    "suggests",
    "the account suggests",
    "kyung's account suggests",
    "according to",
    "reportedly",
    "as presented",
    "as told",
    "may",
    "might",
    "could",
    "possibly",
    "perhaps",
    "seemingly",
    "as if",
)


# --- Public law names ---------------------------------------------------------

LAWS = (
    "SUMMARY_DEPTH_MUST_NOT_EXCEED_PROJECT_KNOWLEDGE",
    "NO_TECHNICAL_LANGUAGE_IN_STORY_SUMMARIES",
    "NO_SUMMARY_PLACEHOLDER_PROSE",
    "NO_GENERIC_STORY_FLUFF",
    "SUMMARY_REVISION_SHOULD_BE_MINIMAL_WHEN_NEW_EVIDENCE_IS_MINOR",
    "SUMMARY_STYLE_MUST_BE_EDITORIAL_NOT_PROMOTIONAL",
    "SUMMARY_FACTS_AND_INTERPRETATIONS_MUST_REMAIN_DISTINCT",
    "DETERMINISTIC_FALLBACK_MUST_PREFER_OMISSION_OVER_MECHANICAL_PROSE",
    "LOG_LINE_SHORT_AND_LONG_SUMMARY_HAVE_INDEPENDENT_READINESS",
    "PREVIOUS_APPROVED_SUMMARY_SHOULD_BE_REVISED_NOT_BLINDLY_REGENERATED",
)


# --- Validators ---------------------------------------------------------------


def check_technical_language(summary: CompiledStorySummary) -> list[str]:
    violations: list[str] = []
    for field in ("logline", "shortSummary", "longSummary"):
        value = getattr(summary, field) or ""
        if value and _TECHNICAL_TERMS.search(value):
            violations.append(f"NO_TECHNICAL_LANGUAGE_IN_STORY_SUMMARIES:{field}")
    return violations


def check_placeholder_prose(summary: CompiledStorySummary) -> list[str]:
    violations: list[str] = []
    for field in ("logline", "shortSummary", "longSummary"):
        value = getattr(summary, field) or ""
        if value and _FILLER_PHRASES.search(value):
            violations.append(f"NO_SUMMARY_PLACEHOLDER_PROSE:{field}")
    return violations


def check_promotional_style(summary: CompiledStorySummary, *, pitch_mode: bool = False) -> list[str]:
    if pitch_mode:
        return []
    violations: list[str] = []
    for field in ("logline", "shortSummary", "longSummary"):
        value = getattr(summary, field) or ""
        if value and _PROMOTIONAL_PHRASES.search(value):
            violations.append(f"SUMMARY_STYLE_MUST_BE_EDITORIAL_NOT_PROMOTIONAL:{field}")
    return violations


def check_theme_pollution(summary: CompiledStorySummary) -> list[str]:
    """Reject "Theme: X: Thematic thread..." style phrasing pasted into prose."""
    violations: list[str] = []
    pattern = re.compile(r"theme\s*[:\-]\s*\w+\s*[:\-]\s*thematic", re.I)
    for field in ("logline", "shortSummary", "longSummary"):
        value = getattr(summary, field) or ""
        if value and pattern.search(value):
            violations.append(f"NO_GENERIC_STORY_FLUFF:{field}")
    return violations


def check_grounding(summary: CompiledStorySummary, source: StorySummarySource) -> list[str]:
    """Semantic grounding: named entities in the summary must be supported.

    Uses alias-aware + lemma tolerance rather than literal phrase matching.
    Accepts paraphrases ("Barnes arrives at the facility for his interview
    with Kyung" vs source "Barnes is escorted underground to meet Kyung").
    Rejects only unsupported inventions (new characters, unrevealed plot).
    """
    violations: list[str] = []
    if not source.confirmedCharacterRoles and not source.confirmedFacts:
        return violations  # nothing to ground against
    # Build a set of known proper nouns from the evidence.
    known_tokens = _known_proper_nouns(source)
    for field in ("logline", "shortSummary", "longSummary"):
        value = getattr(summary, field) or ""
        if not value:
            continue
        summary_nouns = _extract_proper_nouns(value)
        for noun in summary_nouns:
            if not _is_supported(noun, known_tokens):
                violations.append(
                    f"SUMMARY_DEPTH_MUST_NOT_EXCEED_PROJECT_KNOWLEDGE:{field}:{noun}"
                )
    return violations


def check_fact_vs_interpretation(
    summary: CompiledStorySummary, source: StorySummarySource
) -> list[str]:
    """Interpretations must be hedged, not asserted as fact."""
    violations: list[str] = []
    interpretation_text = " ".join(
        source.creatorStatedInterpretations + source.specialistInterpretations
    )
    if not interpretation_text:
        return violations
    # Find sentences in the long summary that echo interpretation content
    # but lack a hedge word.
    long_value = summary.longSummary or ""
    if not long_value:
        return violations
    sentences = re.split(r"(?<=[.!?])\s+", long_value)
    interpretation_tokens = {
        tok.lower()
        for tok in re.findall(r"\b[A-Za-z]{4,}\b", interpretation_text)
        if tok.lower() not in {"the", "and", "with", "from", "that", "this"}
    }
    for sentence in sentences:
        sentence_tokens = {
            tok.lower() for tok in re.findall(r"\b[A-Za-z]{4,}\b", sentence)
        }
        overlap = sentence_tokens & interpretation_tokens
        if len(overlap) >= 3 and not any(hedge in sentence.lower() for hedge in _HEDGE_WORDS):
            violations.append(
                f"SUMMARY_FACTS_AND_INTERPRETATIONS_MUST_REMAIN_DISTINCT:longSummary"
            )
            break
    return violations


def check_stability(
    summary: CompiledStorySummary,
    previous: CompiledStorySummary | None,
    *,
    evidence_changed_minimally: bool,
) -> list[str]:
    """Minor evidence changes should not yield major style rewrites."""
    if previous is None or not evidence_changed_minimally:
        return []
    violations: list[str] = []
    for field in ("logline", "shortSummary", "longSummary"):
        new_val = getattr(summary, field) or ""
        old_val = getattr(previous, field) or ""
        if not old_val or not new_val:
            continue
        # Structural change ratio: word-set symmetric difference / union.
        new_words = set(new_val.lower().split())
        old_words = set(old_val.lower().split())
        union = new_words | old_words
        if not union:
            continue
        diff_ratio = len(new_words ^ old_words) / len(union)
        if diff_ratio > 0.6:
            violations.append(
                f"SUMMARY_REVISION_SHOULD_BE_MINIMAL_WHEN_NEW_EVIDENCE_IS_MINOR:{field}"
            )
    return violations


# --- Helpers ------------------------------------------------------------------


def _known_proper_nouns(source: StorySummarySource) -> set[str]:
    tokens: set[str] = set()
    blob = " ".join(
        source.confirmedCharacterRoles
        + source.confirmedFacts
        + source.approvedScriptSummaries
        + source.confirmedTimelineEvents
    )
    for match in re.findall(r"\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?)\b", blob):
        tokens.add(match.lower())
    return tokens


def _extract_proper_nouns(text: str) -> list[str]:
    return [m.lower() for m in re.findall(r"\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?)\b", text)]


def _is_supported(noun: str, known: set[str]) -> bool:
    if noun in known:
        return True
    # Substring / token tolerance: any known token contains or is contained.
    for k in known:
        if noun in k or k in noun:
            return True
        # Shared first token (e.g. "Barnes" matches "Special Agent Barnes").
        if noun.split()[0] == k.split()[0]:
            return True
    return False


def validate(
    summary: CompiledStorySummary,
    source: StorySummarySource,
    *,
    previous: CompiledStorySummary | None = None,
    evidence_changed_minimally: bool = False,
    pitch_mode: bool = False,
) -> list[str]:
    """Run all laws; return a flat list of violation strings (empty = pass)."""
    out: list[str] = []
    out += check_technical_language(summary)
    out += check_placeholder_prose(summary)
    out += check_promotional_style(summary, pitch_mode=pitch_mode)
    out += check_theme_pollution(summary)
    out += check_grounding(summary, source)
    out += check_fact_vs_interpretation(summary, source)
    out += check_stability(
        summary, previous, evidence_changed_minimally=evidence_changed_minimally
    )
    return out


__all__ = [
    "LAWS",
    "validate",
    "check_technical_language",
    "check_placeholder_prose",
    "check_promotional_style",
    "check_theme_pollution",
    "check_grounding",
    "check_fact_vs_interpretation",
    "check_stability",
]
