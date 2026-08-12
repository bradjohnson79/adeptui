"""Unit tests for the Story Summary Editor package.

Covers: laws (technical language, placeholder filler, promotional style,
theme pollution, grounding, fact-vs-interpretation, stability), theme
normalizer, readiness (per-section), and the conservative fallback.
"""

from __future__ import annotations

from app.codirector.wiki_intelligence.compiled.story_summary_editor import (
    CompiledStorySummary,
    PreviousApprovedSummary,
    StorySummarySource,
    conservative_fallback,
    logline_readiness,
    long_summary_readiness,
    normalize_theme,
    normalize_themes,
    short_summary_readiness,
    should_render,
    validate,
)


# --- Fixtures -----------------------------------------------------------------


def _source(
    *,
    facts: list[str] | None = None,
    scripts: list[str] | None = None,
    characters: list[str] | None = None,
    timeline: list[str] | None = None,
    creator_interp: list[str] | None = None,
    specialist_interp: list[str] | None = None,
    themes: list[str] | None = None,
) -> StorySummarySource:
    return StorySummarySource(
        projectId="proj-test",
        confirmedFacts=facts or [],
        approvedScriptSummaries=scripts or [],
        confirmedCharacterRoles=characters or [],
        confirmedTimelineEvents=timeline or [],
        creatorStatedInterpretations=creator_interp or [],
        specialistInterpretations=specialist_interp or [],
        inferredThemes=themes or [],
    )


def _summary(
    *,
    logline: str = "",
    short: str = "",
    long: str = "",
) -> CompiledStorySummary:
    return CompiledStorySummary(
        logline=logline,
        shortSummary=short,
        longSummary=long,
    )


# --- Theme normalizer ---------------------------------------------------------


def test_normalize_theme_strips_prefix_and_suffix_noise():
    assert normalize_theme("Theme: consciousness: Thematic thread present in the narration: consciousness.") == "Consciousness"
    assert normalize_theme("emerging theme: control") == "Control"
    assert normalize_theme("Trust") == "Trust"
    assert normalize_theme("theme") is None
    assert normalize_theme("") is None
    assert normalize_theme("ab") is None


def test_normalize_themes_dedups_case_insensitively():
    out = normalize_themes(["Consciousness", "consciousness", "Trust", "trust"])
    assert out == ["Consciousness", "Trust"]


# --- Readiness ----------------------------------------------------------------


def test_logline_readiness_minimal_without_subject():
    # No character and no recognized subject → MINIMAL.
    assert logline_readiness(_source(facts=["A story begins."])) == "MINIMAL"


def test_logline_readiness_substantial_with_character():
    src = _source(facts=["Barnes enters DW6.", "Barnes meets Kyung."], characters=["Barnes"])
    assert logline_readiness(src) in {"SUBSTANTIAL", "MATURE"}


def test_long_summary_omitted_until_movements_exist():
    src = _source(facts=["A fact."])
    assert long_summary_readiness(src) == "MINIMAL"
    assert should_render(long_summary_readiness(src)) is False


def test_independent_readiness_logline_present_long_omitted():
    src = _source(
        facts=["Barnes enters DW6.", "Barnes meets Kyung."],
        characters=["Barnes"],
    )
    log_cov = logline_readiness(src)
    long_cov = long_summary_readiness(src)
    assert should_render(log_cov) is True
    assert should_render(long_cov) is False


# --- Laws: technical language -------------------------------------------------


def test_law_rejects_technical_language():
    summary = _summary(short="2 scenes parsed; 3 characters identified.")
    violations = validate(summary, _source(facts=["A fact."]))
    assert any("NO_TECHNICAL_LANGUAGE" in v for v in violations)


def test_law_allows_clean_prose():
    summary = _summary(short="Barnes arrives at the facility to interview Kyung.")
    violations = validate(summary, _source(facts=["Barnes arrives at the facility."], characters=["Barnes"]))
    assert not any("NO_TECHNICAL_LANGUAGE" in v for v in violations)


# --- Laws: placeholder filler -------------------------------------------------


def test_law_rejects_placeholder_filler():
    summary = _summary(short="Short summary would go here.")
    violations = validate(summary, _source(facts=["A fact."]))
    assert any("NO_SUMMARY_PLACEHOLDER_PROSE" in v for v in violations)


# --- Laws: promotional style --------------------------------------------------


def test_law_rejects_promotional_style_by_default():
    summary = _summary(long="This gripping journey follows Barnes through a captivating tale.")
    violations = validate(summary, _source(facts=["Barnes travels."], characters=["Barnes"]))
    assert any("EDITORIAL_NOT_PROMOTIONAL" in v for v in violations)


