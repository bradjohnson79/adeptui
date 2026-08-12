"""Wiki must store project knowledge, not conversation residue."""

from __future__ import annotations

from app.codirector.wiki import _is_conversation_residue, _meaningful_user_messages


def test_questions_and_greetings_are_residue():
    assert _is_conversation_residue("What should we do next?")
    assert _is_conversation_residue("How do we start?")
    assert _is_conversation_residue("Thanks!")
    assert _is_conversation_residue("ok")
    assert _is_conversation_residue("Create a scene")
    assert _is_conversation_residue("Approve that")


def test_lore_and_corrections_are_not_residue():
    assert not _is_conversation_residue(
        "The Dreamweaver is a mythic drama about a harbor child who hears a lantern calling."
    )
    assert not _is_conversation_residue(
        "Correction: the signal came from a crashed probe, not the facility."
    )
    assert not _is_conversation_residue(
        "Create a world where tide-worn lanterns remember every promise the harbor ever made."
    )


def test_meaningful_user_messages_filters_residue():
    messages = [
        {"role": "user", "id": "1", "content": "What should we do next?"},
        {"role": "assistant", "id": "2", "content": "We could define the lead."},
        {
            "role": "user",
            "id": "3",
            "content": "The lead is Korri, a tide-worn dreamweaver from Harbor Ward.",
        },
        {"role": "user", "id": "4", "content": "Thanks"},
    ]
    out = _meaningful_user_messages(messages)
    assert len(out) == 1
    assert "Korri" in out[0]["content"]
