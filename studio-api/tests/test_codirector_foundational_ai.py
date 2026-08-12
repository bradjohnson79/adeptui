"""Part A — Co-Director foundational AI listening / DialoguePlan authority suite."""

from __future__ import annotations

import re

import pytest

from app.codirector.conversation.foundation.dialogue_policy import build_dialogue_plan
from app.codirector.conversation.foundation.grounding import evaluate_grounding, reply_violates_dialogue_plan
from app.codirector.conversation.foundation.intent import analyze_intent
from app.codirector.conversation.foundation.schemas import (
    CoDirectorMode,
    ConversationState,
    IntentType,
)
from app.codirector.conversation.orchestrate import run_conversation_core_turn
from app.codirector.service import _plan_system_nudge


class _FakeProject:
    def __init__(self, project_id: str = "proj-foundation", name: str = "The Dreamweaver"):
        self.id = project_id
        self.name = name
        self.primary_project_type = "web_series"
        self.settings_json = "{}"
        self.updated_at = None
        self.description = ""


class _FakeDb:
    def __init__(self, project: _FakeProject | None = None):
        self.project = project or _FakeProject()
        self.committed = False

    def get(self, model, key):  # noqa: ANN001
        name = getattr(model, "__name__", str(model))
        if name == "Project" and key == self.project.id:
            return self.project
        if name == "CoDirectorConversation":
            return None
        return None

    def add(self, obj):  # noqa: ANN001
        return obj

    def commit(self):
        self.committed = True

    def refresh(self, obj):  # noqa: ANN001
        return obj


LIVE_FAILURE = (
    "I will tell you all about The Dreamweaver as I’d like you to be familiar with "
    "the story before we move into production. Sound good?"
)

PARAPHRASES = [
    "Before we do anything else, I want to explain the story to you.",
    "Let me give you the background first, and please just listen for now.",
    "I’d rather teach you about the project before you start suggesting production steps.",
    "There is a lot you need to understand about this universe. I’m going to walk you through it.",
    "Don’t organize this yet—I just want to tell you what it is.",
]

_TITLE_PREMISE_BAD = re.compile(
    r"clear project title|one[- ]sentence (?:creative )?premise|what(?:'s| is) (?:the|your) (?:title|premise)",
    re.I,
)


def _run(msg: str, *, project_id: str = "proj-foundation", name: str = "The Dreamweaver"):
    db = _FakeDb(_FakeProject(project_id=project_id, name=name))
    return run_conversation_core_turn(
        db,
        project_id=project_id,
        messages=[{"role": "user", "content": msg}],
        user_message=msg,
    )


def test_live_failure_intent_evidence_and_listening_plan():
    intent = analyze_intent(LIVE_FAILURE)
    assert intent.primary_intent == IntentType.EXPLAIN_PROJECT
    assert intent.evidence_spans, "evidence_spans required — not labels alone"
    joined = " ".join(intent.evidence_spans).lower()
    assert "i will tell you" in joined or "will tell you" in joined
    assert "before we move into production" in joined or "production" in joined
    assert "sound good" in joined

    plan = build_dialogue_plan(intent, ConversationState())
    assert plan.mode == CoDirectorMode.LISTENING
    assert plan.question_budget == 0
    assert plan.tool_policy == "NONE"
    assert plan.workflow_advance_policy == "HOLD"

    result = _run(LIVE_FAILURE)
    assert result.usesLlmPrimary is True
    assert result.dialoguePlan.get("mode") == "LISTENING"
    assert result.dialoguePlan.get("question_budget") == 0
    assert result.snapshot.cognitiveMode == "LISTENING"
    assert result.snapshot.workflowHold is True
    assert result.snapshot.preferenceExplainBeforeProduction is True
    assert result.snapshot.activeGoal
    assert result.plan.shouldAskQuestion is False
    assert result.plan.recommendedNextStep is None
    assert not _TITLE_PREMISE_BAD.search(result.reply)
    assert "one-sentence" not in result.reply.lower()


