"""Top-level Conversation Core orchestration — Intent → DialoguePlan is authoritative."""

from __future__ import annotations

import re
import time
from typing import Any

from sqlalchemy.orm import Session

from .companion import (
    IDENTITY_POLICY_VERSION,
    assess_creative_block,
    assess_creative_support,
    assess_story_deviation,
    assemble_companion_context,
    assembler_mode_for,
    build_advisory_plan,
    extract_emerging_principles,
    load_companion_bundle,
    merge_principles,
    merge_return_points,
    merge_strengths,
    maybe_capture_return_point,
    profile_from_principles,
    propose_strength_from_principles,
    save_companion_bundle,
    transition_advisory_state,
    update_creative_lens,
)
from .companion.schemas import AdvisoryDecisionState, CompanionNeed
from .creative_state import update_creative_state
from .discovery import (
    IDENTITY_POLICY_VERSION as DISCOVERY_IDENTITY_POLICY_VERSION,
    assess_creative_temperature,
    assess_intrigue,
    build_comparative_note,
    capture_curiosity_threads,
    conversation_actions,
    discovery_composition_guidance,
    extract_documentation,
    generate_discovery_questions,
    intrigue_guidance,
    load_discovery_bundle,
    merge_curiosity,
    save_discovery_bundle,
    score_response_evidence,
    update_living_brief,
)
from .discovery.schemas import CoDirectorProcessingStage, ProjectPulse
from .foundation.context_assembler import assemble_listening_context
from .foundation.dialogue_policy import build_dialogue_plan
from .foundation.intent import analyze_intent
from .foundation.personality import personality_guidance_for_mode
from .foundation.response_generation import (
    build_generation_messages,
    deterministic_listening_fallback,
)
from .foundation.schemas import CoDirectorMode, ConversationState, IntentType
from .knowledge import apply_wiki_candidates
from .planner import plan_conversation
from .project_director import refresh_director
from .partnership import (
    HANDS_ON_POLICY_VERSION,
    assess_artifact_readiness,
    build_pitch_package,
    build_story_template,
    create_preview_deliverable,
    expand_preview_to_draft,
    format_preview_reply_enrichment,
    load_partnership_bundle,
    major_offer_requires_preview,
    may_create_full_draft,
    partnership_composition_guidance,
    partnership_conversation_actions,
    resolve_ownership,
    save_partnership_bundle,
    select_questions,
    sync_from_relationship,
    update_journey,
    update_vision_from_message,
)
from .partnership.marketing import update_marketing
from .partnership.schemas import CreativeDeliverableStatus, ProjectDestination
from .relationship import (
    apply_onboarding_message,
    load_relationship_profile,
    needs_onboarding,
    onboarding_prompt_block,
    role_guidance_text,
    save_relationship_profile,
)
from .response_composer import compose_reply
from .schemas import (
    ConversationCoreResult,
    ConversationPlan,
    ProjectDirectorState,
    ProjectIntelligenceSnapshot,
    WikiCandidate,
)
from .snapshot import build_tier1_snapshot, save_snapshot
from .success_score import evaluate_success


def _timed_step(timings: dict[str, float], key: str, started_at: float) -> None:
    timings[key] = round(time.perf_counter() - started_at, 6)


def _truncate_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    trimmed: list[dict[str, Any]] = []
    for message in messages[-12:]:
        if not isinstance(message, dict):
            continue
        content = str(message.get("content") or "").strip()
        if len(content) > 280:
            content = content[:277].rstrip() + "..."
        trimmed.append({"role": str(message.get("role") or "user"), "content": content})
    return trimmed


def _update_conversation_goal(
    current_goal: str | None,
    intent: Any,
    user_message: str,
    route_decision_action: str | None = None,
) -> str | None:
    text = (user_message or "").strip().lower()

    switch_markers = ["actually", "instead", "forget that", "never mind", "change of plan", "let's try"]
    if any(m in text for m in switch_markers):
        return _infer_goal_from_message(user_message)

    if route_decision_action:
        action = route_decision_action.lower()
        if action in ("navigate", "read_inspect", "execute_production", "modify_knowledge"):
            return _infer_goal_from_action(route_decision_action, user_message)

    completion_markers = ["done", "finished", "complete", "that's it", "that's all", "i'm happy with"]
    if any(m in text for m in completion_markers):
        return None

    if current_goal:
        goal_lower = current_goal.lower()
        goal_tokens = set(goal_lower.split())
        message_tokens = set(text.split())
        overlap = goal_tokens & message_tokens
        if len(overlap) >= 1 or _is_continuation(text):
            return current_goal

    return _infer_goal_from_message(user_message) or current_goal


def _infer_goal_from_message(message: str) -> str | None:
    text = message.lower()
    if "script" in text or "screenplay" in text or "write" in text:
        return "script_development"
    if "shot" in text or "breakdown" in text or "storyboard" in text:
        return "shot_planning"
    if "character" in text or "korri" in text:
        return "character_development"
    if "visual" in text or "image" in text or "look" in text or "concept" in text:
        return "visual_development"
    if "timeline" in text or "edit" in text:
        return "editorial"
    if "audio" in text or "voice" in text or "sound" in text:
        return "audio_development"
    if "story" in text or "premise" in text or "concept" in text:
        return "story_development"
    return None


def _infer_goal_from_action(action: str, message: str) -> str | None:
    action_lower = action.lower()
    if action_lower == "navigate":
        return "navigation"
    if action_lower == "read_inspect":
        return "research"
    if action_lower in ("execute_production", "propose_creative_change"):
        return "production_action"
    if action_lower == "modify_knowledge":
        return "knowledge_update"
    return _infer_goal_from_message(message)


def _is_continuation(text: str) -> bool:
    short = text.strip().lower()
    return short in {"yes", "y", "ok", "okay", "sure", "continue", "go on", "yeah", "right"}


def _snapshot_without_project(project_id: str | None) -> ProjectIntelligenceSnapshot:
    return ProjectIntelligenceSnapshot(
        projectId=project_id or "",
        title="Untitled Project",
        currentStage="Project Creation",
        currentSubstate="Naming",
        director=ProjectDirectorState(
            currentGoal="Open a project before shaping the story.",
            currentTask="Choose a project.",
            recommendedNextStep="Open an existing project or create a new one first.",
            creativeStage="Project Creation",
            creativeSubstate="Naming",
            revision=0,
        ),
    )


def _state_from_snapshot(snapshot: ProjectIntelligenceSnapshot) -> ConversationState:
    mode_raw = (snapshot.cognitiveMode or "").strip().upper()
    try:
        mode = CoDirectorMode(mode_raw) if mode_raw else CoDirectorMode.DISCOVERY
    except ValueError:
        mode = CoDirectorMode.DISCOVERY
    return ConversationState(
        active_goal=snapshot.activeGoal,
        current_mode=mode,
        user_intent_summary=snapshot.lastIntentPrimary or "",
        pending_questions=list(snapshot.deferredQuestions or []),
        recent_corrections=list(snapshot.recentCorrections or [])[:6],
        workflow_hold=bool(snapshot.workflowHold),
        preference_explain_before_production=bool(snapshot.preferenceExplainBeforeProduction),
    )


