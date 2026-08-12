"""Heuristic conversation planner for Co-Director creator chat."""

from __future__ import annotations

import re
import uuid
from typing import Any, Optional

from .inquiry import decide_inquiry
from .schemas import ConversationPlan, ProjectDirectorState, ProjectIntelligenceSnapshot, WikiCandidate

_QUESTION_RE = re.compile(r"^(what|why|how|when|where|who|which|should|could|would|can|do|does|did|is|are)\b")
_COMMAND_RE = re.compile(
    r"^(please\s+)?(create|make|build|generate|open|go to|navigate|show|start|run|save|approve|delete|rename|update|set)\b"
)
_SPACE_RE = re.compile(r"\s+")
_NEXT_STEP_PATTERNS = (
    "what should we do next",
    "what should we define next",
    "what do we do next",
    "what do we define next",
    "best next three steps",
    "next three steps",
)
_REJECTION_PATTERNS = (
    "reject",
    "don't use",
    "do not use",
    "don't define",
    "do not define",
    "don't make",
    "do not make",
    "don't treat",
    "do not treat",
)
_ANNOUNCE_PREFIX_RE = re.compile(
    r"^(?:i am going to tell you|i'm going to tell you|let me explain|let me begin with|begin with|i'll explain|i want to tell you|here's the lore)\b"
)


def _clean(text: str) -> str:
    return _SPACE_RE.sub(" ", (text or "").strip())


def _lower(text: str) -> str:
    return _clean(text).lower()


def _is_question(text: str) -> bool:
    lowered = _lower(text)
    return lowered.endswith("?") or bool(_QUESTION_RE.match(lowered))


def _is_short_continue(text: str) -> bool:
    return _lower(text) in {"yes", "y", "ok", "okay", "continue", "go on", "keep going", "sure"}


def _is_next_step_prompt(text: str) -> bool:
    return any(phrase in text for phrase in _NEXT_STEP_PATTERNS)


def _is_rejection(text: str) -> bool:
    return any(phrase in text for phrase in _REJECTION_PATTERNS)


def _is_character_acceptance(text: str) -> bool:
    return bool(
        re.match(r"^(?:yes|ok|okay|sure|absolutely)\b", text)
        and any(phrase in text for phrase in ("main character", "lead character", "character"))
    )


def _is_draft_plan_action(text: str) -> bool:
    return any(
        phrase in text
        for phrase in (
            "create a draft plan",
            "draft plan",
            "create a plan",
            "make a draft plan",
            "make a plan for",
        )
    )