@pytest.mark.parametrize("msg", PARAPHRASES)
def test_paraphrases_resolve_to_listening_without_intake(msg: str):
    intent = analyze_intent(msg)
    assert intent.primary_intent in {
        IntentType.EXPLAIN_PROJECT,
        IntentType.PAUSE_ACTION,
        IntentType.INFORM,
        IntentType.SET_PREFERENCE,
    }
    assert intent.evidence_spans
    plan = build_dialogue_plan(intent, ConversationState(workflow_hold=True))
    # Prefer listening/discovery; never production execute.
    assert plan.mode in {CoDirectorMode.LISTENING, CoDirectorMode.DISCOVERY}
    assert plan.workflow_advance_policy in {"HOLD", "SUGGEST"}
    if intent.primary_intent in {IntentType.EXPLAIN_PROJECT, IntentType.PAUSE_ACTION}:
        assert plan.question_budget == 0
        assert plan.workflow_advance_policy == "HOLD"

    result = _run(msg)
    assert result.usesLlmPrimary is True
    assert result.plan.shouldAskQuestion is False or result.dialoguePlan.get("question_budget", 1) == 0
    assert not _TITLE_PREMISE_BAD.search(result.reply)
    bad = reply_violates_dialogue_plan(
        result.reply,
        build_dialogue_plan(analyze_intent(msg), ConversationState(workflow_hold=True)),
    )
    assert not any("Title/premise" in n for n in bad)


def test_dialogue_plan_authority_blocks_director_title_premise_nudge():
    result = _run(LIVE_FAILURE)
    # Legacy director historically suggested title+premise; DialoguePlan HOLD must quarantine.
    assert result.plan.recommendedNextStep is None
    assert "title" not in (result.snapshot.director.recommendedNextStep or "").lower() or "premise" not in (
        result.snapshot.director.recommendedNextStep or ""
    ).lower()
    # System nudge must omit title/premise when HOLD.
    nudge = _plan_system_nudge(result.plan, result.snapshot.director)
    assert "clear project title" not in nudge.lower()
    assert "one-sentence" not in nudge.lower()
    assert "creative premise" not in nudge.lower()


def test_keep_listening_persists_mode_and_defers_questions():
    db = _FakeDb(_FakeProject())
    first = run_conversation_core_turn(
        db,
        project_id="proj-foundation",
        messages=[{"role": "user", "content": LIVE_FAILURE}],
        user_message=LIVE_FAILURE,
    )
    assert first.snapshot.cognitiveMode == "LISTENING"
    assert db.committed is True

    follow = "Keep listening; I’m not finished."
    second = run_conversation_core_turn(
        db,
        project_id="proj-foundation",
        messages=[
            {"role": "user", "content": LIVE_FAILURE},
            {"role": "assistant", "content": first.reply},
            {"role": "user", "content": follow},
        ],
        user_message=follow,
    )
    assert second.snapshot.cognitiveMode in {"LISTENING", "DISCOVERY"}
    assert second.snapshot.workflowHold is True or second.dialoguePlan.get("workflow_advance_policy") == "HOLD"
    assert second.plan.shouldAskQuestion is False


def test_grounding_rejects_title_premise_while_hold():
    intent = analyze_intent(LIVE_FAILURE)
    plan = build_dialogue_plan(intent)
    bad_reply = "Great! Choose a clear project title and a one-sentence creative premise."
    check = evaluate_grounding(
        user_message=LIVE_FAILURE,
        reply=bad_reply,
        intent=intent,
        plan=plan,
    )
    assert check.ok is False
    assert check.violates_dialogue_plan is True

    good_reply = (
        "Absolutely — tell me about The Dreamweaver whenever you’re ready. "
        "I’ll listen for story, characters, and tone before we plan production."
    )
    check2 = evaluate_grounding(
        user_message=LIVE_FAILURE,
        reply=good_reply,
        intent=intent,
        plan=plan,
    )
    assert check2.ok is True


def test_project_isolation_of_goals():
    a = _run(LIVE_FAILURE, project_id="proj-a", name="Alpha Saga")
    b = _run(
        "Before we do anything else, I want to explain the story to you.",
        project_id="proj-b",
        name="Beta Tales",
    )
    assert a.snapshot.projectId == "proj-a"
    assert b.snapshot.projectId == "proj-b"
    assert a.snapshot.activeGoal != b.snapshot.activeGoal or a.snapshot.title != b.snapshot.title


def test_generation_messages_present_for_llm_primary():
    result = _run(LIVE_FAILURE)
    assert result.usesLlmPrimary is True
    assert result.generationMessages
    assert result.generationMessages[0]["role"] == "system"
    assert "Dialogue plan" in result.generationMessages[0]["content"] or "Dialogue Plan" in (
        result.generationMessages[0]["content"]
    )
    assert result.fallbackReply
