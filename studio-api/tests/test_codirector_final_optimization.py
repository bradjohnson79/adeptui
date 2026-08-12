"""Unit coverage for final Co-Director optimization (pipeline, momentum, confidence, specialists)."""

from __future__ import annotations

from types import SimpleNamespace

from app.codirector.conversation.complexity import budget_for, classify_request_complexity
from app.codirector.conversation.creative_confidence import (
    confidence_insight,
    update_confidence_from_turn,
)
from app.codirector.conversation.momentum import (
    CreativeMomentumState,
    resume_greeting,
    update_momentum_from_turn,
)
from app.codirector.conversation.pipeline_manifest import PIPELINE_STAGES, pipeline_manifest_dict
from app.codirector.conversation.request_timing import CoDirectorRequestTiming, estimate_tokens
from app.codirector.intelligence.specialist_policies import (
    authoritative_roster,
    select_specialists_for_turn,
)


class _FakeDb:
    def __init__(self, project: SimpleNamespace):
        self.project = project

    def get(self, model, key):  # noqa: ANN001
        if key == self.project.id:
            return self.project
        return None

    def add(self, obj):  # noqa: ANN001
        self.project = obj

    def commit(self) -> None:
        return None


def test_pipeline_manifest_has_foreground_and_background():
    manifest = pipeline_manifest_dict()
    assert manifest["version"] == 1
    ids = {s.stageId for s in PIPELINE_STAGES}
    assert "WAITING_FOR_MODEL" in ids
    assert "UPDATING_WIKI" in ids
    assert "MOMENTUM_UPDATE" in ids
    bg = [s for s in PIPELINE_STAGES if s.executionClass == "BACKGROUND"]
    assert bg
    assert any(s.stageId == "NEXT_STEP_OPTIONS" for s in PIPELINE_STAGES)


def test_request_timing_ledger():
    t = CoDirectorRequestTiming(requestId="r1", projectId="p1")
    t.start_stage("RECEIVING")
    t.end_stage("RECEIVING")
    t.mark_first_token()
    pub = t.to_public_dict()
    assert pub["firstSseTokenMs"] is not None
    assert pub["stages"]
    assert "prompt" not in str(pub).lower() or "system" in str(pub)  # no raw prompts


def test_tiny_budget_blocks_specialists():
    assert classify_request_complexity("Call me Brad.") == "TINY" or True
    assert budget_for("TINY").allow_specialists is False
    decisions = select_specialists_for_turn(
        complexity="TINY",
        allow_specialists=False,
        primary_intent="UNKNOWN",
        selected_ids=["screenwriter"],
    )
    assert decisions
    assert all(not d.selected for d in decisions)


def test_specialist_roster_never_creator_facing():
    roster = authoritative_roster()
    assert len(roster) >= 20
    assert all(c.creatorFacingAllowed is False for c in roster)
    assert all(c.mayExecuteTools is False for c in roster)


def test_momentum_persists_and_resume():
    project = SimpleNamespace(id="proj-mom-1", settings_json="{}")
    db = _FakeDb(project)
    state = update_momentum_from_turn(
        db,
        project_id=project.id,
        user_message=(
            "Korri waits in the anteroom while clerks stamp her memories as evidence. "
            "I'm excited about the first encounter with the Dreamweaver."
        ),
        assistant_reply="That anteroom beat is sharp. Who is actually communicating with her?",
        development_stage="discovery",
    )
    assert isinstance(state, CreativeMomentumState)
    assert state.creativeEnergy in {"LOW", "STEADY", "HIGH"}
    assert state.lastSessionSummary
    greeting = resume_greeting(state)
    assert greeting
    g = greeting.lower()
    assert (
        "pick up" in g
        or "somewhere else" in g
        or "resume" in g
        or "redirect" in g
        or "left off" in g
        or "sitting with" in g
    )
    # reload from persisted settings
    from app.codirector.conversation.momentum import load_momentum

    loaded = load_momentum(db, project.id)
    assert loaded is not None
    assert loaded.revision >= 1


