"""Co-Director execution state machine + confirmation-first router tests.

Spec §2 (Execution State Machine): state must survive across conversational turns.
Spec §4 (Confirmation Resolution): "Yes, proceed" → dispatch pending execution.
Spec §35 (Deterministic Confirmation Router): confirmation handling BEFORE generic intent.
"""
from __future__ import annotations

import pytest

from app.codirector.execution.pending_store import (
    PendingExecution,
    PENDING_STATES,
)
from app.codirector.routing.deterministic import (
    is_execution_confirmation,
    is_execution_rejection,
)


# --- Confirmation phrase coverage (spec §4, §49) ---

CONFIRMATION_PHRASES = [
    "yes",
    "Yes",
    "yes proceed",
    "Yes, proceed.",
    "proceed",
    "Proceed",
    "go ahead",
    "Go ahead",
    "do it",
    "Do it",
    "continue",
    "Continue",
    "start",
    "Start",
    "generate it",
    "Generate it",
    "please proceed",
    "Please proceed",
    "please continue",
    "approved",
    "Approved",
    "sounds good",
    "Sounds good",
    "let's do it",
    "alright",
    "ok",
    "okay",
    "sure",
    "confirmed",
    "looks good",
    "perfect",
    "that works",
    "that's fine",
]

REJECTION_PHRASES = [
    "no",
    "no thanks",
    "cancel",
    "stop",
    "don't",
    "reject",
    "decline",
    "nope",
    "never mind",
    "discard",
    "revert",
    "undo",
]

CONVERSATIONAL_PHRASES = [
    "What kind of storyboard would work here?",
    "Tell me about the scene",
    "Can you describe Korri?",
    "What would be a good four-shot structure?",
    "I'm not sure about the framing",
]


@pytest.mark.parametrize("phrase", CONFIRMATION_PHRASES)
def test_confirmation_phrases_match(phrase: str):
    """Spec §49: all confirmation phrases must resolve pending execution."""
    assert is_execution_confirmation(phrase), f"Expected confirmation match for: {phrase!r}"


@pytest.mark.parametrize("phrase", REJECTION_PHRASES)
def test_rejection_phrases_match(phrase: str):
    """Rejection phrases must be detected."""
    assert is_execution_rejection(phrase), f"Expected rejection match for: {phrase!r}"


@pytest.mark.parametrize("phrase", CONVERSATIONAL_PHRASES)
def test_conversational_phrases_not_confirmation(phrase: str):
    """Spec §50: conversational questions must NOT trigger execution dispatch."""
    assert not is_execution_confirmation(phrase), f"Unexpected confirmation match for: {phrase!r}"


def test_pending_execution_state_machine_states():
    """Spec §2: required states present."""
    required = {
        "IDLE",
        "PLANNING",
        "AWAITING_REQUIRED_INPUT",
        "AWAITING_CONFIRMATION",
        "READY_TO_DISPATCH",
        "EXECUTING",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
    }
    assert required.issubset(set(PENDING_STATES))


def test_pending_execution_defaults():
    """PendingExecution defaults are safe."""
    pending = PendingExecution(capability="storyboard.generate", project_id="proj1")
    assert pending.state == "IDLE"
    assert pending.requested_output_count == 1
    assert pending.confirmation_required is False
    assert pending.missing_required_fields == []


def test_pending_execution_round_trip():
    """PendingExecution serializes/deserializes cleanly."""
    pending = PendingExecution(
        capability="storyboard.generate",
        project_id="proj1",
        intent="EXECUTION",
        unified_intent={"intent": "EXECUTION", "capability": "storyboard.generate", "confidence": 0.9},
        requested_parameters={"count": 4},
        resolved_context={"count": 4, "character_name": "Korri"},
        requested_output_count=4,
        confirmation_required=True,
        confirmation_question="Shall I proceed?",
        state="AWAITING_CONFIRMATION",
    )
    data = pending.model_dump(mode="json")
    restored = PendingExecution(**data)
    assert restored.capability == "storyboard.generate"
    assert restored.state == "AWAITING_CONFIRMATION"
    assert restored.requested_output_count == 4
    assert restored.unified_intent["capability"] == "storyboard.generate"
