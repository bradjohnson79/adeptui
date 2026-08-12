"""Semantic corpus for Co-Director Conversation Core."""

from __future__ import annotations

import re

from app.codirector.conversation.creative_state import update_creative_state as csm_update
from app.codirector.conversation.orchestrate import run_conversation_core_turn as run_turn


class _FakeProject:
    def __init__(self, project_id: str = "proj-1", name: str = "Untitled Project"):
        self.id = project_id
        self.name = name
        self.primary_project_type = "web_series"
        self.settings_json = "{}"
        self.updated_at = None


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


def test_creative_state_main_character():
    stage, substate, changed = csm_update("Vision", "Premise", "Let's work on the main character.")
    assert stage == "Characters"
    assert substate == "Lead Character"
    assert changed is True


def test_project_introduction_semantics():
    db = _FakeDb(_FakeProject(name="Sandbox"))
    intro = (
        "I am going to tell you about my web series, The Dreamweaver, its lore, characters, "
        "connection to The Adept Chronicles, and the first season we will build."
    )
    result = run_turn(db, project_id="proj-1", messages=[{"role": "user", "content": intro}], user_message=intro)
    assert result.plan.responseMode == "intro"
    assert result.plan.shouldAskQuestion is False
    assert "Dreamweaver" in result.reply
    assert "questionnaire" in result.reply.lower() or "Season" in result.reply
    assert "0.95" not in result.reply
    assert "{" not in result.reply
    assert result.score.overall >= 0.5


def test_next_step_recommendation():
    db = _FakeDb(_FakeProject(name="The Dreamweaver"))
    msg = "What should we do next?"
    result = run_turn(db, project_id="proj-1", messages=[{"role": "user", "content": msg}], user_message=msg)
    assert result.plan.primaryIntent == "recommend_next_step"
    assert result.plan.shouldAskQuestion is False
    assert "recommend" in result.reply.lower() or "next" in result.reply.lower()
    # Question must not become wiki candidate
    assert not any("what should we do next" in c.text.lower() for c in result.plan.wikiCandidates)


def test_define_next_recommendation():
    db = _FakeDb(_FakeProject(name="The Dreamweaver"))
    msg = "What should we define next?"
    result = run_turn(db, project_id="proj-1", messages=[{"role": "user", "content": msg}], user_message=msg)
    assert result.plan.primaryIntent == "recommend_next_step"
    assert result.plan.responseMode == "recommend_next_step"
    assert "recommend" in result.reply.lower() or "next" in result.reply.lower()


def test_invite_continuation_no_questionnaire():
    db = _FakeDb()
    msg = "Let me begin with the Dreamweaver itself."
    result = run_turn(db, project_id="proj-1", messages=[{"role": "user", "content": msg}], user_message=msg)
    assert result.plan.primaryIntent == "invite_continuation"
    assert result.plan.shouldAskQuestion is False
    assert "keep going" in result.reply.lower() or "with you" in result.reply.lower()


def test_character_stage_asks_one_foundation_question():
    db = _FakeDb(_FakeProject(name="The Dreamweaver"))
    msg = "I want to start with the main character."
    result = run_turn(db, project_id="proj-1", messages=[{"role": "user", "content": msg}], user_message=msg)
    assert result.snapshot.currentStage == "Characters"
    assert result.snapshot.currentSubstate == "Lead Character"
    assert result.plan.shouldAskQuestion is True
    assert result.plan.selectedQuestion
    assert result.reply.count("?") <= 2


def test_signal_lore_reply_acknowledges_substance():
    db = _FakeDb(_FakeProject(name="The Dreamweaver"))
    msg = "The signal lasted 47 minutes and carried a mathematical structure no one could decode."
    result = run_turn(db, project_id="proj-1", messages=[{"role": "user", "content": msg}], user_message=msg)
    reply_l = result.reply.lower()
    assert "keep going" in reply_l
    assert any(anchor in reply_l for anchor in ("signal", "47", "mathematical structure"))