def test_law_allows_promotional_in_pitch_mode():
    summary = _summary(long="This gripping journey follows Barnes.")
    violations = validate(
        summary,
        _source(facts=["Barnes travels."], characters=["Barnes"]),
        pitch_mode=True,
    )
    assert not any("EDITORIAL_NOT_PROMOTIONAL" in v for v in violations)


# --- Laws: theme pollution ----------------------------------------------------


def test_law_rejects_theme_record_pasted_into_prose():
    summary = _summary(short="Theme: consciousness: Thematic thread present.")
    violations = validate(summary, _source(facts=["A fact."]))
    assert any("NO_GENERIC_STORY_FLUFF" in v for v in violations)


# --- Laws: grounding ----------------------------------------------------------


def test_grounding_accepts_paraphrase():
    src = _source(
        facts=["Barnes is escorted underground to meet Kyung."],
        characters=["Barnes", "Kyung"],
    )
    summary = _summary(short="Barnes arrives at the facility for his interview with Kyung.")
    violations = validate(summary, src)
    assert not any("SUMMARY_DEPTH_MUST_NOT_EXCEED" in v for v in violations)


def test_grounding_rejects_invented_character():
    src = _source(facts=["Barnes enters DW6."], characters=["Barnes"])
    summary = _summary(short="Barnes confronts the villain Voss.")
    violations = validate(summary, src)
    assert any("SUMMARY_DEPTH_MUST_NOT_EXCEED" in v for v in violations)


# --- Laws: fact vs interpretation ---------------------------------------------


def test_fact_vs_interpretation_requires_hedge():
    src = _source(
        facts=["Barnes enters DW6."],
        creator_interp=["Barnes appears to doubt Kyung's account from the start."],
        characters=["Barnes"],
    )
    # Asserted as fact (no hedge) → violation.
    summary = _summary(long="Barnes doubts Kyung's account from the start.")
    violations = validate(summary, src)
    assert any("FACTS_AND_INTERPRETATIONS" in v for v in violations)


def test_fact_vs_interpretation_passes_with_hedge():
    src = _source(
        facts=["Barnes enters DW6."],
        creator_interp=["Barnes appears to doubt Kyung's account from the start."],
        characters=["Barnes"],
    )
    summary = _summary(long="Barnes appears to doubt Kyung's account from the start.")
    violations = validate(summary, src)
    assert not any("FACTS_AND_INTERPRETATIONS" in v for v in violations)


# --- Laws: stability ----------------------------------------------------------


def test_stability_flags_major_rewrite_on_minor_evidence():
    previous = _summary(long="Barnes arrives at the facility to interview Kyung about the past.")
    new = _summary(long="A detective enters a mysterious building to question a scientist about hidden memories.")
    src = _source(facts=["Barnes arrives at the facility."], characters=["Barnes"])
    violations = validate(new, src, previous=previous, evidence_changed_minimally=True)
    assert any("REVISION_SHOULD_BE_MINIMAL" in v for v in violations)


def test_stability_allows_minor_change_on_minor_evidence():
    previous = _summary(long="Barnes arrives at the facility to interview Kyung.")
    new = _summary(long="Barnes arrives at the facility to interview Kyung about the past.")
    src = _source(facts=["Barnes arrives at the facility."], characters=["Barnes"])
    violations = validate(new, src, previous=previous, evidence_changed_minimally=True)
    assert not any("REVISION_SHOULD_BE_MINIMAL" in v for v in violations)


# --- Conservative fallback ----------------------------------------------------


def test_conservative_fallback_omits_long_when_sparse():
    src = _source(facts=["A single fact."])
    out = conservative_fallback(src)
    assert out.editorMode == "deterministic"
    assert out.longSummary == ""
    assert out.longSummaryCoverage == "MINIMAL"


def test_conservative_fallback_produces_factual_synopsis_when_substantial():
    src = _source(
        facts=[
            "Barnes enters DW6 in 2027.",
            "Barnes meets Kyung Leong.",
            "Kyung recounts events from 1991.",
            "The Dreamweaver is introduced.",
            "Barnes is skeptical.",
            "DW6 is in Alaska.",
        ],
        characters=["Barnes", "Kyung"],
    )
    out = conservative_fallback(src)
    assert out.editorMode == "deterministic"
    # Long summary only renders when SUBSTANTIAL/MATURE.
    if out.longSummaryCoverage in {"SUBSTANTIAL", "MATURE"}:
        assert "Barnes" in out.longSummary
    # No editorial flourish in fallback.
    assert "gripping" not in out.longSummary.lower()
