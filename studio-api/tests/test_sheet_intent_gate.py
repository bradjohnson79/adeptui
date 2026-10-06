"""ORDER 11B: ERS/CRS/PRS sheet curriculum activates only on explicit sheet asks."""

from __future__ import annotations

from app.codirector.knowledgebase.retrieve import render_knowledge_context_block, retrieve_knowledge
from app.codirector.knowledgebase.sheet_intent_gate import (
    SHEET_FORMAL_CURRICULUM_IDS,
    is_explicit_sheet_knowledge_intent,
)

ERS_LECTURE = "An Environment Reference Sheet is one production page"
CRS_LECTURE = "A Character Reference Sheet is the official look"


def _ids(message: str, **kwargs):
    return set(retrieve_knowledge(message, **kwargs).doc_ids)


def test_background_attach_does_not_trigger_sheet_curriculum() -> None:
    for msg in (
        "Use attached image as background",
        "use this as a background",
        "use attached as visual reference for timeline",
        "attach this for the timeline",
        "background plate for the scene",
    ):
        assert not is_explicit_sheet_knowledge_intent(msg)
        ids = _ids(msg)
        assert not (ids & SHEET_FORMAL_CURRICULUM_IDS), (msg, ids)
        block = render_knowledge_context_block(msg) or ""
        assert ERS_LECTURE not in block
        assert CRS_LECTURE not in block


def test_explicit_ers_asks_still_get_sheet_curriculum() -> None:
    for msg in (
        "create Environment Reference Sheet",
        "validate ERS",
        "make an ERS for this cafe",
        "what is an ERS",
    ):
        assert is_explicit_sheet_knowledge_intent(msg)
        ids = _ids(msg)
        assert ids & {"ers-law", "ers-spec"}, (msg, ids)
        block = render_knowledge_context_block(msg) or ""
        assert ERS_LECTURE in block


def test_explicit_crs_ask_still_gets_character_identity() -> None:
    msg = "create a character reference sheet"
    assert is_explicit_sheet_knowledge_intent(msg)
    ids = _ids(msg)
    assert "character-identity" in ids
    block = render_knowledge_context_block(msg) or ""
    assert CRS_LECTURE in block


def test_purpose_environment_reference_sheet_bypasses_message_gate() -> None:
    msg = "Use attached image as background"
    assert not is_explicit_sheet_knowledge_intent(msg)
    assert is_explicit_sheet_knowledge_intent(
        msg, purpose="environment_reference_sheet"
    )
    ids = _ids(msg, purpose="environment_reference_sheet")
    assert ids & {"ers-law", "ers-spec"}


def test_negated_sheet_refusals_do_not_activate() -> None:
    for msg in (
        "Do NOT make an ERS",
        "don't create an ERS",
        "never generate a character reference sheet",
        "Use as background. Do NOT make an ERS.",
        "Use attached image as background. Do NOT make an ERS.",
        "no ERS",
        "without an environment reference sheet",
    ):
        assert not is_explicit_sheet_knowledge_intent(msg), msg
        ids = _ids(msg)
        assert not (ids & SHEET_FORMAL_CURRICULUM_IDS), (msg, ids)
        block = render_knowledge_context_block(msg) or ""
        assert ERS_LECTURE not in block
        assert CRS_LECTURE not in block


def test_affirmative_sheet_ask_with_unrelated_negation_still_activates() -> None:
    msg = "create an ERS, do not make a CRS"
    assert is_explicit_sheet_knowledge_intent(msg)
    ids = _ids(msg)
    assert ids & {"ers-law", "ers-spec"}
