"""Authoritative creative decision loop: LISTEN→…→PREPARE NEXT OPENING."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from .canon_safety import assert_not_promoted_to_canon, build_knowledge
from .contracts import (
    CoDirectorCreativeDecision,
    CreativeOperatingBundle,
    InitiativeLevel,
    ResponsePosture,
)
from .curiosity import (
    mark_answered_from_message,
    question_budget,
    select_surface_question,
    upsert_curiosity_threads,
)
from .disagreement import synthesize_disagreement
from .format_detect import detect_project_format, uses_episodes
from .forward import (
    build_forward_suggestions,
    detect_episode_progression,
    surface_one,
)
from .minds import (
    evaluate_minds,
    extract_insight_seeds,
    extract_open_questions,
    interpret_user_need,
    listening_only,
    map_creative_stage,
)
from .openings import detect_creative_openings, strongest_opening
from .persistence import load_bundle, save_bundle


_POSTURE_MAP: dict[str, ResponsePosture] = {
    "LISTEN": "LISTEN",
    "ENCOURAGEMENT": "ENCOURAGE",
    "DEVELOPMENT": "DEVELOP",
    "CRITIQUE": "REVIEW",
    "CORRECTION": "ORGANIZE",
    "PRODUCTION": "EXECUTE",
    "EXECUTION": "EXECUTE",
    "RESEARCH": "ADVISE",
}


def run_creative_decision_loop(
    db: Session,
    *,
    project_id: str,
    user_message: str,
    discovery_stage: str | None = None,
    primary_project_type: str | None = None,
    snapshot_format: str | None = None,
    initiative_override: InitiativeLevel | None = None,
    specialist_positions: dict[str, str] | None = None,
    persist: bool = True,
) -> tuple[CoDirectorCreativeDecision, CreativeOperatingBundle]:
    """Foreground-safe decision (heuristics only). Heavy org stays in background service."""
    bundle = load_bundle(db, project_id)
    if initiative_override:
        bundle.initiativeLevel = initiative_override

    loop_steps = [
        "LISTEN",
        "INTERPRET",
        "EXTRACT",
        "CONNECT",
        "DECIDE",
        "RESPOND",
        "ORGANIZE",
        "PREPARE_NEXT_OPENING",
    ]

    user_need = interpret_user_need(user_message)
    creative_stage = map_creative_stage(discovery_stage, len((user_message or "").split()), user_need)
    project_format = detect_project_format(
        primary_project_type=primary_project_type,
        snapshot_format=snapshot_format,
        user_message=user_message,
        prior=bundle.projectFormat,
    )
    bundle.projectFormat = project_format
    bundle.creativeStage = creative_stage

    is_listening = listening_only(
        user_need=user_need, initiative=bundle.initiativeLevel, user_message=user_message
    )
    mark_answered_from_message(bundle, user_message)

    insights = extract_insight_seeds(user_message)
    open_qs = extract_open_questions(user_message)
    knowledge = assert_not_promoted_to_canon(
        [
            build_knowledge(
                line,
                creator_asserted=user_need != "LISTEN" or len((user_message or "").split()) > 20,
                source_id=f"turn:{project_id[:8]}",
            )
            for line in _knowledge_lines(user_message)[:6]
        ]
    )

    has_conflicts = bool(specialist_positions) and len(specialist_positions) >= 2
    mind_notes = evaluate_minds(
        user_message=user_message,
        user_need=user_need,
        creative_stage=creative_stage,
        initiative=bundle.initiativeLevel,
        project_format=project_format,
        has_conflicts=has_conflicts,
    )

    # Curiosity threads
    thread_specs = [
        (q, "Answering this would deepen the current material.", "HIGH" if i == 0 else "MEDIUM")
        for i, q in enumerate(open_qs)
    ]
    if thread_specs:
        upsert_curiosity_threads(
            bundle, questions=thread_specs, source_id=f"turn:{project_id[:8]}"
        )

    user_requested_help = bool(
        re.search(r"\b(help me|develop|what should|workshop|discover)\b", user_message or "", re.I)
    )
    budget = question_budget(
        bundle.initiativeLevel, listening_only=is_listening, user_requested_help=user_requested_help
    )
    surfaced = select_surface_question(bundle, budget=budget, user_message=user_message)

    # Episode progression only when format uses episodes
    if uses_episodes(project_format):
        bundle.episodeProgression = detect_episode_progression(
            user_message=user_message, prior=bundle.episodeProgression
        )
    else:
        bundle.episodeProgression = None

    openings = detect_creative_openings(
        user_message=user_message,
        open_questions=open_qs,
        has_episode_gap=bool(
            bundle.episodeProgression
            and bundle.episodeProgression.latestConfirmedEpisode > 0
            and bundle.episodeProgression.nextMissingEpisode
            > bundle.episodeProgression.latestConfirmedEpisode
        ),
        format_label=project_format,
    )
    opening = strongest_opening(openings)

    foundation = [k.statement for k in knowledge if k.kind == "CONFIRMED_FACT"][:4] or insights[:3]
    unresolved = open_qs[:3]
    fwd_list = build_forward_suggestions(
        bundle,
        project_format=project_format,
        listening_only=is_listening,
        foundation_lines=foundation,
        unresolved=unresolved,
    )
    forward = None if is_listening else surface_one(fwd_list, bundle)

    disagreement = None
    if specialist_positions and len(specialist_positions) >= 2:
        disagreement = synthesize_disagreement(
            topic="Creative / continuity tension",
            positions=specialist_positions,
        )
        if disagreement:
            bundle.lastDisagreement = disagreement

    posture: ResponsePosture = _POSTURE_MAP.get(user_need, "LISTEN")
    if is_listening:
        posture = "LISTEN"
    elif surfaced and budget > 0 and posture == "LISTEN":
        posture = "QUESTION"
    elif opening and not is_listening and posture == "LISTEN":
        posture = "DEVELOP"

    required = ["project-bible-steward"]
    if user_need in {"CRITIQUE", "DEVELOPMENT"}:
        required.append("story-editor")
    if user_need == "PRODUCTION":
        required.append("producer")
    if has_conflicts:
        required.extend(["continuity-analyst", "script-supervisor"])

    decision = CoDirectorCreativeDecision(
        userNeed=user_need,
        creativeStage=creative_stage,
        initiativeLevel=bundle.initiativeLevel,
        importantNewKnowledge=knowledge,
        affectedRecordIds=[],
        strongestCreativeInsights=insights,
        strongestOpenQuestions=[surfaced.question] if surfaced else open_qs[:1],
        nextNaturalDevelopment=(forward.suggestion if forward else None)
        or (opening.suggestedAction if opening else None)
        or (opening.missingDimension if opening else None),
        wikiActions=["CLASSIFY", "ROUTE"] if knowledge else [],
        requiredSpecialists=required,
        canonState="CONFIRMED" if any(k.kind == "CONFIRMED_FACT" for k in knowledge) else "INFERRED",
        responsePosture=posture,
        projectFormat=project_format,
        listeningOnly=is_listening,
        questionBudget=budget,
        surfacedQuestion=surfaced.question if surfaced else None,
        creativeOpening=opening,
        forwardSuggestion=forward,
        disagreement=disagreement,
        mindNotes=mind_notes,
        loopCompleted=loop_steps,
    )
    bundle.lastDecision = decision
    if persist:
        save_bundle(db, bundle)
    return decision, bundle


def _knowledge_lines(user_message: str) -> list[str]:
    text = (user_message or "").strip()
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if len(p.strip()) >= 24][:8]


def decision_public_dict(decision: CoDirectorCreativeDecision) -> dict[str, Any]:
    return decision.model_dump(mode="json")
