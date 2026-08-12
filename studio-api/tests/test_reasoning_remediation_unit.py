"""Unit coverage for leaked-reasoning separation used by remediation."""

from __future__ import annotations

from app.codirector.creator_response_gate import is_contaminated, separate_leaked_reasoning


def test_remediation_preserves_creator_portion():
    leaked = (
        "Here's a thinking process\n"
        "Analyze User Input\n"
        "Draft Construction\n\n"
        "I've tracked the harbor rule and I'm ready for the next beat."
    )
    assert is_contaminated(leaked)
    creator, internal = separate_leaked_reasoning(leaked)
    assert creator
    assert "harbor" in creator.lower() or "ready" in creator.lower()
    assert internal
    assert "Analyze User Input" not in creator


def test_full_contamination_quarantines():
    only_think = "Constraint Check and system prompt and question budget review."
    creator, internal = separate_leaked_reasoning(only_think)
    assert creator == "" or not is_contaminated(creator)
    assert internal or creator == ""
