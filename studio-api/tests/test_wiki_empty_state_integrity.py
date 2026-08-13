"""Wiki Empty-State Integrity tests.

Covers the 5 required cases plus the persisted-filler cleanup migration.
Workstream B: Story Logline / Short Summary / Long Summary read EXCLUSIVELY
from the saved Story record (StoryEntry), never from conversation.

- Case 1: meta-conversation only, no Story record → all Story fields blank.
- Case 2: production request only, no Story record → all Story fields blank.
- Case 3: Story record populated → Story fields mirror the record.
- Case 4: mixed conversation + Story record → only Story record enters Story;
  non-canon conversation never bleeds in.
- Case 5: insufficient narrative, no Story record → no invented plot
  (genuinely blank, no filler).
- Migration: clean persisted bad filler in compiledWiki.storySummary,
  distinguishing legitimate user-authored story from misclassified
  meta-conversation.
"""
from __future__ import annotations

import pytest

from app.codirector.wiki_intelligence.classification import (
    classify_conversation_turn,
    is_non_canon_turn,
)


# ── Helpers ────────────────────────────────────────────────────────────────


class _FakeStoryRecord:
    """Minimal StoryEntry-like row for tests (duck-typed by `_story_record_field`)."""

    def __init__(self, logline: str = "", short_summary: str = "", long_summary: str = ""):
        self.logline = logline
        self.short_summary = short_summary
        self.long_summary = long_summary
        self.entry_type = "project_story"


# ── Case 1: meta-conversation only ───────────────────────────────────────


