"""Creator-facing isolation — never promote thinking; contamination gate."""

from __future__ import annotations

from app.codirector.creator_response_gate import (
    extract_creator_content,
    find_contamination,
    find_jargon,
    gate_creator_facing,
    is_contaminated,
    separate_leaked_reasoning,
)


def test_extract_never_promotes_thinking():
    turn = extract_creator_content({"content": "", "thinking": "Analyze User Input carefully"})
    assert turn.creatorFacingContent == ""
    assert turn.internalReasoning
    assert "Analyze" in turn.internalReasoning


def test_contamination_patterns():
    dirty = "Here's a thinking process.\nAnalyze User Input\nThen Draft Construction."
    assert is_contaminated(dirty)
    assert find_contamination(dirty)


def test_gate_suppresses_contaminated_without_separable_answer():
    gated = gate_creator_facing("Constraint Check: question budget exceeded. System prompt says…")
    assert gated.contaminated
    assert gated.creatorFacingContent == ""


def test_separate_keeps_creator_tail():
    raw = (
        "Here's a thinking process\nAnalyze User Input\n\n"
        "I've noted Korri's sarcastic edge and I'm with you on that direction."
    )
    creator, internal = separate_leaked_reasoning(raw)
    assert creator
    assert "Korri" in creator or "sarcastic" in creator.lower()
    assert internal


def test_jargon_detection():
    hits = find_jargon("We hit the grounding gate and context budget.")
    assert hits