def test_yes_begin_with_main_character_stays_in_character_flow():
    db = _FakeDb(_FakeProject(name="The Dreamweaver"))
    first_msg = "Let's work on the main character."
    first = run_turn(db, project_id="proj-1", messages=[{"role": "user", "content": first_msg}], user_message=first_msg)
    follow_up = "Yes, begin with the main character."
    second = run_turn(
        db,
        project_id="proj-1",
        messages=[
            {"role": "user", "content": first_msg},
            {"role": "assistant", "content": first.reply},
            {"role": "user", "content": follow_up},
        ],
        user_message=follow_up,
    )
    assert second.snapshot.currentStage == "Characters"
    assert second.snapshot.currentSubstate == "Lead Character"
    assert second.plan.primaryIntent != "invite_continuation"
    assert "great, let's focus on the lead character first" in second.reply.lower()


def test_correction_supersedes_old_fact():
    project = _FakeProject(name="The Dreamweaver")
    db = _FakeDb(project)
    # Seed snapshot with a facility fact via first lore turn
    lore = "The mysterious signal came from the research facility under the harbor."
    first = run_turn(db, project_id="proj-1", messages=[{"role": "user", "content": lore}], user_message=lore)
    assert first.snapshot.knowledgeEntries

    correction = "Correction: the signal came from a crashed probe, not the facility."
    second = run_turn(
        db,
        project_id="proj-1",
        messages=[
            {"role": "user", "content": lore},
            {"role": "assistant", "content": first.reply},
            {"role": "user", "content": correction},
        ],
        user_message=correction,
    )
    assert second.plan.primaryIntent == "confirm_correction"
    states = {e.text: e.state for e in second.snapshot.knowledgeEntries}
    assert any(state == "superseded" for state in states.values()) or any(
        e.state == "confirmed" and "probe" in e.text.lower() for e in second.snapshot.knowledgeEntries
    )


def test_rejection_marks_rejected():
    project = _FakeProject(name="The Dreamweaver")
    db = _FakeDb(project)
    lore = "We should open with a neon cyberpunk title card."
    first = run_turn(db, project_id="proj-1", messages=[{"role": "user", "content": lore}], user_message=lore)
    reject = "Reject the neon cyberpunk title card idea. Do not use it."
    second = run_turn(
        db,
        project_id="proj-1",
        messages=[
            {"role": "user", "content": lore},
            {"role": "assistant", "content": first.reply},
            {"role": "user", "content": reject},
        ],
        user_message=reject,
    )
    assert any(e.state == "rejected" for e in second.snapshot.knowledgeEntries)


def test_rejection_unknown_signal_intent_does_not_affirm_hostility():
    project = _FakeProject(name="The Dreamweaver")
    db = _FakeDb(project)
    lore = "The signal is hostile and is trying to lure ships into the trench."
    first = run_turn(db, project_id="proj-1", messages=[{"role": "user", "content": lore}], user_message=lore)
    reject = "Do not define the signal as hostile. Its intent is still unknown."
    second = run_turn(
        db,
        project_id="proj-1",
        messages=[
            {"role": "user", "content": lore},
            {"role": "assistant", "content": first.reply},
            {"role": "user", "content": reject},
        ],
        user_message=reject,
    )
    assert any(candidate.state == "rejected" for candidate in second.plan.wikiCandidates) or any(
        "intent is still unknown" in candidate.text.lower() and candidate.state == "confirmed"
        for candidate in second.plan.wikiCandidates
    )
    assert "intent is still unknown" in second.reply.lower() or "rejected" in second.reply.lower()
    assert "current version going forward: the signal is hostile" not in second.reply.lower()


def test_short_yes_uses_recent_context():
    db = _FakeDb(_FakeProject(name="The Dreamweaver"))
    # Seed an open question via character focus, then short yes
    lead = "Let's work on the main character."
    first = run_turn(db, project_id="proj-1", messages=[{"role": "user", "content": lead}], user_message=lead)
    yes = "Yes"
    second = run_turn(
        db,
        project_id="proj-1",
        messages=[
            {"role": "user", "content": lead},
            {"role": "assistant", "content": first.reply},
            {"role": "user", "content": yes},
        ],
        user_message=yes,
    )
    assert second.plan.primaryIntent == "invite_continuation" or second.plan.shouldAskQuestion
    assert second.snapshot.currentStage == "Characters"