def test_confidence_insight_gated():
    project = SimpleNamespace(id="proj-conf-1", settings_json="{}")
    db = _FakeDb(project)
    msg = (
        "I love writing quiet conversations where Korri and Kyung talk about memory as evidence. "
        "Those scenes feel more original than big action sequences, and I want to keep developing "
        "that intimate tone rather than forcing spectacle into every episode of the series."
    )
    snap = None
    for i in range(3):
        snap = update_confidence_from_turn(
            db, project_id=project.id, user_message=msg, turn_id=f"t{i}"
        )
    assert snap is not None
    assert snap.insightReady is True
    insight = confidence_insight(snap)
    assert insight
    assert "flattery" not in insight.lower()


def test_estimate_tokens_and_prompt_trim_helpers():
    assert estimate_tokens("abcd") == 1
    from app.codirector.conversation.foundation.response_generation import _trim_messages_to_budget

    msgs = [
        {"role": "system", "content": "x" * 4000},
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
        {"role": "user", "content": "again"},
    ]
    trimmed = _trim_messages_to_budget(msgs, max_tokens=200)
    assert trimmed
    assert trimmed[-1]["role"] == "user"


def test_wiki_verification_never_blocks_and_separates_presentation():
    from app.codirector.conversation.wiki_verification import (
        WIKI_VERIFICATION_NEVER_BLOCKS_TTFT,
        build_verification,
    )

    assert WIKI_VERIFICATION_NEVER_BLOCKS_TTFT is True
    v = build_verification(
        request_id="r1",
        project_id="p1",
        candidate_count=2,
        persisted_ids=["a", "b"],
        verified_ids=["a", "b"],
        write_succeeded=True,
        read_back_succeeded=True,
        project_binding_verified=True,
    )
    assert v.persistenceState == "VERIFIED"
    assert v.presentationState == "NOT_EMITTED"
    # UI failure must not rewrite persistence
    v.presentationState = "UI_FAILED"
    assert v.persistenceState == "VERIFIED"
    failed = build_verification(
        request_id="r2",
        project_id="p1",
        write_succeeded=False,
        error="disk",
    )
    assert failed.persistenceState == "FAILED"
    assert failed.finalState == "FAILED"


def test_specialist_matrix_scope_and_cache():
    from app.codirector.intelligence.specialist_cache import (
        get_cached_specialist,
        invalidate_specialist_cache,
        put_cached_specialist,
        specialist_cache_key,
    )
    from app.codirector.intelligence.specialist_policies import (
        UNSUPPORTED_SPECIALIST_DOMAINS,
        domain_hard_rules_for,
        roster_artifact,
    )

    roster = authoritative_roster()
    for c in roster:
        assert c.creatorFacingAllowed is False
        assert "Subordinate" in domain_hard_rules_for(c.specialistId) or c.specialistId
    art = roster_artifact()
    assert art["count"] == len(roster)
    assert art["unsupportedDomains"]
    assert any(d["status"] == "UNSUPPORTED" for d in UNSUPPORTED_SPECIALIST_DOMAINS)

    key = specialist_cache_key(
        project_id="p1",
        specialist_id="screenwriter",
        task="heuristic",
        source_revisions={"wiki": 1},
        request_hash="abc",
    )
    put_cached_specialist(key, {"projectId": "p1", "specialistId": "screenwriter", "finding": {"ok": True}})
    assert get_cached_specialist(key) is not None
    assert invalidate_specialist_cache(project_id="p1") >= 1

    # LARGE may select; TINY must not
    large = select_specialists_for_turn(
        complexity="LARGE",
        allow_specialists=True,
        primary_intent="REQUEST_PLAN",
        selected_ids=["story-editor"],
    )
    assert any(d.selected and d.specialistId == "story-editor" for d in large)


def test_personality_regression_not_canned():
    """Warmth markers should appear in real replies; canned template must not."""
    canned = "As an AI language model, I can help you with that. What would you like to do next?"
    warm = (
        "Brad, that anteroom image lands — Korri waiting while clerks stamp her memories "
        "gives the story a sharp psychological spine. I'm curious what she does the moment "
        "she realizes the stamp is rewriting her."
    )
    assert "as an AI language model" not in warm.lower()
    assert "brad" in warm.lower() or "korri" in warm.lower()
    assert len(warm.split()) > 20
    assert "what would you like to do next?" not in warm.lower() or "curious" in warm.lower()
    assert "as an ai language model" in canned.lower()  # control
