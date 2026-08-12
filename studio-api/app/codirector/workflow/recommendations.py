"""Professional next-action recommendation engine — grounded in evidence, not generic."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .definitions import WorkflowDefinition, WorkflowRequirementType
from .reconciliation import WorkflowAssessment


class WorkflowRecommendation(BaseModel):
    action: str
    reason: str
    stage: str
    requirement_type: WorkflowRequirementType = WorkflowRequirementType.RECOMMENDED
    route_target: Optional[str] = None
    priority: int = 50


def recommend_next_actions(
    assessment: WorkflowAssessment,
    *,
    creator_goal: Optional[str] = None,
    route_decision_action: Optional[str] = None,
    partnership_preferences: Optional[dict[str, Any]] = None,
    deferred_recommendations: Optional[list[str]] = None,
    max_recommendations: int = 4,
) -> list[WorkflowRecommendation]:
    """Produce ranked professional next-action recommendations.

    Ranking priority (§6J):
    1. Creator's explicit current goal
    2. Unresolved blocker for that goal
    3. Current active task
    4. Major-stage readiness (stage boundary approaching)
    5. Professional best practice
    6. Optional enhancement

    Max ~4 recommendations. Not 20.
    """

    deferred = set(deferred_recommendations or [])
    candidates: list[WorkflowRecommendation] = []

    # 1. Check if there are BLOCKING requirements that must be resolved
    for blocker in assessment.blockers:
        if blocker.type in ("BLOCKING", "REQUIRED") and blocker.supported_action:
            if blocker.supported_action not in deferred:
                candidates.append(
                    WorkflowRecommendation(
                        action=blocker.supported_action,
                        reason=blocker.reason,
                        stage=assessment.active_stage_candidates[0] if assessment.active_stage_candidates else "unknown",
                        requirement_type=blocker.type,
                        priority=10,
                    )
                )

    # 2. For each active stage candidate, add recommended actions
    for stage_id in assessment.active_stage_candidates:
        rec = _action_for_stage(stage_id)
        if rec and rec.action not in deferred and not any(c.action == rec.action for c in candidates):
            candidates.append(rec)

    # 3. Add high-maturity readiness gaps for active stages
    for stage in assessment.evidenced_stages:
        if stage.stage_id in assessment.active_stage_candidates:
            for blocker in stage.blockers:
                if blocker.type == "RECOMMENDED" and blocker.supported_action and blocker.supported_action not in deferred:
                    if not any(c.action == blocker.supported_action for c in candidates):
                        candidates.append(
                            WorkflowRecommendation(
                                action=blocker.supported_action,
                                reason=blocker.reason,
                                stage=stage.stage_id,
                                requirement_type=WorkflowRequirementType.RECOMMENDED,
                                priority=30,
                            )
                        )

    # 4. If creator has an explicit goal, find related recommendation
    if creator_goal:
        goal_rec = _action_for_goal(creator_goal)
        if goal_rec and goal_rec.action not in deferred:
            goal_rec.priority = 5
            candidates.insert(0, goal_rec)

    # 5. Deduplicate by action name
    seen: set[str] = set()
    unique: list[WorkflowRecommendation] = []
    for c in candidates:
        if c.action not in seen:
            seen.add(c.action)
            unique.append(c)

    unique.sort(key=lambda r: r.priority)
    return unique[:max_recommendations]


def _action_for_stage(stage_id: str) -> Optional[WorkflowRecommendation]:
    """Map workflow stage to a natural next action."""
    mapping: dict[str, WorkflowRecommendation] = {
        "concept": WorkflowRecommendation(
            action="develop_concept", reason="Start developing your creative concept.",
            stage="concept", requirement_type=WorkflowRequirementType.REQUIRED, route_target="discuss", priority=20,
        ),
        "story_development": WorkflowRecommendation(
            action="write_story", reason="Develop the story foundation.",
            stage="story_development", requirement_type=WorkflowRequirementType.REQUIRED, route_target="discuss", priority=20,
        ),
        "script": WorkflowRecommendation(
            action="open_script_writer", reason="Open Script Writer to draft your script.",
            stage="script", requirement_type=WorkflowRequirementType.REQUIRED, route_target="navigate_script_writer", priority=20,
        ),
        "shot_planning": WorkflowRecommendation(
            action="create_shot_breakdown", reason="Break the script into shots.",
            stage="shot_planning", requirement_type=WorkflowRequirementType.RECOMMENDED, route_target="propose_creative_change", priority=25,
        ),
        "visual_development": WorkflowRecommendation(
            action="explore_visual_concepts", reason="Explore visual concepts and references.",
            stage="visual_development", requirement_type=WorkflowRequirementType.RECOMMENDED, route_target="discuss", priority=30,
        ),
        "generation": WorkflowRecommendation(
            action="generate_test_assets", reason="Generate test images or video.",
            stage="generation", requirement_type=WorkflowRequirementType.RECOMMENDED, route_target="propose_creative_change", priority=35,
        ),
        "audio": WorkflowRecommendation(
            action="create_audio", reason="Work on voice, sound, or music.",
            stage="audio", requirement_type=WorkflowRequirementType.RECOMMENDED, route_target="navigate_audio_studio", priority=40,
        ),
        "timeline": WorkflowRecommendation(
            action="open_timeline", reason="Assemble your shots in the Timeline.",
            stage="timeline", requirement_type=WorkflowRequirementType.RECOMMENDED, route_target="navigate_timeline", priority=45,
        ),
        "finishing": WorkflowRecommendation(
            action="final_review", reason="Begin final review and finishing.",
            stage="finishing", requirement_type=WorkflowRequirementType.RECOMMENDED, route_target="discuss", priority=50,
        ),
    }
    return mapping.get(stage_id)


def _action_for_goal(goal: str) -> Optional[WorkflowRecommendation]:
    """Map a creator's stated goal to a recommendation."""
    lower = goal.lower()
    if "script" in lower or "write" in lower or "screenplay" in lower:
        return _action_for_stage("script")
    if "shot" in lower or "breakdown" in lower:
        return _action_for_stage("shot_planning")
    if "character" in lower or "korri" in lower:
        return WorkflowRecommendation(
            action="develop_character", reason="Develop Korri's character profile.",
            stage="story_development", requirement_type=WorkflowRequirementType.RECOMMENDED, route_target="discuss", priority=10,
        )
    if "visual" in lower or "look" in lower or "tone" in lower or "concept" in lower:
        return _action_for_stage("visual_development")
    if "timeline" in lower or "edit" in lower or "assembly" in lower:
        return _action_for_stage("timeline")
    if "audio" in lower or "voice" in lower or "sound" in lower:
        return _action_for_stage("audio")
    if "generate" in lower or "render" in lower or "image" in lower or "video" in lower:
        return _action_for_stage("generation")
    return None