def test_no_project_requests_project():
    db = _FakeDb()
    result = run_turn(db, project_id=None, messages=[{"role": "user", "content": "Hello"}], user_message="Hello")
    assert "project" in result.reply.lower()


def test_success_score_never_leaks_into_reply():
    db = _FakeDb()
    msg = "What should we do next?"
    result = run_turn(db, project_id="proj-1", messages=[{"role": "user", "content": msg}], user_message=msg)
    assert "conversation_quality" not in result.reply.lower()
    assert "overall" not in result.reply.lower()
    assert any(e.get("type") == "conversation_quality" for e in result.events)


def test_project_meridian_intro_names_title_cleanly():
    db = _FakeDb(_FakeProject(name="Sandbox"))
    intro = (
        "This project is called Project Meridian. It is a science-fiction web series about a research team "
        "investigating a crashed probe in Season 1."
    )
    result = run_turn(db, project_id="proj-1", messages=[{"role": "user", "content": intro}], user_message=intro)
    assert "Meridian" in result.reply
    assert "I hear is called" not in result.reply


def test_harbor_signal_intro_and_draft_plan_execute_action():
    db = _FakeDb(_FakeProject(name="CODIRECTOR-FOUNDATION-CERT-demo"))
    intro = (
        "This is Harbor Signal, a science-fiction web series about a coastal research crew "
        "investigating a silent beacon that appears only at low tide."
    )
    first = run_turn(db, project_id="proj-1", messages=[{"role": "user", "content": intro}], user_message=intro)
    assert "Harbor Signal" in first.reply
    assert "CODIRECTOR-FOUNDATION" not in first.reply
    plan_msg = "Create a draft plan for defining Nia, the beacon, and the Episode 1 opening sequence."
    second = run_turn(
        db,
        project_id="proj-1",
        messages=[
            {"role": "user", "content": intro},
            {"role": "assistant", "content": first.reply},
            {"role": "user", "content": plan_msg},
        ],
        user_message=plan_msg,
    )
    assert second.plan.primaryIntent == "execute_action"
    assert re.search(r"plan|draft|outline|approval|review", second.reply, re.I)


def test_attachment_reference_not_swallowed_by_character_stage():
    db = _FakeDb(_FakeProject(name="Project Meridian"))
    lead = "Let's work on the main character."
    first = run_turn(db, project_id="proj-1", messages=[{"role": "user", "content": lead}], user_message=lead)
    attach = (
        "Use the attached image as a reference prompt for Meridian. "
        "Tell me plainly what you can and cannot infer from it."
    )
    second = run_turn(
        db,
        project_id="proj-1",
        messages=[
            {"role": "user", "content": lead},
            {"role": "assistant", "content": first.reply},
            {"role": "user", "content": attach},
        ],
        user_message=attach,
    )
    assert "reference" in second.reply.lower() or "attached" in second.reply.lower()
    assert "visual analysis is unavailable" in second.reply.lower() or "will not invent" in second.reply.lower()
    assert "impossible to ignore" not in second.reply.lower()
    assert not re.search(r"\bI can see\b|\bthe image shows\b|\bdepicts\b", second.reply, re.I)


def test_draft_plan_action_not_swallowed_by_character_stage():
    db = _FakeDb(_FakeProject(name="Project Meridian"))
    lead = "Let's work on the main character."
    first = run_turn(db, project_id="proj-1", messages=[{"role": "user", "content": lead}], user_message=lead)
    plan_msg = "Create a draft plan for defining Mara, the probe signal, and the Episode 1 opening."
    second = run_turn(
        db,
        project_id="proj-1",
        messages=[
            {"role": "user", "content": lead},
            {"role": "assistant", "content": first.reply},
            {"role": "user", "content": plan_msg},
        ],
        user_message=plan_msg,
    )
    assert second.plan.primaryIntent == "execute_action"
    assert second.plan.shouldAskQuestion is False
    assert re.search(r"plan|draft|outline|approval|review", second.reply, re.I)
    assert "impossible to ignore" not in second.reply.lower()