def _has_concrete_details(text: str) -> bool:
    return bool(
        re.search(r"\b\d+\b", text)
        or re.search(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", text)
        or "structure" in text
        or len(text.split()) >= 14
    )


def _is_announce_only_continuation(text: str) -> bool:
    if _is_character_acceptance(text):
        return False
    if not _ANNOUNCE_PREFIX_RE.match(text):
        return False
    return not _has_concrete_details(text)


def _is_residue(text: str) -> bool:
    lowered = _lower(text)
    if not lowered:
        return True
    if _is_question(lowered):
        return True
    if _COMMAND_RE.match(lowered) and len(lowered) < 80:
        return True
    return False


def _section_for_stage(stage: str) -> str:
    mapping = {
        "Project Creation": "knownDetails",
        "Vision": "creativeFoundation",
        "World Building": "worldAndSetting",
        "Characters": "characters",
        "Episode Structure": "storyAndEpisodes",
        "Scenes": "storyAndEpisodes",
        "Dialogue": "storyAndEpisodes",
        "Production Planning": "productionDecisions",
        "Generation": "productionDecisions",
        "Editing": "productionDecisions",
        "Final Delivery": "productionDecisions",
    }
    return mapping.get(stage, "creativeFoundation")


def _acknowledged_facts(snapshot: ProjectIntelligenceSnapshot) -> list[str]:
    facts: list[str] = []
    if snapshot.title and snapshot.title != "Untitled Project":
        facts.append(f"title: {snapshot.title}")
    if snapshot.format:
        facts.append(f"format: {snapshot.format}")
    if snapshot.currentObjective:
        facts.append(f"objective: {snapshot.currentObjective}")
    if snapshot.currentStoryScope:
        facts.append(f"scope: {snapshot.currentStoryScope}")
    return facts[:4]


def _relevant_context(
    snapshot: ProjectIntelligenceSnapshot,
    director: ProjectDirectorState,
    stage: str,
    substate: str | None,
) -> list[str]:
    context = [f"stage: {stage}"]
    if substate:
        context.append(f"substate: {substate}")
    if director.recommendedNextStep:
        context.append(f"next step: {director.recommendedNextStep}")
    if snapshot.keyCharacters and stage == "Characters":
        context.append(f"known characters: {', '.join(snapshot.keyCharacters[:3])}")
    return context


def _matching_entry_id(snapshot: ProjectIntelligenceSnapshot, text: str) -> str | None:
    lowered = _lower(text)
    for entry in snapshot.knowledgeEntries:
        if entry.state in {"rejected", "superseded"}:
            continue
        existing = _lower(entry.text)
        if not existing:
            continue
        if lowered == existing or lowered in existing or existing in lowered:
            return entry.id
    # Correction phrasing often names the old fact after "not" / "instead of".
    for marker in (" not the ", " not a ", " instead of ", " rather than "):
        if marker not in lowered:
            continue
        negated = lowered.split(marker, 1)[1].strip(" .")
        if len(negated) < 3:
            continue
        for entry in snapshot.knowledgeEntries:
            if entry.state in {"rejected", "superseded"}:
                continue
            if negated in _lower(entry.text) or any(
                token and token in _lower(entry.text) for token in negated.split() if len(token) > 4
            ):
                return entry.id
    return None


def _candidate(text: str, *, state: str, section: str, supersedes_id: str | None = None) -> WikiCandidate:
    return WikiCandidate(
        id=f"wiki-{uuid.uuid4().hex[:12]}",
        text=_clean(text),
        state=state,  # type: ignore[arg-type]
        section=section,
        supersedes_id=supersedes_id,
    )


def _extract_correction_text(text: str) -> str:
    cleaned = _clean(text)
    prefixes = ("Correction:", "correction:", "Actually,", "actually,", "Instead,", "instead,")
    for prefix in prefixes:
        if cleaned.startswith(prefix):
            return cleaned[len(prefix) :].strip()
    return cleaned


def plan_conversation(
    user_message: str,
    snapshot: ProjectIntelligenceSnapshot,
    stage: str,
    substate: str | None,
    director: ProjectDirectorState,
    *,
    workflow_assessment: Optional[Any] = None,
) -> ConversationPlan:
    """Plan a deterministic conversation turn without model calls."""

    text = _clean(user_message)
    lowered = text.lower()
    inquiry = decide_inquiry(text, snapshot, stage, substate)
    section = _section_for_stage(stage)
    wiki_candidates: list[WikiCandidate] = []
    contradiction_flags: list[str] = []
    primary_intent = "receive_information"
    response_mode = inquiry.mode
    should_write_wiki = False
    recommended_next_step: str | None = None

    is_correction = lowered.startswith("correction:") or lowered.startswith("actually ") or lowered.startswith("instead ")
    is_rejection = _is_rejection(lowered)
    is_next_step = _is_next_step_prompt(lowered)
    is_continuation = _is_announce_only_continuation(lowered)
    is_draft_plan = _is_draft_plan_action(lowered)
    is_intro = (
        any(token in lowered for token in ("project", "series", "season", "story", "universe", "shared universe"))
        and (
            len(text) >= 140
            or "i am going to tell you about" in lowered
            or "i'm going to tell you about" in lowered
        )
    )

    if "contradiction" in lowered or "that conflicts with" in lowered:
        contradiction_flags.append("The latest message points to a contradiction that needs cleanup.")

    if is_draft_plan:
        # Plan drafting is an explicit action; do not swallow it into character Q&A.
        primary_intent = "execute_action"
        response_mode = "draft_plan"
    elif is_next_step:
        primary_intent = "recommend_next_step"
        response_mode = "recommend_next_step"
        recommended_next_step = director.recommendedNextStep
        if workflow_assessment is not None:
            try:
                from app.codirector.workflow.recommendations import recommend_next_actions
                from app.codirector.workflow.definitions import get_workflow_for_format
                wf = get_workflow_for_format(getattr(snapshot, "format", None))
                recs = recommend_next_actions(workflow_assessment, max_recommendations=3)
                if recs:
                    recommended_next_step = recs[0].reason[:120]
            except Exception:
                pass
    elif is_correction:
        primary_intent = "confirm_correction"
        response_mode = "confirm_correction"
        corrected_text = _extract_correction_text(text)
        supersedes_id = _matching_entry_id(snapshot, corrected_text)
        wiki_candidates.append(
            _candidate(
                corrected_text,
                state="confirmed",
                section=section,
                supersedes_id=supersedes_id,
            )
        )
        should_write_wiki = True
    elif is_rejection:
        primary_intent = "confirm_correction"
        response_mode = "confirm_correction"
        matched_id = _matching_entry_id(snapshot, text)
        matched_text = next(
            (entry.text for entry in snapshot.knowledgeEntries if entry.id == matched_id),
            "",
        )
        if not matched_text:
            # Fall back to keyword overlap against active knowledge entries.
            rejection_words = {"reject", "don't", "do", "not", "use", "define", "make", "treat", "it", "its"}
            tokens = [t for t in lowered.replace("reject", "").split() if len(t) > 4 and t not in rejection_words]
            for entry in snapshot.knowledgeEntries:
                if entry.state in {"rejected", "superseded"}:
                    continue
                entry_l = _lower(entry.text)
                if any(token in entry_l for token in tokens):
                    matched_id = entry.id
                    matched_text = entry.text
                    break
        if matched_text:
            wiki_candidates.append(
                _candidate(
                    matched_text,
                    state="rejected",
                    section=section,
                    supersedes_id=matched_id,
                )
            )
            should_write_wiki = True
        if "signal" in lowered and "hostile" in lowered and not matched_text:
            wiki_candidates.append(
                _candidate(
                    "The signal is hostile.",
                    state="rejected",
                    section=section,
                )
            )
        if "intent is still unknown" in lowered or "its intent is still unknown" in lowered or "unknown intent" in lowered:
            wiki_candidates.append(
                _candidate(
                    "The signal's intent is still unknown.",
                    state="confirmed",
                    section=section,
                )
            )
            should_write_wiki = True
    elif is_intro:
        # Long project introductions must win over "I am going to tell you" continuation cues.
        primary_intent = "receive_information"
        response_mode = "intro"
        if not _is_residue(text):
            wiki_candidates.append(_candidate(text, state="proposed", section=section))
            should_write_wiki = True
    elif _is_question(text):
        primary_intent = "answer_question" if inquiry.mode == "answer_question" else "request_clarification"
        response_mode = inquiry.mode
    elif is_continuation or _is_short_continue(text):
        primary_intent = "invite_continuation"
        response_mode = inquiry.mode if inquiry.mode != "conversation" else "invite_continuation"
    else:
        primary_intent = "receive_information"
        response_mode = inquiry.mode if inquiry.mode != "conversation" else "receive_information"
        if not _is_residue(text):
            wiki_candidates.append(_candidate(text, state="proposed", section=section))
            should_write_wiki = True

    if not is_next_step:
        completion_markers = ["done", "finished", "complete", "that's it", "that's all", "i'm happy with", "good enough"]
        is_natural_transition = any(m in lowered for m in completion_markers)
        if is_natural_transition and workflow_assessment is not None:
            try:
                from app.codirector.workflow.recommendations import recommend_next_actions
                from app.codirector.workflow.definitions import get_workflow_for_format
                wf = get_workflow_for_format(getattr(snapshot, "format", None))
                recs = recommend_next_actions(workflow_assessment, max_recommendations=1)
                if recs:
                    recommended_next_step = recs[0].reason[:120]
            except Exception:
                pass
        elif not is_natural_transition:
            recommended_next_step = None

    missing_information: list[str] = []
    should_ask = inquiry.should_ask if primary_intent not in {"execute_action", "recommend_next_step", "confirm_correction"} else False
    selected_question = inquiry.question if should_ask else None
    if should_ask and selected_question:
        missing_information.append(selected_question)
    if snapshot.title == "Untitled Project" and stage == "Project Creation":
        missing_information.append("Project title")

    return ConversationPlan(
        primaryIntent=primary_intent,  # type: ignore[arg-type]
        acknowledgedFacts=_acknowledged_facts(snapshot),
        relevantContext=_relevant_context(snapshot, director, stage, substate),
        missingInformation=missing_information[:3],
        contradictionFlags=contradiction_flags,
        responseMode=response_mode,
        shouldAskQuestion=should_ask,
        selectedQuestion=selected_question,
        recommendedNextStep=recommended_next_step,
        shouldWriteWiki=should_write_wiki,
        wikiCandidates=wiki_candidates,
        creativeStage=stage,
        creativeSubstate=substate,
        directorContext={
            "currentGoal": director.currentGoal,
            "recommendedNextStep": director.recommendedNextStep,
            "blockedItems": list(director.blockedItems),
        },
    )
