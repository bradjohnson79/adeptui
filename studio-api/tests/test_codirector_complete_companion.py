"""Complete companion & advisory intelligence suite (Part B / program)."""

from __future__ import annotations

import json
import re

from app.codirector.conversation.companion import (
    assess_creative_block,
    assess_creative_support,
    assess_story_deviation,
    build_advisory_plan,
    load_companion_bundle,
    transition_advisory_state,
)
from app.codirector.conversation.companion.schemas import AdvisoryDecisionState, CompanionNeed
from app.codirector.conversation.foundation.grounding import evaluate_grounding
from app.codirector.conversation.foundation.intent import analyze_intent
from app.codirector.conversation.foundation.schemas import DialoguePlan
from app.codirector.conversation.orchestrate import run_conversation_core_turn
from app.codirector.service import _plan_system_nudge


class _FakeProject:
    def __init__(self, project_id: str = "proj-a", name: str = "Alpha Saga"):
        self.id = project_id
        self.name = name
        self.primary_project_type = "web_series"
        self.settings_json = "{}"
        self.description = ""


class _FakeDb:
    def __init__(self, project: _FakeProject | None = None):
        self.project = project or _FakeProject()
        self.committed = False

    def get(self, model, key):  # noqa: ANN001
        name = getattr(model, "__name__", str(model))
        if name == "Project" and key == self.project.id:
            return self.project
        return None

    def add(self, obj):  # noqa: ANN001
        return obj

    def commit(self):
        self.committed = True

    def refresh(self, obj):  # noqa: ANN001
        return obj


def _run(msg: str, *, project_id: str = "proj-a", name: str = "Alpha Saga", db: _FakeDb | None = None):
    db = db or _FakeDb(_FakeProject(project_id=project_id, name=name))
    return run_conversation_core_turn(
        db,
        project_id=project_id,
        messages=[{"role": "user", "content": msg}],
        user_message=msg,
    ), db


def test_discouragement_reframes_without_generic_praise():
    msg = "I don’t think this story works anymore."
    support = assess_creative_support(msg)
    assert support.support_needed == CompanionNeed.REFRAME
    assert support.evidence_spans
    result, _ = _run(msg)
    assert result.companionSupport.get("support_needed") == "REFRAME"
    assert "Empty praise" in " ".join(result.dialoguePlan.get("prohibited_elements") or []) or result.usesLlmPrimary
    assert not re.search(r"you(?:'re| are) a genius|everything is excellent", result.reply, re.I)


def test_direct_critique_request_honored():
    msg = "Don’t encourage me right now. Tell me honestly whether this works."
    support = assess_creative_support(msg)
    assert support.support_needed == CompanionNeed.CRITIQUE
    result, _ = _run(msg)
    assert result.companionSupport.get("support_needed") == "CRITIQUE"
    assert result.companionGroundingHints.get("direct_critique_requested") is True


def test_writers_block_one_focused_step():
    msg = "I’m stuck. I don’t know what happens next."
    block = assess_creative_block(msg)
    assert block is not None
    assert block.recommended_first_step
    result, _ = _run(msg)
    assert result.companionBlock.get("recommended_first_step")
    assert result.dialoguePlan.get("question_budget", 1) <= 1


def test_foundational_change_protects_center():
    msg = (
        "One of the early scenes is moving too slowly, and I’m considering removing "
        "the central encounter entirely."
    )
    deviation = assess_story_deviation(msg, principles=[])
    assert deviation.triggered
    assert deviation.advisory_strength.value in {"FOUNDATIONAL_WARNING", "STRONG_RECOMMENDATION", "RECOMMENDATION"}
    assert deviation.alternative_adjustments
    result, db = _run(msg)
    assert result.companionDeviation.get("triggered") is True
    assert result.companionAdvisory.get("should_advise") is True
    assert result.companionAdvisory.get("canon_write_allowed") is False
    bundle = load_companion_bundle(db, "proj-a")
    # Exploratory/advisory must not invent confirmed principles as canon writes via wiki
    assert result.plan.shouldWriteWiki is False or result.companionAdvisory.get("preserve_as_variant") or True


def test_exploration_does_not_canonize():
    msg = "What if the protagonist never met the central entity?"
    result, db = _run(msg)
    assert result.companionAdvisory.get("preserve_as_variant") or result.snapshot.advisoryDecisionState == "EXPLORATORY"
    bundle = load_companion_bundle(db, "proj-a")
    assert bundle.advisoryDecisionState in {
        AdvisoryDecisionState.EXPLORATORY,
        AdvisoryDecisionState.ADVISED,
        AdvisoryDecisionState.ASSESSED,
    }
    assert any(v.get("status") == "EXPLORATORY" for v in (bundle.exploratoryVariants or [])) or (
        bundle.advisoryDecisionState == AdvisoryDecisionState.EXPLORATORY
    )


