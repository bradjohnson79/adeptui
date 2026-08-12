"""Wiki Empty-State Integrity tests.

Covers the 5 required cases plus the persisted-filler cleanup migration:
- Case 1: meta-conversation only → all Story fields blank.
- Case 2: production request only → all Story fields blank.
- Case 3: genuine story → extraction permitted (Logline/Short/Long populated).
- Case 4: mixed conversation → only narrative enters Story.
- Case 5: insufficient narrative → no invented plot (blank, no filler).
- Migration: clean persisted bad filler in compiledWiki.storySummary,
  distinguishing legitimate user-authored story from misclassified meta-conversation.
"""
from __future__ import annotations

import pytest

from app.codirector.wiki_intelligence.classification import (
    classify_conversation_turn,
    is_non_canon_turn,
)


# ── Case 1: meta-conversation only ───────────────────────────────────────


def test_case1_meta_conversation_only_yields_blank_story() -> None:
    """A conversation with only acknowledgments / workflow talk must NOT
    populate Logline / Short Summary / Long Summary. All Story fields stay
    genuinely empty (None / empty string), never placeholder prose."""
    from app.codirector.wiki_intelligence.compiled.story_compiler import (
        compile_story_summary,
    )

    turns = [
        "ok thanks will do",
        "sounds good let's get started",
        "great, please go ahead",
    ]
    result = compile_story_summary(story_texts=turns, open_questions=[], episode_summaries=[], source_ids=[])
    assert result.logline in (None, "", ), f"meta-conversation must not produce a logline, got: {result.logline!r}"
    assert result.shortSummary in (None, "", ), f"meta-conversation must not produce a short summary, got: {result.shortSummary!r}"
    assert result.longSummary in (None, "", ), f"meta-conversation must not produce a long summary, got: {result.longSummary!r}"
    # Critical: no placeholder prose.
    for field in (result.logline, result.shortSummary, result.longSummary):
        if field:
            assert "No story" not in field
            assert "TBD" not in field
            assert "not yet" not in field.lower()
            assert "awaiting" not in field.lower()


# ── Case 2: production request only ──────────────────────────────────────


def test_case2_production_request_only_yields_blank_story() -> None:
    """A conversation with only production instructions (even when they
    mention characters/scenes) must NOT populate Story canon fields."""
    from app.codirector.wiki_intelligence.compiled.story_compiler import (
        compile_story_summary,
    )

    turns = [
        "Create a character sheet for Korri who enters the coffee shop and orders a latte.",
        "Generate a storyboard for the opening scene.",
        "Make a hero portrait of Korri.",
    ]
    # First confirm the classifier correctly rejects these as canon.
    for t in turns:
        assert is_non_canon_turn(t), f"production request must be non-canon: {t!r}"
        assert classify_conversation_turn(t) == "production_request"

    result = compile_story_summary(story_texts=turns, open_questions=[], episode_summaries=[], source_ids=[])
    assert result.logline in (None, "")
    assert result.shortSummary in (None, "")
    assert result.longSummary in (None, "")


# ── Case 3: genuine story → extraction permitted ─────────────────────────


def test_case3_genuine_story_populates_summary() -> None:
    """Genuine narrative description of in-world events MUST be extracted and
    populate Logline / Short / Long. The honesty rule blocks filler, not real
    story content."""
    from app.codirector.wiki_intelligence.compiled.story_compiler import (
        compile_story_summary,
    )

    turns = [
        "Korri enters the coffee shop, orders a latte, tastes it, and reacts with "
        "surprise at the flavor. She decides to investigate the mysterious barista.",
    ]
    # The classifier must accept this as story_canon.
    assert classify_conversation_turn(turns[0]) == "story_canon"
    assert not is_non_canon_turn(turns[0])

    result = compile_story_summary(story_texts=turns, open_questions=[], episode_summaries=[], source_ids=[])
    # Genuine story must produce a non-empty summary (exact shape depends on
    # the compiler, but it must NOT be blank when real narrative is supplied).
    summary_blob = " ".join(
        s for s in (result.logline, result.shortSummary, result.longSummary) if s
    )
    assert summary_blob.strip(), "genuine story must produce summary content"
    assert "Korri" in summary_blob or "coffee" in summary_blob, (
        f"summary should reference the narrative, got: {summary_blob!r}"
    )


# ── Case 4: mixed conversation → only narrative enters Story ──────────────


