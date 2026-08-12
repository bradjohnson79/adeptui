"""M41 Wave 4 — plan state machine (M41-CD-59…62)."""

from __future__ import annotations

import pytest

from app.codirector.errors import PLAN_ALREADY_TERMINAL, PLAN_STATE_TRANSITION_INVALID, CoDirectorError
from app.codirector.plans.state_machine import assert_plan_transition, assert_step_transition


def test_m41_cd_59_valid_plan_state_transitions_succeed() -> None:
    """M41-CD-59 Valid plan-state transitions succeed."""
    assert_plan_transition("draft", "proposed", command="propose")
    assert_plan_transition("proposed", "approved", command="approve")
    assert_plan_transition("approved", "ready", command="approve")
    assert_plan_transition("ready", "paused", command="pause")
    assert_plan_transition("paused", "ready", command="resume")
    assert_plan_transition("ready", "cancelled", command="cancel")
    assert_plan_transition("cancelled", "archived", command="archive")


def test_m41_cd_60_invalid_plan_state_transitions_are_rejected() -> None:
    """M41-CD-60 Invalid plan-state transitions are rejected."""
    with pytest.raises(CoDirectorError) as ei:
        assert_plan_transition("draft", "completed", command="approve")
    assert ei.value.code == PLAN_STATE_TRANSITION_INVALID
    with pytest.raises(CoDirectorError) as ei2:
        assert_plan_transition("archived", "ready", command="resume")
    assert ei2.value.code in {PLAN_STATE_TRANSITION_INVALID, PLAN_ALREADY_TERMINAL}
    with pytest.raises(CoDirectorError) as ei3:
        assert_plan_transition("draft", "in_progress", command="propose")
    assert ei3.value.code == PLAN_STATE_TRANSITION_INVALID


def test_m41_cd_61_terminal_plans_cannot_resume_or_mutate_illegally() -> None:
    """M41-CD-61 Terminal plans cannot resume or mutate illegally."""
    with pytest.raises(CoDirectorError) as ei:
        assert_plan_transition("cancelled", "ready", command="resume")
    assert ei.value.code in {PLAN_ALREADY_TERMINAL, PLAN_STATE_TRANSITION_INVALID}
    with pytest.raises(CoDirectorError):
        assert_plan_transition("archived", "proposed", command="propose")


def test_m41_cd_62_pause_and_resume_preserve_history_edges() -> None:
    """M41-CD-62 Pause and resume preserve plan state and history (transition edges)."""
    assert_plan_transition("ready", "paused", command="pause")
    assert_plan_transition("paused", "ready", command="resume")
    assert_plan_transition("blocked", "paused", command="pause")
    assert_plan_transition("paused", "blocked", command="resume")
    assert_step_transition("ready", "paused")
    assert_step_transition("paused", "ready")