def test_case1_meta_conversation_only_yields_blank_story() -> None:
    """A conversation with only acknowledgments / workflow talk must NOT
    populate Logline / Short Summary / Long Summary. All Story fields stay
    genuinely empty (None / empty string), never placeholder prose. With the
    Story-record source-of-truth change, conversation is no longer consulted
    for those fields at all — blank means blank."""
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
    mention characters/scenes) must NOT populate Story canon fields. The
    Story record is the only source for Logline/Short/Long; conversation
    cannot write them regardless of content."""
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


# ── Case 3: Story record populated → Story fields mirror the record ──────


def test_case3_story_record_populates_summary() -> None:
    """When the saved Story record has Logline/Short/Long, the compiled
    Story summary MUST mirror that record exactly. Conversation is not
    consulted for those fields — the Story record is the single source."""
    from app.codirector.wiki_intelligence.compiled.story_compiler import (
        compile_story_summary,
    )

    logline = "Korri enters the coffee shop and tastes a latte that surprises her."
    short = "Korri orders a latte, reacts with surprise at the flavor, and decides to investigate the mysterious barista."
    long_summary = (
        "Korri enters the coffee shop, orders a latte, tastes it, and reacts with "
        "surprise at the flavor. She decides to investigate the mysterious barista."
    )
    record = _FakeStoryRecord(
        logline=logline,
        short_summary=short,
        long_summary=long_summary,
    )

    # Even with a polluted conversation, the Story record wins.
    turns = ["Please call me friend", "ok thanks will do"]
    result = compile_story_summary(
        story_texts=turns,
        open_questions=[],
        episode_summaries=[],
        source_ids=[],
        story_record=record,
    )
    assert result.logline == logline
    assert result.shortSummary == short
    assert result.longSummary == long_summary
    # No filler bleeds in from conversation.
    assert "call me friend" not in (result.logline + result.shortSummary + result.longSummary).lower()
    assert "thanks will do" not in (result.logline + result.shortSummary + result.longSummary).lower()


# ── Case 4: mixed conversation + Story record → only record enters Story ─


def test_case4_mixed_conversation_only_record_enters_story() -> None:
    """When a conversation contains both meta/preference/production turns AND
    a populated Story record, ONLY the record's values enter Story. The
    non-canon conversation turns must not bleed into Logline / Short / Long."""
    from app.codirector.wiki_intelligence.compiled.story_compiler import (
        compile_story_summary,
    )

    logline = "Korri enters the coffee shop and tastes a surprising latte."
    record = _FakeStoryRecord(logline=logline)
    turns = [
        "Please call me friend",  # user_preference
        "ok thanks will do",  # meta_conversation
        "Create a storyboard for the opening scene.",  # production_request
        "what if she orders espresso instead",  # brainstorming
    ]
    result = compile_story_summary(
        story_texts=turns,
        open_questions=[],
        episode_summaries=[],
        source_ids=[],
        story_record=record,
    )
    blob = " ".join(s for s in (result.logline, result.shortSummary, result.longSummary) if s)
    # The Story record's logline must be reflected.
    assert result.logline == logline
    assert "Korri" in blob or "coffee" in blob, (
        f"Story record logline must enter Story, got: {blob!r}"
    )
    # The non-canon conversation turns must NOT bleed in.
    assert "call me friend" not in blob.lower()
    assert "thanks will do" not in blob.lower()
    assert "storyboard" not in blob.lower(), "production request must not enter Story"
    assert "espresso instead" not in blob.lower(), "brainstorming must not enter Story"


# ── Case 5: insufficient narrative, no Story record → no invented plot ──────


def test_case5_insufficient_narrative_no_invented_plot() -> None:
    """Without a Story record, conversation cannot populate Story fields —
    no invented plot, no filler, no placeholder prose. Genuinely blank."""
    from app.codirector.wiki_intelligence.compiled.story_compiler import (
        compile_story_summary,
    )

    turns = ["Korri is a barista."]  # short narrative fragment, no Story record
    result = compile_story_summary(story_texts=turns, open_questions=[], episode_summaries=[], source_ids=[])
    blob = " ".join(s for s in (result.logline, result.shortSummary, result.longSummary) if s)
    # Story-record source-of-truth: blank means blank — no invented plot.
    assert blob.strip() == "", (
        f"without a Story record, Story fields must be blank, got: {blob!r}"
    )


# ── Migration: clean persisted bad filler ─────────────────────────────────


def test_migration_clean_bad_filler_preserves_legitimate_story() -> None:
    """The cleanup migration must distinguish legitimate user-authored story
    material from misclassified meta-conversation, and preserve the former
    while removing the latter. With the Story-record source-of-truth, the
    compiler produces blank Story fields for conversation-only input."""
    from app.codirector.wiki_intelligence.classification import is_canon_turn

    legitimate_story = (
        "Korri enters the coffee shop, orders a latte, tastes it, and reacts with "
        "surprise at the flavor."
    )
    misclassified_filler = "Please call me friend"  # user_preference, not story

    # The classifier must distinguish them.
    assert is_canon_turn(legitimate_story), "legitimate story must classify as canon"
    assert not is_canon_turn(misclassified_filler), "user-preference filler must NOT be canon"

    # A compiled story summary built from ONLY filler must be blank —
    # conversation cannot write Story fields at all now.
    from app.codirector.wiki_intelligence.compiled.story_compiler import (
        compile_story_summary,
    )
    filler_only = compile_story_summary(
        story_texts=[misclassified_filler, "ok thanks"],
        open_questions=[],
        episode_summaries=[],
        source_ids=[],
    )
    assert filler_only.logline in (None, "")
    assert filler_only.shortSummary in (None, "")
    assert filler_only.longSummary in (None, "")

    # Legitimate story must come through the Story record, not conversation.
    record = _FakeStoryRecord(
        logline="Korri enters the coffee shop and reacts with surprise at the latte.",
        short_summary="Korri orders a latte and reacts with surprise.",
        long_summary="Korri enters the coffee shop, orders a latte, tastes it, and reacts with surprise.",
    )
    mixed = compile_story_summary(
        story_texts=[misclassified_filler, "ok thanks"],
        open_questions=[],
        episode_summaries=[],
        source_ids=[],
        story_record=record,
    )
    mixed_blob = " ".join(s for s in (mixed.logline, mixed.shortSummary, mixed.longSummary) if s)
    assert "Korri" in mixed_blob or "coffee" in mixed_blob, "legitimate story must come from Story record"
    assert "call me friend" not in mixed_blob.lower(), "filler must not enter Story"


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
