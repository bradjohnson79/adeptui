"""Contextual next-step options — soft invitations, not menus."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session


def _project_settings(project: Any) -> dict[str, Any]:
    raw = getattr(project, "settings_json", None)
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:  # noqa: BLE001
            return {}
    return {}

CoDirectorNextStepType = Literal[
    "CONTINUE_STORY",
    "EXPLORE_CHARACTER",
    "EXPLORE_WORLD",
    "EXPLORE_RULES",
    "BUILD_STORY_TEMPLATE",
    "BUILD_TREATMENT",
    "BUILD_OUTLINE",
    "DEVELOP_SCENE",
    "DEVELOP_EPISODE",
    "CREATE_CONCEPTS",
    "VISUAL_DEVELOPMENT",
    "TONE_AND_ATMOSPHERE",
    "RESEARCH_COMPARABLES",
    "BUILD_PITCH",
    "REVIEW_WIKI",
    "REVIEW_OPEN_QUESTIONS",
    "KEEP_LISTENING",
]

Readiness = Literal["AVAILABLE", "PARTIAL", "NOT_READY"]

_DEFERRED_KEY = "deferredNextSteps"


class CoDirectorNextStepOption(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: CoDirectorNextStepType
    label: str
    shortDescription: str | None = None
    whyNow: str | None = None
    readiness: Readiness = "AVAILABLE"
    ownershipRequired: bool = False
    priority: int = 50
    previewSpine: str | None = None


class DeferredNextStep(BaseModel):
    projectId: str
    optionType: CoDirectorNextStepType
    deferredAt: str
    reconsiderAfterStage: str | None = None
    userReason: str | None = None


_ROLE_PRIORITY: dict[str, list[CoDirectorNextStepType]] = {
    "STORY_PARTNER": [
        "CONTINUE_STORY",
        "EXPLORE_CHARACTER",
        "BUILD_TREATMENT",
        "BUILD_OUTLINE",
        "DEVELOP_SCENE",
    ],
    "PRODUCER": [
        "BUILD_TREATMENT",
        "BUILD_PITCH",
        "BUILD_OUTLINE",
        "CONTINUE_STORY",
        "REVIEW_OPEN_QUESTIONS",
    ],
    "CREATIVE_DIRECTOR": [
        "VISUAL_DEVELOPMENT",
        "TONE_AND_ATMOSPHERE",
        "CREATE_CONCEPTS",
        "CONTINUE_STORY",
        "EXPLORE_WORLD",
    ],
    "RESEARCH_PARTNER": [
        "RESEARCH_COMPARABLES",
        "EXPLORE_WORLD",
        "CONTINUE_STORY",
        "REVIEW_WIKI",
    ],
    "BALANCED": [
        "CONTINUE_STORY",
        "EXPLORE_CHARACTER",
        "BUILD_TREATMENT",
        "VISUAL_DEVELOPMENT",
        "BUILD_PITCH",
    ],
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _has_active_execution(db: Session, project_id: str) -> bool:
    """Return True when there is a non-terminal execution pack for this project.

    The execution pack store is owned by Workstream C and may not exist yet —
    every import is guarded so absence degrades gracefully to "no active
    execution" (existing behavior). This never raises.
    """
    if not project_id:
        return False
    try:
        from .execution import contracts as _exec_contracts  # noqa: F401

        # The pack store lives in Workstream C; import lazily and tolerate absence.
        try:
            from .execution.pack_store import (  # type: ignore[attr-defined]
                get_active_execution_for_project,
            )
        except Exception:  # noqa: BLE001
            return False
        plan = get_active_execution_for_project(db, project_id)
        if plan is None:
            return False
        return not bool(getattr(plan, "is_terminal", True))
    except Exception:  # noqa: BLE001
        return False


def _last_completed_execution(db: Session, project_id: str):
    """Return the most recent terminal execution pack for this project, or None.

    Used to surface capability-aware post-completion actions (Regenerate Frame,
    Open in Library, Send to Timeline). Guards the Workstream C pack store
    import; absence returns None.
    """
    if not project_id:
        return None
    try:
        try:
            from .execution.pack_store import (  # type: ignore[attr-defined]
                get_last_completed_execution_for_project,
            )
        except Exception:  # noqa: BLE001
            return None
        return get_last_completed_execution_for_project(db, project_id)
    except Exception:  # noqa: BLE001
        return None


# Capability-aware post-completion actions (spec §42, Workstream H).
# These are shown INSTEAD of generic next-step cards once an execution has
# completed, so the creator is invited to act on the real result set rather
# than continue chatting abstractly.
_POST_COMPLETION_ACTIONS: dict[str, list[tuple[str, str, str]]] = {
    # capability_id -> list of (label, why_now, option_type)
    "storyboard.generate": [
        ("Regenerate a frame", "Adjust one frame without losing the others.", "VISUAL_DEVELOPMENT"),
        ("Open in Library", "Review the generated frames in your Library.", "REVIEW_WIKI"),
        ("Send to Timeline", "Place frames on the Timeline to start cutting.", "DEVELOP_SCENE"),
    ],
    "image.generate": [
        ("Open in Library", "Review the generated images in your Library.", "REVIEW_WIKI"),
        ("Send to Timeline", "Place images on the Timeline.", "DEVELOP_SCENE"),
    ],
    "image.generate_batch": [
        ("Open in Library", "Review the batch in your Library.", "REVIEW_WIKI"),
        ("Send to Timeline", "Place images on the Timeline.", "DEVELOP_SCENE"),
    ],
    "voice.generate": [
        ("Open in Library", "Listen to the voice clips in your Library.", "REVIEW_WIKI"),
    ],
}


def _build_post_completion_options(
    db: Session,
    *,
    project_id: str,
    user_message: str,
) -> list[CoDirectorNextStepOption]:
    """Surface capability-aware actions after an execution completes.

    Falls back to an empty list when no completed execution exists or the
    capability is not mapped. This is intentionally narrow — it never invents
    actions for capabilities we don't recognize.
    """
    plan = _last_completed_execution(db, project_id)
    if plan is None:
        return []
    capability = getattr(plan, "capability", "") or ""
    actions = _POST_COMPLETION_ACTIONS.get(capability)
    if not actions:
        return []
    deferred = {d.optionType for d in _load_deferred(db, project_id)}
    options: list[CoDirectorNextStepOption] = []
    for label, why, option_type in actions:
        if option_type in deferred:
            continue
        options.append(
            CoDirectorNextStepOption(
                type=option_type,  # type: ignore[arg-type]
                label=label,
                whyNow=why,
                readiness="AVAILABLE",
                ownershipRequired=False,
                priority=10,
            )
        )
    return options[:4]


def _load_deferred(db: Session, project_id: str) -> list[DeferredNextStep]:
    from app.db import Project

    project = db.get(Project, project_id)
    if not project:
        return []
    settings = _project_settings(project)
    raw = settings.get(_DEFERRED_KEY) or []
    out: list[DeferredNextStep] = []
    for item in raw:
        if isinstance(item, dict):
            try:
                out.append(DeferredNextStep.model_validate(item))
            except Exception:  # noqa: BLE001
                continue
    return out


def persist_deferred_option(
    db: Session,
    *,
    project_id: str,
    option_type: CoDirectorNextStepType,
    user_reason: str | None = None,
) -> None:
    from app.db import Project

    project = db.get(Project, project_id)
    if not project:
        return
    settings = _project_settings(project)
    existing = _load_deferred(db, project_id)
    existing = [d for d in existing if d.optionType != option_type]
    existing.append(
        DeferredNextStep(
            projectId=project_id,
            optionType=option_type,
            deferredAt=_utc_now(),
            userReason=user_reason,
        )
    )
    settings[_DEFERRED_KEY] = [d.model_dump(mode="json") for d in existing[-20:]]
    project.settings_json = json.dumps(settings, ensure_ascii=False)
    db.add(project)
    db.commit()


def should_offer_options(
    *,
    user_message: str,
    primary_intent: str | None,
    workflow_hold: bool,
    listen_only: bool,
) -> bool:
    text = (user_message or "").strip()
    lower = text.lower()
    if listen_only or (workflow_hold and "just listen" in lower):
        return False
    if re_narrow_factual(lower):
        return False
    creative_markers = (
        "the story",
        "character",
        "world",
        "timeline",
        "premise",
        "season",
        "episode",
        "dreamweaver",
        "filled in how",
        "develop",
        "korri",
    )
    has_creative_marker = any(k in lower for k in creative_markers)
    # Narrow factual Qs stay suppressed; creative markers always unlock invitations.
    if (
        primary_intent in {"answer_question", "request_clarification"}
        and len(text.split()) < 18
        and not has_creative_marker
    ):
        return False
    # Substantive creative share or natural pause after preferences.
    if len(text.split()) >= 35 or has_creative_marker:
        return True
    return False


def re_narrow_factual(lower: str) -> bool:
    import re

    return bool(re.search(r"^(what|when|where|who|how many|did i|is the)\b", lower)) and len(lower.split()) < 16


def treatment_readiness(known: dict[str, bool]) -> tuple[Readiness, str | None, str | None]:
    keys = ["premise", "protagonist", "conflict", "framing"]
    have = sum(1 for k in keys if known.get(k))
    missing = [k for k in keys if not known.get(k)]
    if have >= 3:
        return (
            "AVAILABLE",
            "Enough core material to shape a working treatment.",
            "Present-day stakes → inciting contact → fracture → investigation → consequence",
        )
    if have >= 1:
        return (
            "PARTIAL",
            "We could begin a working treatment and leave unresolved sections clearly marked.",
            None,
        )
    return "NOT_READY", None, None


# Phase 6 — SUPERSEDED by build_workflow_next_steps. Kept for backward compatibility.
# After Phase 6, all production next-action recommendations must come from the Workflow Engine.
def build_next_step_options(
    db: Session,
    *,
    project_id: str,
    user_message: str,
    relationship_role: str | None,
    primary_intent: str | None = None,
    workflow_hold: bool = False,
    creative_stage: str | None = None,
    wiki_candidate_count: int = 0,
    listen_only: bool = False,
) -> list[CoDirectorNextStepOption]:
    if not should_offer_options(
        user_message=user_message,
        primary_intent=primary_intent,
        workflow_hold=workflow_hold,
        listen_only=listen_only,
    ):
        return []

    # Workstream H — Agent Execution Law: while a non-terminal execution is
    # running for this project, generic suggestion cards (CONTINUE_STORY,
    # EXPLORE_CHARACTER, EXPLORE_WORLD, VISUAL_DEVELOPMENT, …) are suppressed.
    # The creator should see live execution state, not invitations to keep
    # chatting. After the execution completes, capability-aware actions are
    # surfaced instead (see _build_post_completion_options).
    if _has_active_execution(db, project_id):
        return []

    # After completion of a recent execution, offer capability-aware actions
    # (Regenerate Frame / Open in Library / Send to Timeline) instead of the
    # generic discovery cards. Falls back to legacy behavior when no recent
    # completed execution exists or the capability isn't mapped.
    post_completion = _build_post_completion_options(
        db, project_id=project_id, user_message=user_message
    )
    if post_completion:
        return post_completion

    deferred = {d.optionType for d in _load_deferred(db, project_id)}
    lower = (user_message or "").lower()
    known = {
        "premise": any(k in lower for k in ("story", "premise", "about", "world")),
        "protagonist": any(k in lower for k in ("character", "she ", "he ", "they ", "named")),
        "conflict": any(k in lower for k in ("conflict", "vs", "against", "threat", "problem")),
        "framing": any(k in lower for k in ("timeline", "flashback", "present", "frame", "testimony")),
    }
    treat_ready, treat_why, treat_preview = treatment_readiness(known)

    candidates: list[CoDirectorNextStepOption] = [
        CoDirectorNextStepOption(
            type="CONTINUE_STORY",
            label="Keep telling the story",
            shortDescription="Stay in discovery and keep unfolding naturally.",
            readiness="AVAILABLE",
            ownershipRequired=False,
            priority=5,
        ),
    ]
    if "EXPLORE_CHARACTER" not in deferred and (known["protagonist"] or wiki_candidate_count > 0):
        candidates.append(
            CoDirectorNextStepOption(
                type="EXPLORE_CHARACTER",
                label="Explore a character",
                whyNow="A person at the center of the story is already coming into focus.",
                readiness="AVAILABLE",
                ownershipRequired=False,
                priority=20,
            )
        )
    if "EXPLORE_WORLD" not in deferred and (known["premise"] or "world" in lower or "rules" in lower):
        candidates.append(
            CoDirectorNextStepOption(
                type="EXPLORE_WORLD",
                label="Define the world rules",
                whyNow="World details are already showing up in the conversation.",
                readiness="AVAILABLE",
                ownershipRequired=False,
                priority=25,
            )
        )
    if "EXPLORE_RULES" not in deferred and ("rule" in lower or "memory is" in lower or "court" in lower):
        candidates.append(
            CoDirectorNextStepOption(
                type="EXPLORE_RULES",
                label="Define the world rules",
                whyNow="A governing story rule is already on the table.",
                readiness="AVAILABLE",
                ownershipRequired=False,
                priority=26,
            )
        )
    # Treatment only when enough material exists — never force structured development.
    if treat_ready == "AVAILABLE" and "BUILD_TREATMENT" not in deferred:
        candidates.append(
            CoDirectorNextStepOption(
                type="BUILD_TREATMENT",
                label="Build a working treatment",
                whyNow=treat_why,
                readiness=treat_ready,
                ownershipRequired=True,
                priority=30,
                previewSpine=treat_preview,
            )
        )
    if "VISUAL_DEVELOPMENT" not in deferred and (
        any(k in lower for k in ("visual", "look", "tone", "atmosphere", "cinematic", "image"))
        or treat_ready == "AVAILABLE"
    ):
        candidates.append(
            CoDirectorNextStepOption(
                type="VISUAL_DEVELOPMENT",
                label="Develop visual concepts",
                whyNow="Tone and imagery can sharpen once the premise is clear.",
                readiness="AVAILABLE",
                ownershipRequired=False,
                priority=28,
            )
        )
    if "DEVELOP_EPISODE" not in deferred and any(
        k in lower for k in ("episode", "season", "series", "installment")
    ):
        candidates.append(
            CoDirectorNextStepOption(
                type="DEVELOP_EPISODE",
                label="Outline an episode",
                whyNow="Serial shape is already part of how you're telling this.",
                readiness="PARTIAL",
                ownershipRequired=False,
                priority=32,
            )
        )
    if "BUILD_PITCH" not in deferred and treat_ready == "AVAILABLE" and "pitch" in lower:
        candidates.append(
            CoDirectorNextStepOption(
                type="BUILD_PITCH",
                label="Prepare a short pitch",
                whyNow="The core premise is clear enough for a short pitch — authorship first.",
                readiness="PARTIAL",
                ownershipRequired=True,
                priority=40,
            )
        )
    if "REVIEW_WIKI" not in deferred and wiki_candidate_count > 0:
        candidates.append(
            CoDirectorNextStepOption(
                type="REVIEW_WIKI",
                label="Review Wiki updates",
                whyNow="New project notes may have been captured from this conversation.",
                readiness="AVAILABLE",
                ownershipRequired=False,
                priority=45,
            )
        )

    role = (relationship_role or "BALANCED").upper().replace(" ", "_")
    preferred = _ROLE_PRIORITY.get(role) or _ROLE_PRIORITY["BALANCED"]
    order = {t: i for i, t in enumerate(preferred)}
    candidates.sort(key=lambda o: (order.get(o.type, 100), o.priority))
    # Always keep continue-first when present.
    continue_opts = [o for o in candidates if o.type == "CONTINUE_STORY"]
    rest = [o for o in candidates if o.type != "CONTINUE_STORY"]
    return (continue_opts + rest)[:4]


# Phase 6 — supersede generic next-steps with Workflow Engine recommendations
def build_workflow_next_steps(
    db: Session,
    *,
    project_id: str,
    user_message: str,
    creator_goal: str | None = None,
    partnership_role: str | None = None,
    check_major_stage: bool = False,
) -> list[CoDirectorNextStepOption]:
    """Build next-step options from the Workflow Engine instead of generic heuristics."""
    try:
        from app.codirector.workflow.recommendations import recommend_next_actions
        from app.codirector.workflow.reconciliation import reconcile_workflow
        from app.codirector.workflow.definitions import get_workflow_for_format
    except ImportError:
        return []

    if not should_offer_options(
        user_message=user_message,
        primary_intent=None,
        workflow_hold=False,
        listen_only=False,
    ):
        return []

    # Workstream H — suppress workflow recommendations while an execution is
    # running, and surface capability-aware post-completion actions when one
    # has just completed.
    if _has_active_execution(db, project_id):
        return []
    post_completion = _build_post_completion_options(
        db, project_id=project_id, user_message=user_message
    )
    if post_completion:
        return post_completion

    deferred = {d.optionType for d in _load_deferred(db, project_id)}

    assessment = reconcile_workflow(db, project_id)
    workflow_def = get_workflow_for_format(assessment.applicable_workflow)

    # Check major-stage boundaries
    if check_major_stage and partnership_role in ("BALANCED", "CREATIVE_DIRECTOR"):
        boundary_stages = [s for s in workflow_def.stages if s.major_stage_boundary]
        for stage in boundary_stages:
            if stage.id in assessment.active_stage_candidates and stage.id not in deferred:
                return [
                    CoDirectorNextStepOption(
                        type="CONTINUE_STORY",
                        label=f"Ready to move to {stage.label}?",
                        shortDescription=f"The next major stage would normally be {stage.label}. Would you like to proceed or keep working on the current material?",
                        readiness="AVAILABLE",
                        ownershipRequired=False,
                        priority=5,
                    )
                ]

    recommendations = recommend_next_actions(
        assessment,
        creator_goal=creator_goal,
        deferred_recommendations=list(deferred),
    )

    options: list[CoDirectorNextStepOption] = []
    for rec in recommendations:
        option_type = _workflow_action_to_next_step_type(rec.action)
        if option_type and option_type not in deferred:
            options.append(
                CoDirectorNextStepOption(
                    type=option_type,
                    label=rec.reason[:60] if len(rec.reason) > 60 else rec.reason,
                    shortDescription=rec.reason,
                    readiness="AVAILABLE",
                    ownershipRequired=False,
                    priority=rec.priority,
                )
            )

    return options[:4]


def _workflow_action_to_next_step_type(action: str) -> str | None:
    """Map workflow recommendation actions to CoDirectorNextStepType constants."""
    mapping = {
        "open_script_writer": "DEVELOP_SCENE",
        "create_shot_breakdown": "CREATE_CONCEPTS",
        "explore_visual_concepts": "VISUAL_DEVELOPMENT",
        "develop_character": "EXPLORE_CHARACTER",
        "write_story": "CONTINUE_STORY",
        "develop_concept": "CONTINUE_STORY",
        "generate_test_assets": "CREATE_CONCEPTS",
        "create_audio": "DEVELOP_SCENE",
        "open_timeline": "DEVELOP_SCENE",
        "final_review": "REVIEW_WIKI",
    }
    return mapping.get(action)


def defer_workflow_recommendation(
    db: Session,
    *,
    project_id: str,
    action: str,
    reason: str | None = None,
) -> None:
    """Defer a workflow recommendation so it isn't repeated immediately."""
    option_type = _workflow_action_to_next_step_type(action)
    if option_type:
        persist_deferred_option(db, project_id=project_id, option_type=option_type, user_reason=reason)


def option_to_prompt(option: CoDirectorNextStepOption) -> str:
    if option.type == "CONTINUE_STORY":
        return "I'd like to keep telling the story — please keep listening and stay with me in discovery."
    if option.type == "BUILD_TREATMENT":
        return "I'd like to begin a working treatment from what we have so far. Ask me how we should share authorship before drafting."
    if option.type == "EXPLORE_CHARACTER":
        return "Let's explore the central character more deeply — who they are and what they want."
    if option.type == "VISUAL_DEVELOPMENT":
        return "Let's explore the visual concept and tone for the series."
    if option.type == "EXPLORE_WORLD":
        return "Let's define the world rules more clearly."
    if option.type == "BUILD_PITCH":
        return "Help me prepare a short pitch from the material we have. Ask about authorship first."
    if option.type == "REVIEW_WIKI":
        return "Please review what has been documented so far and tell me what still feels thin."
    return f"Let's continue with: {option.label}"