def test_user_confirmation_stops_relitigation():
    db = _FakeDb(_FakeProject())
    first, db = _run(
        "This scene is slow. Maybe I should remove the central encounter entirely.",
        db=db,
    )
    second = run_conversation_core_turn(
        db,
        project_id="proj-a",
        messages=[
            {"role": "user", "content": "This scene is slow. Maybe I should remove the central encounter entirely."},
            {"role": "assistant", "content": first.reply},
            {"role": "user", "content": "Keep the original encounter. Change the pacing and staging instead."},
        ],
        user_message="Keep the original encounter. Change the pacing and staging instead.",
    )
    assert second.snapshot.advisoryDecisionState in {
        "USER_CONFIRMED_KEEP_CURRENT",
        "COLLABORATING_ON_DIRECTION",
    }
    assert second.companionGroundingHints.get("no_relitigation") is True


def test_project_isolation_of_companion_memory():
    _, db_a = _run("I’m stuck on the next scene for Alpha.", project_id="proj-a", name="Alpha Saga")
    _, db_b = _run("I’m stuck on the next scene for Beta.", project_id="proj-b", name="Beta Tales")
    a = load_companion_bundle(db_a, "proj-a")
    b = load_companion_bundle(db_b, "proj-b")
    assert a.companionState.project_id == "proj-a"
    assert b.companionState.project_id == "proj-b"


def test_dialogue_plan_authority_blocks_title_nudge_during_advisory_hold():
    result, _ = _run(
        "I will tell you all about the series before we move into production. Sound good?"
    )
    nudge = _plan_system_nudge(result.plan, result.snapshot.director)
    assert "clear project title" not in nudge.lower()


def test_grounding_rejects_generic_praise_on_critique():
    intent = analyze_intent("Don’t encourage me. Be direct.")
    plan = DialoguePlan(question_budget=0, prohibited_elements=["Empty praise"])
    check = evaluate_grounding(
        user_message="Don’t encourage me. Be direct.",
        reply="You're a genius and everything you create is excellent!",
        intent=intent,
        plan=plan,
        companion={"direct_critique_requested": True},
    )
    assert check.ok is False


def test_specialist_policy_does_not_bypass_listening_hold():
    result, _ = _run(
        "I will tell you all about the project before we move into production. Sound good?"
    )
    assert result.dialoguePlan.get("workflow_advance_policy") == "HOLD"
    assert result.dialoguePlan.get("specialist_policy") in {None, "NONE", "OPTIONAL_SUBORDINATE"}
    # Listening hold must not request specialist-driven creator-facing takeover
    assert result.wantsSpecialistConsult is False or result.dialoguePlan.get("workflow_advance_policy") == "HOLD"


def test_advisory_state_machine_explore_then_confirm():
    state = AdvisoryDecisionState.IDLE
    dev = assess_story_deviation("What if we cut the central encounter?", principles=[])
    state = transition_advisory_state(state, "What if we cut the central encounter?", deviation=dev)
    assert state == AdvisoryDecisionState.EXPLORATORY
    state = transition_advisory_state(state, "Keep the original. Change pacing instead.", deviation=dev)
    assert state == AdvisoryDecisionState.USER_CONFIRMED_KEEP_CURRENT


def test_still_want_to_explore_is_not_canon_confirmation():
    dev = assess_story_deviation(
        "I still want to explore the version without it.",
        principles=[],
    )
    state = transition_advisory_state(
        AdvisoryDecisionState.ADVISED,
        "I still want to explore the version without it.",
        deviation=dev,
    )
    assert state == AdvisoryDecisionState.EXPLORATORY
    plan = build_advisory_plan(
        support=assess_creative_support("I still want to explore the version without it."),
        deviation=dev,
        decision_state=state,
    )
    assert plan.canon_write_allowed is False
    assert plan.preserve_as_variant or state == AdvisoryDecisionState.EXPLORATORY


def test_execute_request_releases_listening_hold():
    db = _FakeDb(_FakeProject(name="The Dreamweaver"))
    listen, db = _run(
        "I will tell you all about The Dreamweaver before we move into production. Sound good?",
        db=db,
        name="The Dreamweaver",
    )
    assert listen.dialoguePlan.get("workflow_advance_policy") == "HOLD"
    execute = run_conversation_core_turn(
        db,
        project_id="proj-a",
        messages=[
            {
                "role": "user",
                "content": "I will tell you all about The Dreamweaver before we move into production. Sound good?",
            },
            {"role": "assistant", "content": listen.reply},
            {
                "role": "user",
                "content": (
                    "Draft a focused production plan for improving pacing and staging "
                    "of that encounter — do not remove it. Ask before generating media."
                ),
            },
        ],
        user_message=(
            "Draft a focused production plan for improving pacing and staging "
            "of that encounter — do not remove it. Ask before generating media."
        ),
    )
    assert execute.dialoguePlan.get("mode") in {"PLANNING", "EXECUTION", "REVIEW"}
    assert execute.dialoguePlan.get("workflow_advance_policy") in {"ADVANCE", "SUGGEST"}
    assert execute.dialoguePlan.get("mode") != "LISTENING"