def _plan_from_dialogue(
    *,
    dialogue,
    intent,
    legacy: ConversationPlan,
    stage: str,
    substate: str | None,
) -> ConversationPlan:
    """Map authoritative DialoguePlan onto legacy ConversationPlan fields (subordinate)."""

    # Start from legacy planner output; DialoguePlan overrides creator-facing constraints.
    response_mode = legacy.responseMode or "conversation"
    primary: str = legacy.primaryIntent or "receive_information"

    if dialogue.mode == CoDirectorMode.LISTENING or intent.primary_intent == IntentType.EXPLAIN_PROJECT:
        if intent.primary_intent == IntentType.EXPLAIN_PROJECT:
            primary = "invite_continuation"
            response_mode = "intro"
        else:
            primary = "invite_continuation"
            response_mode = "invite_continuation"
    elif intent.primary_intent == IntentType.CORRECT_ASSISTANT:
        primary = "confirm_correction"
        response_mode = "confirm_correction"
    elif intent.primary_intent == IntentType.REQUEST_PLAN:
        primary = "recommend_next_step"
        response_mode = "recommend_next_step"
    elif intent.primary_intent in {IntentType.REQUEST_ACTION, IntentType.REQUEST_GENERATION}:
        primary = "execute_action"
        response_mode = "execute_action"

    # DialoguePlan wins over legacy inquiry while HOLD/LISTENING.
    # Otherwise preserve subordinate inquiry when the plan is not forcing silence.
    recommended = legacy.recommendedNextStep
    if dialogue.workflow_advance_policy == "HOLD" or dialogue.mode == CoDirectorMode.LISTENING:
        should_ask = False
        selected_q = None
        recommended = None
    elif dialogue.question_budget > 0:
        should_ask = bool(legacy.shouldAskQuestion)
        selected_q = legacy.selectedQuestion if should_ask else None
    else:
        # Neutral / discovery defaults: allow legacy single-question inquiry.
        should_ask = bool(legacy.shouldAskQuestion)
        selected_q = legacy.selectedQuestion if should_ask else None

    return ConversationPlan(
        primaryIntent=primary,  # type: ignore[arg-type]
        acknowledgedFacts=list(legacy.acknowledgedFacts),
        relevantContext=list(legacy.relevantContext),
        missingInformation=list(legacy.missingInformation) if should_ask else [],
        contradictionFlags=list(legacy.contradictionFlags),
        responseMode=response_mode,
        shouldAskQuestion=should_ask,
        selectedQuestion=selected_q,
        recommendedNextStep=recommended,
        shouldWriteWiki=dialogue.memory_policy in {"WRITE_CONFIRMED_FACTS", "PROPOSE"} or legacy.shouldWriteWiki,
        wikiCandidates=list(legacy.wikiCandidates),
        creativeStage=stage,
        creativeSubstate=substate,
        directorContext={
            **(legacy.directorContext or {}),
            "dialoguePlanMode": dialogue.mode.value,
            "workflowAdvancePolicy": dialogue.workflow_advance_policy,
            "questionBudget": dialogue.question_budget,
            "toolPolicy": dialogue.tool_policy,
        },
    )


def _apply_plan_to_snapshot(
    snapshot: ProjectIntelligenceSnapshot,
    plan: ConversationPlan,
    director: ProjectDirectorState,
    messages: list[dict[str, Any]],
    *,
    state: ConversationState,
    intent,
    dialogue,
) -> ProjectIntelligenceSnapshot:
    updated = snapshot.model_copy(deep=True)
    updated.currentStage = plan.creativeStage
    updated.currentSubstate = plan.creativeSubstate
    updated.director = director
    updated.contradictions = list(plan.contradictionFlags)
    updated.recentMessages = _truncate_messages(messages)
    updated.cognitiveMode = dialogue.mode.value
    updated.activeGoal = state.active_goal
    if dialogue.workflow_advance_policy in {"ADVANCE", "SUGGEST"} and dialogue.mode in {
        CoDirectorMode.EXECUTION,
        CoDirectorMode.PLANNING,
        CoDirectorMode.REVIEW,
    }:
        updated.workflowHold = False
    else:
        updated.workflowHold = state.workflow_hold or dialogue.workflow_advance_policy == "HOLD"
    updated.preferenceExplainBeforeProduction = state.preference_explain_before_production
    updated.deferredQuestions = list(state.pending_questions)
    updated.lastIntentPrimary = intent.primary_intent.value
    updated.lastEvidenceSpans = list(intent.evidence_spans[:8])

    if plan.shouldAskQuestion and plan.selectedQuestion and plan.selectedQuestion not in updated.openQuestions:
        updated.openQuestions.append(plan.selectedQuestion)
    elif dialogue.question_budget <= 0:
        # Defer questions silently rather than promoting them while listening.
        for q in list(updated.openQuestions):
            if q and q not in updated.deferredQuestions:
                updated.deferredQuestions.append(q)
        updated.openQuestions = []

    for candidate in plan.wikiCandidates:
        if candidate.state == "confirmed":
            if candidate.text not in updated.confirmedFacts:
                updated.confirmedFacts.insert(0, candidate.text)
            if candidate.text not in updated.recentCorrections and plan.primaryIntent == "confirm_correction":
                updated.recentCorrections.insert(0, candidate.text)
        elif candidate.state == "proposed" and candidate.text not in updated.unresolvedIdeas:
            updated.unresolvedIdeas.insert(0, candidate.text)

    updated.confirmedFacts = updated.confirmedFacts[:12]
    updated.recentCorrections = updated.recentCorrections[:6]
    updated.unresolvedIdeas = updated.unresolvedIdeas[:10]
    updated.openQuestions = updated.openQuestions[:8]
    updated.deferredQuestions = updated.deferredQuestions[:12]
    return updated


