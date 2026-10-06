"""Co-Director Intelligence Refinement fences (owner mission 2026-09-19).

Deterministic fences for the ten mission probes and the memory/contamination
laws. These pin the REFINED intelligence behavior:

- Probe 1/2 (RC1/RC2): opinion turns are DISCUSS; timed-prompt authorship is
  LLM authorship — never asset placement.
- Probe 5B/RC6: "Okay, prepare it." is an instruction, not an approval hijack.
- Probe 8/RC7: a dismissed target never re-anchors the goal.
- RC3: execution status is durable machine state, excluded from the LLM's
  conversational memory (server-authoritative fold).
- RC4: the conversational memory window is no longer crushed to 2x400.
- RC5: contextual follow-ups resolve against real conversation context.
- RC8: attachment existence alone does not decide a Timeline action.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.codirector.routing.deterministic import (
    classify_deterministic,
    is_execution_confirmation,
    is_prompt_authoring,
    NAVIGATION_TARGETS,
)
from app.codirector.routing.unified_intent import (
    DispatchStrategy,
    UnifiedIntentKind,
    classify_intent,
)
from app.codirector.conversation.foundation.intent import analyze_intent
from app.codirector.conversation.foundation.visual_generation import is_prompt_only_request

_DEFAULT_WS = frozenset(NAVIGATION_TARGETS.values())

_CORPUS_PATH = Path(__file__).resolve().parent / "fixtures" / "codirector2_route_cases.json"


# ---------------------------------------------------------------------------
# Probe 1 (RC2) — opinion beats data query
# ---------------------------------------------------------------------------


def test_probe1_opinion_about_scene_is_discuss():
    result = classify_deterministic(
        "Before we do anything else, what do you think of the Schnick Coffee scene?"
    )
    assert result is not None
    assert result.actionClass.value == "DISCUSS"
    assert result.writeAllowed is False


def test_rc2_genuine_data_query_stays_read_inspect():
    result = classify_deterministic("What scenes do we have?")
    assert result is not None
    assert result.actionClass.value == "READ_INSPECT"


# ---------------------------------------------------------------------------
# Probe 2 (RC1 / Phase 5) — WRITE TIMED PROMPT is authorship
# ---------------------------------------------------------------------------


def test_probe2_timed_prompt_is_authoring_not_execution():
    result = classify_deterministic("Now create the timed prompt for this scene in Timeline.")
    assert result is not None
    assert result.actionClass.value == "DISCUSS"
    assert result.target == "prompt_authoring"
    assert result.writeAllowed is False


def test_probe2_unified_intent_is_conversation_llm_only():
    unified = classify_intent("Now create the timed prompt for this scene in Timeline.", {})
    assert unified.intent == UnifiedIntentKind.CONVERSATION
    assert unified.dispatch == DispatchStrategy.LLM_ONLY
    assert unified.capability == ""


def test_give_me_the_timed_prompt_is_authoring():
    assert is_prompt_authoring("Give me the timed prompt.") is True
    assert is_prompt_only_request("Give me the timed prompt.") is True


def test_add_asset_to_timeline_still_executes():
    result = classify_deterministic("Add this image to the Timeline.")
    assert result is not None
    assert result.actionClass.value == "EXECUTE_PRODUCTION"


def test_timed_prompt_placement_maps_to_prompt_segment_capability():
    unified = classify_intent(
        "Add the timed prompt to the timeline.", {},
        route_decision=classify_deterministic("Add the timed prompt to the timeline."),
    )
    assert unified.intent == UnifiedIntentKind.EXECUTION
    assert unified.capability == "timeline.add_prompt_segment"
    assert "timeline.propose_add_prompt_segment" in unified.curated_tool_ids


def test_scene_production_spec_is_not_authoring():
    """A full production spec (duration/batches/aspect/engine) is scene
    preparation, not prompt authorship — the frozen Scene 3 regression."""
    message = (
        "For Scene 3, I would like to create a Timeline prompt for the Character reference of "
        "Cade O'Connor, and using the Venture Corridor Scene environment reference sheet as the "
        "setting. The scene will be 30 seconds long with 2 batches. 21:9, 1.0 MegaPixels using MiniMax H3."
    )
    assert is_prompt_authoring(message) is False


def test_bare_aspect_ratio_never_mints_execution():
    assert classify_deterministic("9:16.") is None


# ---------------------------------------------------------------------------
# Probe 5B (RC6) — whole-utterance confirmation
# ---------------------------------------------------------------------------


def test_probe5b_okay_prepare_it_is_not_an_approval():
    result = classify_deterministic("Okay, prepare it.", pending_proposal_ids=["proposal-1"])
    assert result is None


def test_probe5b_okay_prepare_it_does_not_confirm_pending_execution():
    assert is_execution_confirmation("Okay, prepare it.") is False


def test_bare_okay_with_pending_still_confirms():
    assert is_execution_confirmation("Okay.") is True
    assert is_execution_confirmation("Yes, proceed.") is True


def test_generate_it_remains_an_affirmation():
    assert is_execution_confirmation("generate it") is True
    assert is_execution_confirmation("Generate it") is True


def test_new_instruction_riding_on_affirmation_is_instruction():
    assert is_execution_confirmation("Yes, generate the storyboard") is False
    assert is_execution_confirmation("Alright, set that up") is False


# ---------------------------------------------------------------------------
# Probe 8 (RC7) — dismissed targets do not re-anchor the goal
# ---------------------------------------------------------------------------


def test_probe8_goal_switches_off_dismissed_target():
    from app.codirector.conversation.orchestrate import _update_conversation_goal

    goal = _update_conversation_goal(
        "editorial",
        type("_I", (), {"user_goal_summary": "talk about Korri's dialogue"})(),
        "Forget Timeline for a second. I want to talk about Korri's dialogue.",
        route_decision_action=None,
    )
    assert goal != "editorial"
    assert goal == "character_development"


def test_rc7_single_timeline_word_no_longer_reanchors():
    from app.codirector.conversation.orchestrate import _update_conversation_goal

    goal = _update_conversation_goal(
        "editorial",
        type("_I", (), {"user_goal_summary": "discuss the café look"})(),
        "Before we do anything else, what do you think of the Timeline shot?",
        route_decision_action=None,
    )
    # A single shared token ("timeline") is not continuation evidence.
    assert goal != "editorial"


def test_probe8_classifier_leaves_switch_to_semantic():
    assert classify_deterministic(
        "Forget Timeline for a second. I want to talk about Korri's dialogue."
    ) is None


# ---------------------------------------------------------------------------
# RC3 — execution status never enters the LLM's conversational memory
# ---------------------------------------------------------------------------


def _memory_session():
    from app.db import Base  # noqa: WPS433

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_fold_events_for_llm_excludes_execution_and_tool_rows():
    from app.codirector.conversation_events import EventInput, append_events, fold_events, fold_events_for_llm

    db = _memory_session()
    append_events(
        db,
        "proj-mem",
        [
            EventInput(role="user", content="Add the café image to the timeline.", actor="user"),
            EventInput(role="assistant", content="I've added it as the café background.", message_type="answer", actor="assistant"),
            EventInput(
                role="system",
                content="Add asset — 1/1 complete. Done.",
                event_type="execution_status",
                message_type="completion",
                message_id="exec-1",
                actor="system",
            ),
            EventInput(role="tool", content="{}", event_type="tool_call", tool_id="timeline.propose_add_image_clip", actor="system"),
        ],
    )

    llm_view = fold_events_for_llm(db, "proj-mem")
    ui_view = fold_events(db, "proj-mem")

    llm_contents = [str(m.get("content") or "") for m in llm_view]
    ui_contents = [str(m.get("content") or "") for m in ui_view]

    # LLM view: conversational turns only.
    assert "Add the café image to the timeline." in llm_contents
    assert "I've added it as the café background." in llm_contents
    assert not any("Add asset —" in c for c in llm_contents)
    assert all(str(m.get("role")) in {"user", "assistant", "system"} for m in llm_view)

    # UI view keeps the durable machine rows.
    assert any("Add asset —" in c for c in ui_contents)


def test_rc3_execution_status_event_is_non_conversational_role():
    from app.codirector.conversation_events import fold_events_for_llm

    db = _memory_session()
    _ = fold_events_for_llm(db, "proj-empty")
    # The prior append wrote only LLM-visible rows; assert the empty-fold path
    # is safe so a fresh project falls back to the client transcript cleanly.
    assert fold_events_for_llm(db, "proj-empty") == []


def test_memory_window_is_no_longer_crushed_to_2x400():
    from app.codirector.conversation.foundation.response_generation import build_generation_messages
    from app.codirector.conversation.foundation.dialogue_policy import build_dialogue_plan
    from app.codirector.conversation.foundation.schemas import ConversationState
    intent = analyze_intent("Keep going with the scene.")
    plan = build_dialogue_plan(intent)
    history = [
        {"role": "user", "content": f"Turn {i}: " + ("detail " * 80)} for i in range(10)
    ]
    messages = build_generation_messages(
        user_message="Keep going with the scene.",
        intent=intent,
        plan=plan,
        state=ConversationState(),
        context_block="",
        project_title="Probe Project",
        recent_messages=history,
        max_context_tokens=2800,
    )
    # OLD behavior: only the last 2 x 400-char messages survived. The refined
    # window must keep substantially more conversational turns.
    conv = [m for m in messages if m["role"] in {"user", "assistant"}]
    assert len(conv) >= 6
    kept_lengths = [len(m["content"]) for m in conv]
    assert max(kept_lengths) > 400


# ---------------------------------------------------------------------------
# RC5 — contextual follow-ups resolve against real context
# ---------------------------------------------------------------------------


def test_probe4_followup_resolves_with_conversation_context():
    recent = [
        {"role": "user", "content": "Now create the timed prompt for this scene in Timeline."},
        {"role": "assistant", "content": "Here's the timed prompt for the scene: ..."},
    ]
    unified = classify_intent("Great. Set that up for me.", {"recent_messages": recent})
    assert unified.intent == UnifiedIntentKind.EXECUTION
    assert unified.dispatch == DispatchStrategy.CURATED_TOOLS


def test_probe7_tighter_followup_resolves():
    recent = [
        {"role": "user", "content": "Set up a medium shot on Korri."},
        {"role": "assistant", "content": "Medium shot established on Korri."},
    ]
    unified = classify_intent("Let's make that tighter.", {"recent_messages": recent})
    assert unified.intent == UnifiedIntentKind.EXECUTION
    assert unified.dispatch == DispatchStrategy.CURATED_TOOLS


# ---------------------------------------------------------------------------
# Final-closure mission (2026-09-19) — Blockers 1 + 2 fences
# ---------------------------------------------------------------------------


def test_recall_intent_exact_summary():
    from app.codirector.conversation.foundation.intent import analyze_intent

    intent = analyze_intent("Summarize the final scene exactly as we have it now. Don't add anything.")
    assert intent.primary_intent.value == "RECALL_SCENE"


def test_recall_intent_who_is_in_scene():
    from app.codirector.conversation.foundation.intent import analyze_intent

    intent = analyze_intent("Who is in this scene and what is each person doing?")
    assert intent.primary_intent.value == "RECALL_SCENE"


def test_recall_plan_requires_completeness_and_fidelity():
    from app.codirector.conversation.foundation.dialogue_policy import build_dialogue_plan
    from app.codirector.conversation.foundation.intent import analyze_intent

    plan = build_dialogue_plan(analyze_intent("Who is in this scene and what is each person doing?"))
    required = " ".join(plan.required_elements).lower()
    prohibited = " ".join(plan.prohibited_elements).lower()
    assert "established" in required
    assert "only facts" in required
    assert "invent" in prohibited
    assert plan.question_budget == 0


def test_trim_preserves_user_fact_turns_over_assistant_prose():
    """Final-closure Blocker 1: when the token budget forces trimming, oldest
    ASSISTANT prose is dropped before any creator turn — established facts
    (turn 1 'social ad', turn 2 'host') must survive."""
    from app.codirector.conversation.foundation.response_generation import _trim_messages_to_budget

    history = []
    for i in range(1, 10):
        history.append({"role": "user", "content": f"Fact {i}: the scene detail number {i} is established here."})
        history.append({"role": "assistant", "content": f"Reply {i}: " + ("elaborate creative prose " * 40)})
    history.append({"role": "user", "content": "Summarize the final scene exactly as we have it now."})
    trimmed = _trim_messages_to_budget(
        [{"role": "system", "content": "x" * 2000}, *history],
        max_tokens=1200,
    )
    user_contents = [m["content"] for m in trimmed if m["role"] == "user"]
    assert any("Fact 1" in c for c in user_contents), "turn-1 creator fact must survive trimming"
    assert any("Fact 2" in c for c in user_contents), "turn-2 creator fact must survive trimming"


# ---------------------------------------------------------------------------
# Final-closure mission (2026-09-19) — Blocker 3 fence (SceneId Resolution Law)
# ---------------------------------------------------------------------------


class _FakeDb:
    def get(self, model, key):  # noqa: ANN001
        return None

    def query(self, *a, **k):  # noqa: ANN002, ANN003
        raise ValueError("no db in fence")

    def add(self, obj):  # noqa: ANN001
        return obj

    def commit(self):
        return None


def test_timeline_add_asset_without_scene_declares_missing_scene_id():
    from app.codirector.routing.unified_intent import DispatchStrategy, UnifiedIntentKind, classify_intent
    from app.codirector.service import _build_execution_context, _enrich_execution_context

    message = "Add this café image to Timeline as a visual reference."
    unified = classify_intent(
        message,
        {},
        route_decision=classify_deterministic(message, active_workspace="timeline"),
    )
    assert unified.intent == UnifiedIntentKind.EXECUTION
    assert unified.capability == "timeline.add_asset"
    assert unified.dispatch == DispatchStrategy.DETERMINISTIC

    ctx = _build_execution_context(message, unified, [])
    ctx = _enrich_execution_context(
        _FakeDb(),
        "proj-1",
        ctx,
        unified,
        [],
        attachment_ids=["asset-cafe-1"],
        scene_id=None,
    )
    assert ctx.get("missing_required_fields") == ["sceneId"]
    # No fabricated scene id anywhere in the context.
    assert not str(ctx.get("scene_id") or "").strip()
    assert not str(ctx.get("sceneId") or "").strip()


def test_timeline_add_asset_with_bound_scene_binds_scene_id():
    from app.codirector.routing.unified_intent import classify_intent
    from app.codirector.service import _build_execution_context, _enrich_execution_context

    message = "Add this café image to Timeline as a visual reference."
    unified = classify_intent(
        message,
        {},
        route_decision=classify_deterministic(message, active_workspace="timeline"),
    )
    ctx = _build_execution_context(message, unified, [])
    ctx = _enrich_execution_context(
        _FakeDb(),
        "proj-1",
        ctx,
        unified,
        [],
        attachment_ids=["asset-cafe-1"],
        scene_id="scene-123",
    )
    assert ctx.get("scene_id") == "scene-123"
    assert ctx.get("sceneId") == "scene-123"
    assert "missing_required_fields" not in ctx
    assert (ctx.get("tool_params") or {}).get("sceneId") == "scene-123"


# ---------------------------------------------------------------------------
# Timed-prompt content handoff (2026-09-20) — fences
# ---------------------------------------------------------------------------


def test_author_place_single_command_routes_to_prompt_segment_curated():
    """Test 3 routing: 'Create the timed prompt … and put it into Timeline' is a
    prompt-segment placement with AUTHORING language → CURATED_TOOLS so the LLM
    emits the authored text as the structured `text` argument. It must NOT
    misroute to timeline.add_asset (empty ImageClip)."""
    message = "Create the timed prompt for this scene and put it into Timeline."
    det = classify_deterministic(message, active_workspace="timeline")
    unified = classify_intent(message, {}, route_decision=det)
    assert unified.intent == UnifiedIntentKind.EXECUTION
    assert unified.capability == "timeline.add_prompt_segment"
    assert unified.dispatch == DispatchStrategy.CURATED_TOOLS
    assert "timeline.propose_add_prompt_segment" in unified.curated_tool_ids


def test_place_existing_stays_deterministic_prompt_segment():
    """Test 2 routing: a pure placement command (no authoring verb) stays on the
    deterministic lane where the authored text resolves from the durable log."""
    message = "Can you add the Scene 1 timed prompt into Timeline"
    det = classify_deterministic(message, active_workspace="timeline")
    unified = classify_intent(message, {}, route_decision=det)
    assert unified.capability == "timeline.add_prompt_segment"
    assert unified.dispatch == DispatchStrategy.DETERMINISTIC


def test_place_existing_resolves_authored_text_byte_exact():
    """Test 2/4/5: the authored timed prompt resolves byte-exact from the
    durable log into tool_params.text, with scene-duration timing."""
    from app.db import Base  # noqa: F401
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.codirector.conversation_events import EventInput, append_events, fold_events_for_llm
    from app.codirector.service import _build_execution_context, _enrich_execution_context

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    authored = "[0s-8s] Medium shot of Korri behind the bar.\n[8s-15s] Smooth pan left to reveal Cade seated at the left table."
    append_events(
        db,
        "proj-tp",
        [
            EventInput(role="user", content="Create the Timed Prompt for this scene in Timeline.", actor="user"),
            EventInput(role="assistant", content=authored, message_type="answer", actor="assistant"),
        ],
    )
    assert any(authored in str(m.get("content")) for m in fold_events_for_llm(db, "proj-tp"))

    message = "Can you add the Scene 1 timed prompt into Timeline"
    unified = classify_intent(message, {}, route_decision=classify_deterministic(message, active_workspace="timeline"))
    ctx = _build_execution_context(message, unified, [])
    ctx = _enrich_execution_context(
        db,
        "proj-tp",
        ctx,
        unified,
        [],
        attachment_ids=[],
        scene_id="scene-tp-1",
    )
    tp = ctx.get("tool_params") or {}
    assert tp.get("text") == authored, "authored text must reach tool_params byte-exact"
    assert tp.get("sceneId") == "scene-tp-1"
    assert "missing_required_fields" not in ctx


def test_place_without_authored_text_declares_missing_prompt():
    """Test 5 fence: no authored timed prompt in the log → honest missing-field
    declaration; never an empty segment."""
    from app.db import Base  # noqa: F401
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.codirector.conversation_events import fold_events_for_llm
    from app.codirector.routing.unified_intent import classify_intent
    from app.codirector.service import _build_execution_context, _enrich_execution_context

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    assert fold_events_for_llm(db, "proj-empty-tp") == []

    message = "Can you add the Scene 1 timed prompt into Timeline"
    unified = classify_intent(message, {}, route_decision=classify_deterministic(message, active_workspace="timeline"))
    ctx = _build_execution_context(message, unified, [])
    ctx = _enrich_execution_context(
        db,
        "proj-empty-tp",
        ctx,
        unified,
        [],
        attachment_ids=[],
        scene_id="scene-x",
    )
    assert "text" in (ctx.get("missing_required_fields") or [])
    tp = ctx.get("tool_params") or {}
    assert not str(tp.get("text") or "").strip()


def test_prompt_segment_without_scene_declares_missing_scene_id():
    from app.codirector.routing.unified_intent import classify_intent
    from app.codirector.service import _build_execution_context, _enrich_execution_context

    message = "Can you add the Scene 1 timed prompt into Timeline"
    unified = classify_intent(message, {}, route_decision=classify_deterministic(message, active_workspace="timeline"))
    ctx = _build_execution_context(message, unified, [])
    ctx = _enrich_execution_context(
        _FakeDb(),
        "proj-tp",
        ctx,
        unified,
        [],
        attachment_ids=[],
        scene_id=None,
    )
    assert ctx.get("missing_required_fields") == ["sceneId"]
    assert not str(ctx.get("sceneId") or "").strip()


def test_intelligence_corpus_cases_present():
    corpus = json.loads(_CORPUS_PATH.read_text(encoding="utf-8"))
    ids = {case["id"] for case in corpus}
    assert "case-17-intel-p1-opinion-with-scene-noun" in ids
    assert "case-18-intel-p2-timed-prompt-authoring" in ids
    assert "case-20-intel-okay-prepare-it-not-approve" in ids
    assert "case-23-intel-timed-prompt-placement" in ids