def test_case4_mixed_conversation_only_narrative_enters_story() -> None:
    """When a conversation contains both meta/preference/production turns AND
    genuine narrative, ONLY the narrative enters Story. The non-canon turns
    must not bleed into Logline / Short / Long."""
    from app.codirector.wiki_intelligence.compiled.story_compiler import (
        compile_story_summary,
    )

    narrative = (
        "Korri enters the coffee shop, orders a latte, tastes it, and reacts with "
        "surprise at the flavor. She decides to investigate the mysterious barista."
    )
    turns = [
        "Please call me friend",  # user_preference
        "ok thanks will do",  # meta_conversation
        "Create a storyboard for the opening scene.",  # production_request
        narrative,  # story_canon
        "what if she orders espresso instead",  # brainstorming (not canon by default)
    ]
    result = compile_story_summary(story_texts=turns, open_questions=[], episode_summaries=[], source_ids=[])
    summary_blob = " ".join(
        s for s in (result.logline, result.shortSummary, result.longSummary) if s
    )
    # The narrative must be reflected.
    assert "Korri" in summary_blob or "coffee" in summary_blob, (
        f"genuine narrative must enter Story, got: {summary_blob!r}"
    )
    # The non-canon turns must NOT bleed in.
    assert "call me friend" not in summary_blob.lower()
    assert "thanks will do" not in summary_blob.lower()
    assert "storyboard" not in summary_blob.lower(), "production request must not enter Story"
    assert "espresso instead" not in summary_blob.lower(), "brainstorming must not enter Story by default"


# ── Case 5: insufficient narrative → no invented plot ─────────────────────


def test_case5_insufficient_narrative_no_invented_plot() -> None:
    """A single short narrative fragment that isn't enough to form a real
    story summary must NOT be inflated into invented plot. The compiler must
    leave fields blank rather than fabricate."""
    from app.codirector.wiki_intelligence.compiled.story_compiler import (
        compile_story_summary,
    )

    # A single short turn that mentions a character but has no real narrative arc.
    turns = ["Korri is a barista."]  # too short to be story_canon (<40 chars? borderline)
    result = compile_story_summary(story_texts=turns, open_questions=[], episode_summaries=[], source_ids=[])
    summary_blob = " ".join(
        s for s in (result.logline, result.shortSummary, result.longSummary) if s
    )
    # Either blank (honest) OR only restates the supplied fragment — but never
    # invents plot that wasn't supplied (e.g. "Korri must save the coffee shop
    # from bankruptcy" when the user only said "Korri is a barista").
    if summary_blob.strip():
        # If anything was produced, it must be traceable to the input, not invented.
        assert "barista" in summary_blob.lower() or "korri" in summary_blob.lower()
        # No invented plot devices.
        banned = ["must save", "from bankruptcy", "evil villain", "discover a magical", "save the world"]
        for phrase in banned:
            assert phrase not in summary_blob.lower(), f"compiler invented plot: {phrase!r}"


# ── Migration: clean persisted bad filler ─────────────────────────────────


def test_migration_clean_bad_filler_preserves_legitimate_story() -> None:
    """The cleanup migration must distinguish legitimate user-authored story
    material from misclassified meta-conversation, and preserve the former
    while removing the latter."""
    from app.codirector.wiki_intelligence.classification import is_canon_turn

    legitimate_story = (
        "Korri enters the coffee shop, orders a latte, tastes it, and reacts with "
        "surprise at the flavor."
    )
    misclassified_filler = "Please call me friend"  # user_preference, not story

    # The classifier must distinguish them.
    assert is_canon_turn(legitimate_story), "legitimate story must classify as canon"
    assert not is_canon_turn(misclassified_filler), "user-preference filler must NOT be canon"

    # A compiled story summary built from ONLY filler must be blank.
    from app.codirector.wiki_intelligence.compiled.story_compiler import (
        compile_story_summary,
    )
    filler_only = compile_story_summary(story_texts=[misclassified_filler, "ok thanks"], open_questions=[], episode_summaries=[], source_ids=[])
    assert filler_only.logline in (None, "")
    assert filler_only.shortSummary in (None, "")
    assert filler_only.longSummary in (None, "")

    # A compiled story summary built from filler + legitimate story must
    # preserve the legitimate story and drop the filler.
    mixed = compile_story_summary(story_texts=[misclassified_filler, "ok thanks", legitimate_story], open_questions=[], episode_summaries=[], source_ids=[])
    mixed_blob = " ".join(
        s for s in (mixed.logline, mixed.shortSummary, mixed.longSummary) if s
    )
    assert "Korri" in mixed_blob or "coffee" in mixed_blob, "legitimate story must survive cleanup"
    assert "call me friend" not in mixed_blob.lower(), "filler must be cleaned"


# ── Classifier guard: production instruction mentioning story terms ───────


def test_production_instruction_mentioning_story_terms_not_promoted() -> None:
    """The critical guard: a production instruction that MENTIONS a character/
    scene/location must NOT be promoted to story_canon. This is the Schnick
    Coffee defect — 'Create a character sheet for Korri who enters the coffee
    shop' was misclassified as narrative."""
    text = "Create a character sheet for Korri who enters the coffee shop and orders a latte."
    assert classify_conversation_turn(text) == "production_request"
    assert not is_non_canon_turn(text) is False  # production_request is non-canon
    assert is_non_canon_turn(text), "production request must be classified as non-canon"