def run_conversation_core_turn(
    db: Session,
    *,
    project_id: str | None,
    messages: list[dict],
    user_message: str,
    mode: str = "chat",
    defer_enrichment: bool = False,
    curated_tool_ids: list[str] | None = None,
) -> ConversationCoreResult:
    """Execute one Conversation Core turn with foundation Intent→DialoguePlan authority.

    When ``defer_enrichment`` is True (streaming hot path), Wiki extraction, Living Brief,
    pitch/marketing/research, and discovery-form work are skipped so model dispatch is not
    blocked. Call ``run_deferred_enrichment`` after first tokens / completion.

    When ``curated_tool_ids`` is provided (Workstream B — CURATED_TOOLS dispatch),
    the IDs are forwarded to ``build_generation_messages`` so the system message
    carries a compact tool catalog and the model can emit ```` ```tool ```` blocks.
    """

    timings: dict[str, float] = {}
    events: list[dict[str, Any]] = []
    from .complexity import budget_for, classify_request_complexity

    complexity = classify_request_complexity(user_message, mode=mode)
    budget = budget_for(complexity)
    events.append(
        {
            "type": "request_complexity",
            "complexity": complexity,
            "budget": {
                "max_retrieval_sources": budget.max_retrieval_sources,
                "max_context_tokens": budget.max_context_tokens,
                "allow_specialists": budget.allow_specialists,
                "background_documentation": budget.background_documentation,
            },
        }
    )

    if not project_id:
        snapshot = _snapshot_without_project(project_id)
        plan = ConversationPlan(
            primaryIntent="request_clarification",
            responseMode="request_project",
            shouldAskQuestion=False,
            shouldWriteWiki=False,
            creativeStage="Project Creation",
            creativeSubstate="Naming",
            directorContext={"mode": mode},
        )
        reply = "Please open an existing project or create a new one first, and then I can help shape the story with you."
        score = evaluate_success(user_message, reply, plan, snapshot, snapshot)
        events.append({"type": "conversation_plan", "plan": plan.model_dump(mode="json")})
        events.append({"type": "conversation_quality", "score": score.model_dump(mode="json")})
        return ConversationCoreResult(
            plan=plan,
            snapshot=snapshot,
            reply=reply,
            score=score,
            timings=timings,
            events=events,
            usesLlmPrimary=False,
        )

    started = time.perf_counter()
    try:
        from .project_cache import warm_project_cache

        # Reuse warm cache on ordinary turns; do not force rewrite every request.
        warm_project_cache(db, project_id, force=False, persist=False)
    except Exception:  # noqa: BLE001
        pass
    snapshot_before = build_tier1_snapshot(db, project_id, messages)
    _timed_step(timings, "build_snapshot", started)

    started = time.perf_counter()
    processing_stages: list[str] = [CoDirectorProcessingStage.RECEIVED.value, CoDirectorProcessingStage.UNDERSTANDING.value]
    intent = analyze_intent(user_message)
    state = _state_from_snapshot(snapshot_before)
    # Phase 8 — ephemeral conversation goal tracking
    conversation_goal = _update_conversation_goal(
        snapshot_before.activeGoal,
        intent,
        user_message,
        route_decision_action=None,
    )
    companion_bundle = load_companion_bundle(db, project_id)
    relationship = load_relationship_profile(db, project_id)
    discovery_bundle = load_discovery_bundle(db, project_id)
    partnership_bundle = load_partnership_bundle(db, project_id)
    sync_from_relationship(partnership_bundle.collaboration, relationship)
    if needs_onboarding(relationship):
        relationship, _completed = apply_onboarding_message(relationship, user_message)
        if _completed:
            save_relationship_profile(db, project_id, relationship)
    support = assess_creative_support(user_message, companion_state=companion_bundle.companionState)
    temperature = assess_creative_temperature(
        user_message,
        prior_stage=discovery_bundle.creative_stage,
        explicit_critique=support.support_needed == CompanionNeed.CRITIQUE,
    )
    discovery_bundle.creative_stage = temperature.stage
    processing_stages.append(CoDirectorProcessingStage.INTRIGUE_ANALYSIS.value)
    intrigue = assess_intrigue(user_message)
    discovery_bundle.last_intrigue = intrigue
    companion_bundle.companionState.current_working_state = support.working_state
    companion_bundle.companionState.current_need = support.support_needed
    if support.support_needed == CompanionNeed.CRITIQUE:
        companion_bundle.companionState.critique_preference = "direct"
        companion_bundle.companionState.encouragement_preference = "defer"
    if intent.primary_intent == IntentType.EXPLAIN_PROJECT:
        state.workflow_hold = True
        state.preference_explain_before_production = True
        companion_bundle.companionState.explain_before_planning = True
        companion_bundle.companionState.do_not_interrupt_while_narrating = True
        state.active_goal = intent.user_goal_summary
        state.current_mode = CoDirectorMode.LISTENING
    elif intent.primary_intent.value in {"PAUSE_ACTION", "SET_PREFERENCE"}:
        state.workflow_hold = True
        state.active_goal = intent.user_goal_summary or state.active_goal
    elif intent.primary_intent in {
        IntentType.REQUEST_ACTION,
        IntentType.REQUEST_PLAN,
        IntentType.REQUEST_GENERATION,
        IntentType.REQUEST_FEEDBACK,
    } or support.support_needed == CompanionNeed.EXECUTE:
        # Creator authorized moving past pure listening hold for this turn.
        state.workflow_hold = False
        companion_bundle.companionState.do_not_interrupt_while_narrating = False
        state.active_goal = intent.user_goal_summary or support.likely_user_goal or state.active_goal

    deviation = assess_story_deviation(
        user_message,
        principles=companion_bundle.principles,
        prior_decision_state=companion_bundle.advisoryDecisionState.value,
    )
    companion_bundle.advisoryDecisionState = transition_advisory_state(
        companion_bundle.advisoryDecisionState,
        user_message,
        deviation=deviation if deviation.triggered else None,
    )
    if deviation.triggered and companion_bundle.advisoryDecisionState == AdvisoryDecisionState.IDLE:
        companion_bundle.advisoryDecisionState = AdvisoryDecisionState.ADVISED
    advisory = build_advisory_plan(
        support=support,
        deviation=deviation if deviation.triggered else None,
        decision_state=companion_bundle.advisoryDecisionState,
    )
    block = assess_creative_block(
        user_message,
        companion_state=companion_bundle.companionState,
        strength_ids=companion_bundle.companionState.known_strength_ids,
        return_point_ids=[r.id for r in companion_bundle.returnPoints[:4]],
    )

    dialogue = build_dialogue_plan(intent, state)
    # Attach companion/advisory onto DialoguePlan (single authority surface).
    dialogue.advisory = advisory.model_dump(mode="json")
    dialogue.companion_need = support.support_needed.value
    dialogue.creative_working_state = support.working_state.value
    if support.support_needed == CompanionNeed.CRITIQUE:
        dialogue.prohibited_elements = list(
            dict.fromkeys([*dialogue.prohibited_elements, "Empty praise", "Automatic agreement", "Unnecessary encouragement"])
        )
        dialogue.required_elements = list(
            dict.fromkeys([*dialogue.required_elements, "Direct strengths and weaknesses with evidence"])
        )
        dialogue.tone_profile = "candid-supportive"
        dialogue.mode = CoDirectorMode.REVIEW
    if advisory.should_advise and deviation.triggered:
        dialogue.required_elements = list(
            dict.fromkeys(
                [
                    *dialogue.required_elements,
                    "Acknowledge valid logic in the proposed change",
                    "Identify the actual problem layer",
                    "Compare gains and losses against demonstrated strengths",
                ]
            )
        )
        if advisory.provide_alternative:
            dialogue.required_elements.append("Offer a less destructive alternative when appropriate")
        dialogue.prohibited_elements = list(
            dict.fromkeys(
                [
                    *dialogue.prohibited_elements,
                    "Automatic agreement",
                    "Repeated argument after confirmation",
                    "Silent canon overwrite",
                ]
            )
        )
        if advisory.preserve_as_variant or companion_bundle.advisoryDecisionState == AdvisoryDecisionState.EXPLORATORY:
            dialogue.memory_policy = "PROPOSE"
            dialogue.workflow_advance_policy = "HOLD"
        if companion_bundle.advisoryDecisionState in {
            AdvisoryDecisionState.USER_CONFIRMED_KEEP_CURRENT,
            AdvisoryDecisionState.USER_CONFIRMED_CHANGE,
            AdvisoryDecisionState.COLLABORATING_ON_DIRECTION,
        }:
            dialogue.required_elements.append("Support the confirmed direction fully without re-arguing")
            dialogue.prohibited_elements.append("Re-litigate prior advisory disagreement")
    if block:
        dialogue.required_elements = list(
            dict.fromkeys(
                [
                    *dialogue.required_elements,
                    f"Offer this focused next step: {block.recommended_first_step}",
                ]
            )
        )
        dialogue.prohibited_elements = list(
            dict.fromkeys([*dialogue.prohibited_elements, "Large random idea dump", "Generic motivational slogans"])
        )
        dialogue.question_budget = 1 if block.focused_question_required else 0

    # Specialist consult only when budget allows + DialoguePlan need — still subordinate.
    # TINY/SMALL narration must not auto-invoke production/pitch/research specialists.
    from ..intelligence.specialist_policies import select_specialists_for_turn

    wants_specialists = False
    candidate_ids: list[str] = []
    if budget.allow_specialists and (
        intent.primary_intent
        in {IntentType.REQUEST_FEEDBACK, IntentType.REQUEST_PLAN, IntentType.REQUEST_ACTION}
        or support.support_needed == CompanionNeed.EXECUTE
    ):
        if dialogue.workflow_advance_policy != "HOLD" or support.support_needed == CompanionNeed.EXECUTE:
            dialogue.specialist_policy = "OPTIONAL_SUBORDINATE"
            # Soft candidates — selection policy still gates by complexity/budget.
            if intent.primary_intent == IntentType.REQUEST_ACTION:
                candidate_ids = ["producer", "pipeline-manager"]
            elif intent.primary_intent == IntentType.REQUEST_PLAN:
                candidate_ids = ["story-editor", "screenwriter"]
            else:
                candidate_ids = ["story-analyst", "continuity-analyst"]
    elif not budget.allow_specialists:
        dialogue.specialist_policy = "NONE"

    specialist_decisions = select_specialists_for_turn(
        complexity=complexity,
        allow_specialists=budget.allow_specialists,
        primary_intent=intent.primary_intent.value,
        selected_ids=candidate_ids,
    )
    wants_specialists = any(d.selected for d in specialist_decisions)
    selected_decisions = [d for d in specialist_decisions if d.selected]
    events.append(
        {
            "type": "specialist_selection",
            "complexity": complexity,
            "allowSpecialists": budget.allow_specialists,
            "selected": [d.specialistId for d in selected_decisions],
            "skippedCount": sum(1 for d in specialist_decisions if not d.selected),
            "decisions": [d.model_dump(mode="json") for d in selected_decisions[:8]],
        }
    )

    state.current_mode = dialogue.mode
    if not state.active_goal:
        state.active_goal = support.likely_user_goal or intent.user_goal_summary
    events.append({"type": "intent_analysis", "intent": intent.model_dump(mode="json")})
    events.append({"type": "creative_support", "support": support.model_dump(mode="json")})
    if deviation.triggered:
        events.append({"type": "story_deviation", "deviation": deviation.model_dump(mode="json")})
    if block:
        events.append({"type": "creative_block", "block": block.model_dump(mode="json")})
    events.append({"type": "dialogue_plan", "plan": dialogue.model_dump(mode="json")})
    events.append(
        {
            "type": "advisory_state",
            "state": companion_bundle.advisoryDecisionState.value,
            "advisory": advisory.model_dump(mode="json"),
            "identityPolicyVersion": IDENTITY_POLICY_VERSION,
        }
    )
    _timed_step(timings, "intent_dialogue", started)

    started = time.perf_counter()
    stage, substate, changed = update_creative_state(
        snapshot_before.currentStage,
        snapshot_before.currentSubstate,
        user_message,
    )
    # Listening HOLD: do not advance creative stage into intake questionnaires.
    if dialogue.workflow_advance_policy == "HOLD" and dialogue.mode == CoDirectorMode.LISTENING:
        stage = snapshot_before.currentStage or stage
        substate = snapshot_before.currentSubstate or substate
        changed = False
    events.append(
        {
            "type": "creative_state",
            "stage": stage,
            "substate": substate,
            "changed": changed,
        }
    )
    _timed_step(timings, "creative_state", started)

    started = time.perf_counter()
    # Legacy planner/director are subordinate signals only.
    seed_plan = ConversationPlan(creativeStage=stage, creativeSubstate=substate, responseMode=mode)
    director_seed = refresh_director(snapshot_before, seed_plan, user_message)
    legacy_plan = plan_conversation(user_message, snapshot_before, stage, substate, director_seed)
    plan = _plan_from_dialogue(
        dialogue=dialogue,
        intent=intent,
        legacy=legacy_plan,
        stage=stage,
        substate=substate,
    )
    # Phase 8 — ephemeral conversation goal (session-scoped, not persisted to project state)
    plan.directorContext["conversationGoal"] = conversation_goal
    director = refresh_director(snapshot_before, plan, user_message)
    if dialogue.workflow_advance_policy == "HOLD":
        # Quarantine title/premise backlog from creator-facing plan fields.
        director = director.model_copy(
            update={
                "recommendedNextStep": (
                    "Continue listening while the creator explains the project."
                    if dialogue.mode == CoDirectorMode.LISTENING
                    else director.recommendedNextStep
                ),
                "blockedItems": [
                    b
                    for b in director.blockedItems
                    if "title" not in b.lower() and "premise" not in b.lower()
                ],
            }
        )
        plan.recommendedNextStep = None
    events.append({"type": "project_director", "director": director.model_dump(mode="json")})
    events.append({"type": "conversation_plan", "plan": plan.model_dump(mode="json")})
    _timed_step(timings, "planning", started)

    started = time.perf_counter()
    # Phase CK — auto-Wiki extraction disabled. Generic conversation does not
    # create canonical wiki records. The Knowledge Card flow replaces this path.
    wiki_candidates = []
    plan.shouldWriteWiki = False
    is_exploratory_turn = (
        advisory.preserve_as_variant
        or companion_bundle.advisoryDecisionState == AdvisoryDecisionState.EXPLORATORY
        or support.working_state.value == "EXPLORING"
    )
    block_canon_write = is_exploratory_turn or (
        deviation.triggered
        and not advisory.canon_write_allowed
        and companion_bundle.advisoryDecisionState
        not in {
            AdvisoryDecisionState.USER_CONFIRMED_CHANGE,
            AdvisoryDecisionState.CANON_UPDATED,
        }
    )
    if block_canon_write:
        wiki_candidates = []
        plan.shouldWriteWiki = False
    if is_exploratory_turn:
        companion_bundle.exploratoryVariants = [
            {"text": user_message[:400], "status": "EXPLORATORY"},
            *list(companion_bundle.exploratoryVariants or [])[:19],
        ]
    if companion_bundle.advisoryDecisionState == AdvisoryDecisionState.USER_CONFIRMED_KEEP_CURRENT:
        companion_bundle.lastAdvisoryChange = "keep_current_adjust_surroundings"
    if companion_bundle.advisoryDecisionState == AdvisoryDecisionState.USER_CONFIRMED_CHANGE:
        companion_bundle.lastAdvisoryChange = user_message[:280]

    snapshot_after = apply_wiki_candidates(snapshot_before, wiki_candidates, user_message)
    snapshot_after = _apply_plan_to_snapshot(
        snapshot_after,
        plan,
        director,
        messages,
        state=state,
        intent=intent,
        dialogue=dialogue,
    )
    snapshot_after.companionNeed = support.support_needed.value
    snapshot_after.advisoryDecisionState = companion_bundle.advisoryDecisionState.value
    snapshot_after.companionSupportStrategy = list(support.suggested_response_strategy[:6])

    # Memory updates with provenance (never promote inference to confirmed without support).
    source_id = f"turn:{len(messages)}:{hash(user_message) & 0xFFFF:x}"
    continue_explaining = bool(
        re.search(r"\b(keep (?:listening|developing|explaining)|continue explaining)\b", user_message or "", re.I)
    )

    # Response-first path: defer Wiki / Living Brief / pitch / marketing / research.
    if defer_enrichment:
        from .discovery.schemas import DocumentationReason, DocumentationResult

        documentation = DocumentationResult(
            substantive=False,
            candidate_count=0,
            reason=DocumentationReason.NOT_SUBSTANTIVE,
            summary_lines=["Documentation deferred until after response streaming."],
        )
        discovery_bundle.last_documentation = documentation
        readiness_list = []
        active_preview = None
        active_draft = None
        active_pitch = None
        partnership_questions = []
        deferred_qs: list = []
        discovery_questions = []
        research_hint = None
        personal_dest = False
        what_changed = ["Background project knowledge update queued."]
        discovery_bundle.last_what_changed = what_changed
        pulse = ProjectPulse(
            current_phase=partnership_bundle.journey.current_stage.replace("_", " ").title(),
            creative_momentum=temperature.momentum.title(),
            confirmed_facts=sum(1 for c in discovery_bundle.wiki_candidates if c.status == "CONFIRMED"),
            emerging_ideas=sum(1 for c in discovery_bundle.wiki_candidates if c.status in {"EMERGING", "INFERRED"}),
            open_decisions=len(discovery_bundle.discovery_questions) + len(partnership_bundle.journey.upcoming_decisions),
            canon_conflicts=len(partnership_bundle.vision.conflicts or []),
            next_useful_step="Continue the conversation — project knowledge updates in the background.",
        )
        _timed_step(timings, "knowledge", started)
    else:
      processing_stages.append(CoDirectorProcessingStage.FACT_EXTRACTION.value)
      documentation = extract_documentation(
          user_message,
          project_id=project_id,
          source_id=source_id,
          relationship=relationship,
      )
      discovery_bundle.last_documentation = documentation
      if documentation.candidate_count > 0:
          processing_stages.append(CoDirectorProcessingStage.WIKI_UPDATE.value)
          discovery_bundle.wiki_candidates = [
              *documentation.candidates,
              *list(discovery_bundle.wiki_candidates or [])[:80],
          ]
          # Map into Conversation Core wiki candidates for snapshot knowledge entries.
          mapped: list[WikiCandidate] = []
          for c in documentation.candidates:
              state_map = {
                  "CONFIRMED": "confirmed",
                  "EMERGING": "proposed",
                  "INFERRED": "proposed",
                  "DISPUTED": "unresolved",
                  "SUPERSEDED": "superseded",
              }
              section = {
                  "CHARACTER": "characters",
                  "LOCATION": "worldAndSetting",
                  "EVENT": "storyAndEpisodes",
                  "TIMELINE": "storyAndEpisodes",
                  "WORLD_RULE": "worldAndSetting",
                  "THEME": "creativeFoundation",
                  "STORY_PRINCIPLE": "creativeFoundation",
                  "ENTITY": "worldAndSetting",
                  "PROJECT": "knownDetails",
                  "ORGANIZATION": "worldAndSetting",
              }.get(c.category.value, "creativeFoundation")
              mapped.append(
                  WikiCandidate(
                      id=c.id,
                      text=f"{c.title}: {c.content}"[:400],
                      state=state_map.get(c.status, "proposed"),  # type: ignore[arg-type]
                      section=section,
                      provenance=c.status,
                      sourceTurn=source_id,
                  )
              )
          if mapped and not block_canon_write:
              snapshot_after = apply_wiki_candidates(snapshot_after, mapped, user_message)
              plan.wikiCandidates = list(plan.wikiCandidates) + mapped
              plan.shouldWriteWiki = True
      discovery_bundle.brief = update_living_brief(
          discovery_bundle.brief,
          project_id=project_id,
          user_message=user_message,
          candidates=documentation.candidates,
      )

      # --- Hands-on partnership: vision, readiness, preview/draft, pitch, marketing ---
      user_auth_draft = bool(
        re.search(
            r"\b("
            r"create (?:the )?draft|draft it|"
            r"expand(?:\s+\w+){0,3}\s+preview|"
            r"prepare (?:a )?(?:short )?pitch|"
            r"build (?:the )?(?:story )?template|"
            r"write (?:the )?(?:treatment|pitch)|"
            r"authorize draft|"
            r"story template for me to review"
            r")\b",
            user_message or "",
            re.I,
        )
      )
      processing_stages.append(CoDirectorProcessingStage.VISION_ANALYSIS.value)
      update_vision_from_message(
        partnership_bundle, user_message, creative_stage=temperature.stage.value
      )
      update_journey(
        partnership_bundle,
        creative_stage=temperature.stage.value,
        substantive=documentation.substantive,
        user_message=user_message,
      )
      processing_stages.append(CoDirectorProcessingStage.ARTIFACT_READINESS.value)
      readiness_list = assess_artifact_readiness(
        partnership_bundle,
        user_message=user_message,
        brief_fields=discovery_bundle.brief.fields,
        creative_stage=temperature.stage.value,
        user_authorized_draft=user_auth_draft,
      )
      active_preview = None
      active_draft = None
      active_pitch = None
      for assessment in readiness_list:
        if major_offer_requires_preview(assessment) and assessment.preview_hook:
            active_preview = create_preview_deliverable(
                partnership_bundle, assessment, project_id=project_id
            )
            break
      # Authorize-only turns: reuse prior PREVIEW when the latest message is short.
      if user_auth_draft and not active_preview:
        active_preview = next(
            (
                d
                for d in reversed(partnership_bundle.deliverables)
                if d.status == CreativeDeliverableStatus.PREVIEW
            ),
            None,
        )
      if user_auth_draft and active_preview:
        ownership = resolve_ownership(partnership_bundle.collaboration, active_preview.type)
        if may_create_full_draft(ownership, user_authorized=True):
            if active_preview.type == "story_template":
                processing_stages.append(CoDirectorProcessingStage.DRAFTING.value)
                source_text = (
                    user_message
                    if len((user_message or "").split()) >= 20
                    else (active_preview.preview_content or user_message)
                )
                draft = build_story_template(
                    project_id=project_id,
                    user_message=source_text,
                    brief_fields=discovery_bundle.brief.fields,
                    ownership_mode=ownership,
                    why_now=active_preview.why_now,
                )
                expanded = expand_preview_to_draft(
                    partnership_bundle,
                    active_preview.id,
                    draft.content,
                    field_marks=draft.field_marks,
                    assumptions=draft.assumptions,
                )
                active_draft = expanded or draft
                if expanded is None:
                    partnership_bundle.deliverables.append(draft)
                    active_draft = draft
            elif active_preview.type == "pitch_summary":
                processing_stages.append(CoDirectorProcessingStage.PITCH_BUILDING.value)
                pitch_assessment = next(
                    (a for a in readiness_list if a.artifact_type == "pitch_summary"), None
                )
                active_pitch = build_pitch_package(
                    partnership_bundle,
                    project_id=project_id,
                    user_message=user_message,
                    assessment=pitch_assessment,
                )
                expand_preview_to_draft(
                    partnership_bundle,
                    active_preview.id,
                    active_pitch.short_pitch,
                    assumptions=active_pitch.assumptions,
                )
                active_draft = next(
                    (
                        d
                        for d in partnership_bundle.deliverables
                        if d.id == active_preview.id
                        and d.status != CreativeDeliverableStatus.PREVIEW
                    ),
                    None,
                )
      # Pitch without prior preview when explicitly authorized and ready
      if user_auth_draft and not active_pitch:
        pitch_ready = next(
            (a for a in readiness_list if a.artifact_type == "pitch_summary" and a.readiness.value == "READY"),
            None,
        )
        if pitch_ready and may_create_full_draft(pitch_ready.ownership_mode, user_authorized=True):
            if CoDirectorProcessingStage.PITCH_BUILDING.value not in processing_stages:
                processing_stages.append(CoDirectorProcessingStage.PITCH_BUILDING.value)
            active_pitch = build_pitch_package(
                partnership_bundle,
                project_id=project_id,
                user_message=user_message,
                assessment=pitch_ready,
            )
      personal_dest = partnership_bundle.vision.primary_destination == ProjectDestination.PERSONAL
      if not personal_dest and (
        partnership_bundle.vision.primary_destination.value != "UNDECIDED"
        or re.search(r"\b(marketing|launch|youtube|festival)\b", user_message or "", re.I)
      ):
        processing_stages.append(CoDirectorProcessingStage.MARKETING_ANALYSIS.value)
        update_marketing(
            partnership_bundle,
            user_message=user_message,
            intrigue_hooks=list(intrigue.distinctive_elements[:3]),
        )
      elif personal_dest:
        update_marketing(partnership_bundle, user_message=user_message, intrigue_hooks=[])

      partnership_questions, deferred_qs = select_questions(
        partnership_bundle,
        relationship=relationship,
        creative_stage=temperature.stage.value,
        continue_explaining=continue_explaining,
        substantive=documentation.substantive,
        user_message=user_message,
        question_budget=temperature.question_budget,
      )
      partnership_bundle.deferred_questions = deferred_qs

      processing_stages.append(CoDirectorProcessingStage.DISCOVERY_FORM.value)
      discovery_questions = generate_discovery_questions(
        project_id=project_id,
        user_message=user_message,
        brief=discovery_bundle.brief,
        candidates=documentation.candidates,
        temperature=temperature,
      )
      if discovery_questions:
        discovery_bundle.discovery_questions = [
            *discovery_questions,
            *[q for q in discovery_bundle.discovery_questions if q.id not in {d.id for d in discovery_questions}],
        ][:30]
      discovery_bundle.curiosity_threads = merge_curiosity(
        discovery_bundle.curiosity_threads,
        capture_curiosity_threads(
            project_id=project_id,
            user_message=user_message,
            intrigue=intrigue,
            source_id=source_id,
        ),
      )

      research_hint = None
      user_auth_research = bool(
        re.search(
            r"\b(research|compare|similar works|look up|authorize research)\b",
            user_message or "",
            re.I,
        )
      )
      if relationship.research_permission != "OFFLINE" and (
        relationship.research_permission in {"WHEN_USEFUL", "ACTIVE"} or user_auth_research
      ):
        note, comparison, research_status = build_comparative_note(
            project_id=project_id,
            project_snippet=user_message[:200],
            user_authorized=bool(user_auth_research) or relationship.research_permission == "ACTIVE",
            permission=relationship.research_permission,
        )
        if note:
            processing_stages.append(CoDirectorProcessingStage.RESEARCHING.value)
            discovery_bundle.research_notes = [note, *list(discovery_bundle.research_notes or [])][:20]
            research_hint = (
                f"Comparable class notes available ({comparison.reference_title if comparison else 'research'}). "
                "Emphasize differences and project distinctiveness."
            )
        elif research_status and relationship.research_permission == "ASK_FIRST" and not user_auth_research:
            research_hint = "Offer research as an optional next step; ask before searching."

      what_changed = list(documentation.summary_lines) if documentation.reason.value == "OK" else []
      if documentation.substantive and documentation.candidate_count == 0:
        what_changed = [f"Documentation: {documentation.reason.value}"]
      if active_preview:
        what_changed.append(f"1 {active_preview.type.replace('_', ' ')} preview offered")
      if active_draft:
        what_changed.append(f"1 {active_draft.type.replace('_', ' ')} draft ready for review")
      if active_pitch:
        what_changed.append("1 pitch opportunity drafted")
      if partnership_bundle.vision.primary_destination.value != "UNDECIDED":
        what_changed.append(f"1 project destination noted: {partnership_bundle.vision.primary_destination.value}")
      discovery_bundle.last_what_changed = what_changed

      pulse = ProjectPulse(
        current_phase=partnership_bundle.journey.current_stage.replace("_", " ").title(),
        creative_momentum=temperature.momentum.title(),
        confirmed_facts=sum(1 for c in discovery_bundle.wiki_candidates if c.status == "CONFIRMED"),
        emerging_ideas=sum(1 for c in discovery_bundle.wiki_candidates if c.status in {"EMERGING", "INFERRED"}),
        open_decisions=len(discovery_bundle.discovery_questions) + len(partnership_bundle.journey.upcoming_decisions),
        canon_conflicts=len(partnership_bundle.vision.conflicts or []),
        next_useful_step=(
            partnership_bundle.journey.next_useful_artifact
            or (discovery_questions[0].question if discovery_questions else None)
            or "Continue listening while the creator develops the idea."
        ),
      )

      incoming_principles = extract_emerging_principles(user_message, project_id, source_id)
      companion_bundle.principles = merge_principles(companion_bundle.principles, incoming_principles)
      companion_bundle.strengthProfile = profile_from_principles(project_id, companion_bundle.principles)
      companion_bundle.creatorStrengths = merge_strengths(
        companion_bundle.creatorStrengths,
        propose_strength_from_principles(project_id, companion_bundle.principles, source_id=source_id),
      )
      companion_bundle.companionState.known_strength_ids = [s.id for s in companion_bundle.creatorStrengths[:8]]
      companion_bundle.returnPoints = merge_return_points(
        companion_bundle.returnPoints,
        maybe_capture_return_point(user_message, project_id, source_id),
      )
      companion_bundle.creativeLens = update_creative_lens(
        companion_bundle.creativeLens, user_message, project_id, source_id
      )
      if companion_bundle.advisoryDecisionState == AdvisoryDecisionState.USER_CONFIRMED_KEEP_CURRENT:
        companion_bundle.advisoryDecisionState = AdvisoryDecisionState.COLLABORATING_ON_DIRECTION
      _timed_step(timings, "knowledge", started)

    asm_mode = assembler_mode_for(support, advisory, dialogue.mode.value)
    if temperature.stage.value == "EMERGENCE":
        asm_mode = "CREATIVE_SUPPORT"
    if dialogue.mode == CoDirectorMode.LISTENING and support.support_needed == CompanionNeed.LISTEN:
        context_block = assemble_listening_context(
            snapshot=snapshot_after,
            state=state,
            intent=intent,
            plan=dialogue,
            recent_messages=list(messages),
        )
    else:
        context_block = assemble_companion_context(
            mode=asm_mode,
            project_title=snapshot_after.title or "Untitled Project",
            active_goal=state.active_goal,
            support=support,
            advisory=advisory,
            deviation=deviation if deviation.triggered else None,
            block=block,
            bundle=companion_bundle,
            recent_messages=list(messages),
        )
    context_block = (
        personality_guidance_for_mode(asm_mode, support.support_needed.value)
        + "\n\n"
        + role_guidance_text(relationship)
        + "\n\n"
        + onboarding_prompt_block(relationship)
        + "\n\n"
        + intrigue_guidance(intrigue)
        + "\n\n"
        + discovery_composition_guidance(
            temperature=temperature,
            intrigue=intrigue,
            documentation=documentation,
            questions=discovery_questions,
            relationship=relationship,
            research_hint=research_hint,
        )
        + "\n\n"
        + partnership_composition_guidance(
            readiness=readiness_list,
            preview=active_preview,
            vision=partnership_bundle.vision,
            pitch=active_pitch or (partnership_bundle.pitches[-1] if partnership_bundle.pitches else None),
            marketing=partnership_bundle.marketing,
            questions=partnership_questions,
            personal_destination=personal_dest,
        )
        + "\n\n"
        + context_block
    )

    # Compact momentum / confidence / cache / creative operating — never full Wiki dumps on the hot path.
    try:
        from .momentum import load_momentum, momentum_prompt_block
        from .creative_confidence import load_confidence, confidence_prompt_block
        from .project_cache import cache_prompt_block, load_project_cache

        context_block = (
            momentum_prompt_block(load_momentum(db, project_id))
            + "\n\n"
            + confidence_prompt_block(load_confidence(db, project_id))
            + "\n\n"
            + cache_prompt_block(load_project_cache(db, project_id))
            + "\n\n"
            + context_block
        )
    except Exception:  # noqa: BLE001
        pass

    # Creative operating decision — compact heuristics only (no specialist fan-out on TTFT path).
    try:
        from ..creative_operating.composition import COACHING_DOCTRINE, creative_operating_prompt_block
        from ..creative_operating.decision_loop import run_creative_decision_loop

        primary_type = None
        try:
            from app.db import Project

            proj = db.get(Project, project_id)
            primary_type = getattr(proj, "primary_project_type", None) if proj else None
        except Exception:  # noqa: BLE001
            primary_type = None
        coi_decision, coi_bundle = run_creative_decision_loop(
            db,
            project_id=project_id,
            user_message=user_message,
            discovery_stage=temperature.stage.value if temperature else None,
            primary_project_type=primary_type,
            snapshot_format=getattr(snapshot_after, "format", None),
            persist=True,
        )
        life_stage = None
        specialists = None
        try:
            from ..production_lifecycle.format_maps import specialists_for_stage

            raw_life = getattr(snapshot_after, "productionLifecycle", None) or {}
            life_stage = raw_life.get("currentStage")
            if life_stage:
                specialists = specialists_for_stage(str(life_stage))
        except Exception:  # noqa: BLE001
            life_stage = None
            specialists = None
        coi_block = creative_operating_prompt_block(
            coi_decision,
            coi_bundle,
            lifecycle_stage=str(life_stage) if life_stage else None,
            specialists_for_stage=specialists,
        )
        if coi_block:
            context_block = COACHING_DOCTRINE + "\n\n" + coi_block + "\n\n" + context_block
    except Exception:  # noqa: BLE001
        pass

    processing_stages.append(CoDirectorProcessingStage.RESPONSE_GENERATION.value)
    generation_messages = build_generation_messages(
        user_message=user_message,
        intent=intent,
        plan=dialogue,
        state=state,
        context_block=context_block,
        project_title=snapshot_after.title or "Untitled Project",
        recent_messages=list(messages),
        max_context_tokens=budget.max_context_tokens,
        curated_tool_ids=curated_tool_ids,
    )
    fallback = deterministic_listening_fallback(
        user_message=user_message,
        intent=intent,
        plan=dialogue,
        project_title=snapshot_after.title or "the project",
    )
    # Warm relationship-ack fallback when creator just submitted working preferences.
    if re.search(
        r"\b(i(?:'|’)ve filled in how i(?:'|’)d like us to work|call me .+|i(?:'|’)d like to call you|"
        r"skip the setup form for now)\b",
        user_message or "",
        re.I,
    ):
        you = relationship.user_preferred_name or "friend"
        me = relationship.assistant_preferred_name or "Co-Director"
        role_name = relationship.primary_role.value.replace("_", " ").title()
        fallback = (
            f"Thank you, {you}. I’m {me}, and I’m glad we’re set. "
            f"I’ll work with you as your {role_name}, and I’ll keep your collaboration preferences in mind. "
            f"Whenever you’re ready, tell me about the project — I’m listening and looking forward to building it with you."
        )

    started = time.perf_counter()
    template_reply = compose_reply(plan, snapshot_after, director, user_message)
    if dialogue.mode == CoDirectorMode.LISTENING or dialogue.workflow_advance_policy == "HOLD":
        template_reply = fallback
    if re.search(
        r"\b(i(?:'|’)ve filled in how i(?:'|’)d like us to work|skip the setup form for now)\b",
        user_message or "",
        re.I,
    ):
        # Prefer the warm acknowledgment over a terse listening stub.
        template_reply = fallback
    # Enrich fallback/template with discovery evidence so EMERGENCE never tone-only.
    if temperature.stage.value in {"EMERGENCE", "EXPLORATION"} and documentation.substantive:
        wiki_line = (
            "; ".join(documentation.summary_lines[:2])
            if documentation.reason.value == "OK"
            else f"Documentation note: {documentation.reason.value}"
        )
        hook = intrigue.distinctive_elements[0] if intrigue.distinctive_elements else (user_message[:120] if user_message else "this idea")
        reflect = intrigue.emotional_hooks[0] if intrigue.emotional_hooks else "the human stake inside the premise"
        enrich = (
            f" What stands out is {hook}. That tension matters because {reflect}. "
            f"I’ve begun documenting: {wiki_line}."
        )
        if discovery_questions and temperature.question_budget > 0:
            enrich += f" When you’re ready: {discovery_questions[0].question}"
        elif research_hint:
            enrich += f" {research_hint}"
        if enrich.strip() not in template_reply:
            template_reply = (template_reply.rstrip() + enrich).strip()
    # Hands-on preview enrichment (useful preview before major commitment)
    if active_preview and active_preview.preview_content:
        preview_enrich = format_preview_reply_enrichment(
            active_preview,
            next((a for a in readiness_list if a.artifact_type == active_preview.type), None),
        )
        if preview_enrich and preview_enrich.strip() not in template_reply:
            template_reply = (template_reply.rstrip() + preview_enrich).strip()
    if active_draft and active_draft.content and "draft ready" not in template_reply.lower():
        template_reply = (
            template_reply.rstrip()
            + f"\n\nHere's a first-pass {active_draft.type.replace('_', ' ')} draft (not approved). "
            "You can approve it, revise it, expand it, or tell me it's not ready yet."
        ).strip()
    if active_pitch and active_pitch.short_pitch:
        if active_pitch.logline not in template_reply:
            template_reply = (
                template_reply.rstrip()
                + f"\n\nPreliminary pitch (draft):\n{active_pitch.short_pitch}\n\n"
                "Does this capture the project, or does it need more heart, mystery, clarity, or focus?"
            ).strip()
    _timed_step(timings, "compose_reply", started)

    uses_llm = True  # Companion/foundation path: LLM is primary whenever a project turn runs.

    wiki_summary_for_evidence = "; ".join(documentation.summary_lines[:2]) if documentation.reason.value == "OK" else ""
    dq_text = discovery_questions[0].question if discovery_questions else ""
    response_evidence = score_response_evidence(
        template_reply,
        wiki_summary=wiki_summary_for_evidence,
        discovery_question=dq_text,
    )
    discovery_bundle.last_response_evidence = response_evidence
    processing_stages.append(CoDirectorProcessingStage.GROUNDING.value)

    discovery_actions = conversation_actions(
        temperature=temperature,
        documentation=documentation,
        has_questions=bool(discovery_questions),
        research_available=relationship.research_permission != "OFFLINE",
    )
    partnership_actions = partnership_conversation_actions(
        readiness=readiness_list,
        has_preview=bool(active_preview),
        has_draft=bool(active_draft),
        has_pitch=bool(active_pitch or partnership_bundle.pitches),
        research_available=relationship.research_permission != "OFFLINE",
    )
    # Prefer partnership actions when artifact offers are live; keep continue_explaining first
    seen_ids = set()
    actions: list[dict[str, str]] = []
    for a in partnership_actions + discovery_actions:
        if a["id"] in seen_ids:
            continue
        seen_ids.add(a["id"])
        actions.append(a)
        if len(actions) >= 4:
            break

    # Premature wiki-success claims are forbidden until deferred verification (never on TTFT path).
    _wiki_success_claim = bool(
        re.search(
            r"\b(?:"
            r"added to (?:the )?wiki|"
            r"updated (?:the )?wiki|"
            r"wiki (?:has been |was )?(?:updated|saved)|"
            r"saved to (?:the )?wiki|"
            r"documented in (?:the )?wiki|"
            r"begun documenting|"
            r"added:\s*\d+\s+confirmed"
            r")\b",
            template_reply or "",
            re.I,
        )
    )
    # On defer path candidate_count is stubbed to 0 — any success claim is premature.
    fake_wiki = _wiki_success_claim and int(documentation.candidate_count or 0) == 0

    major_ready = [a for a in readiness_list if major_offer_requires_preview(a)]
    preview_ok = (
        not major_ready
        or bool(active_preview and active_preview.preview_content)
        or bool(active_draft)
    )
    why_now_ok = not major_ready or all(bool(a.why_now.strip()) for a in major_ready)

    grounding_hints = {
        "direct_critique_requested": support.support_needed == CompanionNeed.CRITIQUE,
        "no_relitigation": advisory.no_relitigation_after_confirmation
        and companion_bundle.advisoryDecisionState
        in {
            AdvisoryDecisionState.USER_CONFIRMED_CHANGE,
            AdvisoryDecisionState.USER_CONFIRMED_KEEP_CURRENT,
            AdvisoryDecisionState.COLLABORATING_ON_DIRECTION,
            AdvisoryDecisionState.CANON_UPDATED,
        },
        "exploration_only": advisory.preserve_as_variant
        or companion_bundle.advisoryDecisionState == AdvisoryDecisionState.EXPLORATORY,
        "should_encourage_with_evidence": support.support_needed == CompanionNeed.ENCOURAGE,
        "emergence_protection": temperature.stage.value == "EMERGENCE",
        "critique_allowed": temperature.critique_allowed,
        "caution_allowed": temperature.caution_allowed,
        "require_response_evidence": temperature.stage.value in {"EMERGENCE", "EXPLORATION"}
        and documentation.substantive,
        "response_evidence": response_evidence.model_dump(mode="json"),
        "fake_wiki_claim": fake_wiki,
        "user_preferred_name": relationship.user_preferred_name,
        "assistant_preferred_name": relationship.assistant_preferred_name,
        "wiki_summary": wiki_summary_for_evidence,
        "discovery_question": dq_text,
        # Partnership gates
        "require_useful_preview": bool(major_ready) and not preview_ok,
        "require_why_now": bool(major_ready) and not why_now_ok,
        "artifact_offer_active": bool(major_ready),
        "preview_present": bool(active_preview and active_preview.preview_content),
        "why_now_present": why_now_ok,
        "no_unauthorized_authorship": bool(
            active_draft
            and resolve_ownership(partnership_bundle.collaboration, active_draft.type).value == "USER_LEADS"
            and not user_auth_draft
        ),
        "personal_destination": personal_dest,
        "premature_marketing": personal_dest
        and bool(re.search(r"\b(you must market|launch campaign|monetize now)\b", template_reply or "", re.I)),
        "locked_rewrite_attempt": bool(
            re.search(r"\b(rewrit(?:e|ing)|replace) (?:the )?(?:locked )?screenplay\b", user_message or "", re.I)
        )
        and any(d.type == "screenplay" and d.status == CreativeDeliverableStatus.LOCKED for d in partnership_bundle.deliverables),
    }

    started = time.perf_counter()
    score = evaluate_success(user_message, template_reply, plan, snapshot_before, snapshot_after)
    events.append({"type": "conversation_quality", "score": score.model_dump(mode="json")})
    events.append({"type": "conversation_state", "state": state.model_dump(mode="json")})
    events.append(
        {
            "type": "companion_state",
            "state": {
                "need": support.support_needed.value,
                "workingState": support.working_state.value,
                "advisoryDecision": companion_bundle.advisoryDecisionState.value,
                "principles": len(companion_bundle.principles),
                "strengths": len(companion_bundle.creatorStrengths),
                "exploratoryVariants": len(companion_bundle.exploratoryVariants or []),
                "assemblerMode": asm_mode,
            },
        }
    )
    events.append({"type": "creative_temperature", "temperature": temperature.model_dump(mode="json")})
    events.append({"type": "intrigue", "assessment": intrigue.model_dump(mode="json")})
    events.append({"type": "documentation_result", "result": documentation.model_dump(mode="json")})
    events.append({"type": "response_evidence", "evidence": response_evidence.model_dump(mode="json")})
    events.append({"type": "discovery_questions", "questions": [q.model_dump(mode="json") for q in discovery_questions]})
    events.append({"type": "conversation_actions", "actions": actions})
    events.append({"type": "project_pulse", "pulse": pulse.model_dump(mode="json")})
    events.append({"type": "what_changed", "lines": what_changed})
    events.append(
        {
            "type": "relationship_profile",
            "profile": relationship.model_dump(mode="json"),
            "identityPolicyVersion": DISCOVERY_IDENTITY_POLICY_VERSION,
        }
    )
    events.append({"type": "processing_stages", "stages": processing_stages + [CoDirectorProcessingStage.COMPLETE.value]})
    events.append(
        {
            "type": "artifact_readiness",
            "assessments": [a.model_dump(mode="json") for a in readiness_list],
            "policyVersion": HANDS_ON_POLICY_VERSION,
        }
    )
    if active_preview:
        events.append({"type": "deliverable", "deliverable": active_preview.model_dump(mode="json")})
    if active_draft:
        events.append({"type": "deliverable", "deliverable": active_draft.model_dump(mode="json")})
    events.append({"type": "journey_state", "journey": partnership_bundle.journey.model_dump(mode="json")})
    events.append({"type": "vision_profile", "vision": partnership_bundle.vision.model_dump(mode="json")})
    if active_pitch or partnership_bundle.pitches:
        events.append(
            {
                "type": "pitch_package",
                "pitch": (active_pitch or partnership_bundle.pitches[-1]).model_dump(mode="json"),
            }
        )
    events.append({"type": "marketing_strategy", "marketing": partnership_bundle.marketing.model_dump(mode="json")})
    events.append(
        {
            "type": "collaboration_profile",
            "collaboration": partnership_bundle.collaboration.model_dump(mode="json"),
        }
    )
    _timed_step(timings, "success_score", started)

    started = time.perf_counter()
    save_snapshot(db, snapshot_after)
    save_companion_bundle(db, project_id, companion_bundle)
    save_relationship_profile(db, project_id, relationship)
    save_discovery_bundle(db, project_id, discovery_bundle)
    save_partnership_bundle(db, project_id, partnership_bundle)
    _timed_step(timings, "save_snapshot", started)

    return ConversationCoreResult(
        plan=plan,
        snapshot=snapshot_after,
        reply=template_reply,
        score=score,
        timings=timings,
        events=events,
        intent=intent.model_dump(mode="json"),
        dialoguePlan=dialogue.model_dump(mode="json"),
        conversationState=state.model_dump(mode="json"),
        usesLlmPrimary=uses_llm,
        fallbackReply=fallback,
        generationMessages=generation_messages,
        companionSupport=support.model_dump(mode="json"),
        companionAdvisory=advisory.model_dump(mode="json"),
        companionDeviation=deviation.model_dump(mode="json") if deviation.triggered else {},
        companionBlock=block.model_dump(mode="json") if block else {},
        companionGroundingHints=grounding_hints,
        wantsSpecialistConsult=wants_specialists,
        relationshipProfile=relationship.model_dump(mode="json"),
        creativeTemperature=temperature.model_dump(mode="json"),
        intrigue=intrigue.model_dump(mode="json"),
        documentationResult=documentation.model_dump(mode="json"),
        responseEvidence=response_evidence.model_dump(mode="json"),
        discoveryQuestions=[q.model_dump(mode="json") for q in discovery_questions],
        conversationActions=actions,
        projectPulse=pulse.model_dump(mode="json"),
        whatChanged=what_changed,
        processingStages=processing_stages + [CoDirectorProcessingStage.COMPLETE.value],
        livingBrief=discovery_bundle.brief.model_dump(mode="json"),
        artifactReadiness=[a.model_dump(mode="json") for a in readiness_list],
        activeDeliverable=(active_draft or active_preview).model_dump(mode="json")
        if (active_draft or active_preview)
        else {},
        journeyState=partnership_bundle.journey.model_dump(mode="json"),
        visionProfile=partnership_bundle.vision.model_dump(mode="json"),
        pitchPackage=(
            (active_pitch or partnership_bundle.pitches[-1]).model_dump(mode="json")
            if (active_pitch or partnership_bundle.pitches)
            else {}
        ),
        marketingStrategy=partnership_bundle.marketing.model_dump(mode="json"),
        collaborationProfile=partnership_bundle.collaboration.model_dump(mode="json"),
    )
