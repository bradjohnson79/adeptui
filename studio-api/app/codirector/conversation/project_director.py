"""Deterministic project director state refresh."""

from __future__ import annotations

from .creative_state import DEFAULT_SUBSTATES
from .schemas import ConversationPlan, ProjectDirectorState, ProjectIntelligenceSnapshot


def _clean_message(text: str) -> str:
    compact = " ".join((text or "").split())
    return compact[:160]


def _stage_recommendation(stage: str, substate: str | None) -> str:
    recommendations = {
        "Project Creation": "Choose a clear project title and a one-sentence creative premise.",
        "Vision": "Lock the premise, tone, and format so later choices stay aligned.",
        "World Building": "Define the world rules that will shape character and story decisions.",
        "Characters": "Anchor the cast with a lead character goal, flaw, and relationship pressure.",
        "Episode Structure": "Outline the season arc and break it into episode-level turns.",
        "Scenes": "Turn the current story beat into a focused scene with a clear purpose.",
        "Dialogue": "Write the emotional objective of the exchange before refining lines.",
        "Production Planning": "Choose the next production-ready task that can move the project forward today.",
        "Generation": "Prepare the next asset or render request with the creative intent already decided.",
        "Editing": "Review what is working and tighten pacing or continuity in the current cut.",
        "Final Delivery": "Confirm the final deliverables, polish details, and prepare the handoff.",
    }
    recommendation = recommendations.get(stage, recommendations["Project Creation"])
    if stage == "Characters" and substate == "Lead Character":
        return "Define the lead character's goal, flaw, and emotional pressure before expanding the rest of the cast."
    return recommendation


def _goal_for_stage(stage: str) -> str:
    goals = {
        "Project Creation": "Establish the project's identity.",
        "Vision": "Clarify the creative vision.",
        "World Building": "Solidify the world and its rules.",
        "Characters": "Define the core cast.",
        "Episode Structure": "Shape the story arc.",
        "Scenes": "Turn the story into playable scenes.",
        "Dialogue": "Refine what the characters say and mean.",
        "Production Planning": "Translate story decisions into production work.",
        "Generation": "Create the assets needed for the project.",
        "Editing": "Polish and refine the generated material.",
        "Final Delivery": "Prepare the finished project for delivery.",
    }
    return goals.get(stage, "Advance the project.")


def refresh_director(
    snapshot: ProjectIntelligenceSnapshot,
    plan_hints: ConversationPlan | None,
    user_message: str,
) -> ProjectDirectorState:
    """Refresh the deterministic project director state."""

    stage = (plan_hints.creativeStage if plan_hints else snapshot.currentStage) or "Project Creation"
    substate = (
        plan_hints.creativeSubstate if plan_hints else snapshot.currentSubstate
    ) or DEFAULT_SUBSTATES.get(stage)
    outstanding_questions = [question for question in snapshot.openQuestions if question]

    blocked_items: list[str] = []
    if not (snapshot.title or "").strip() or snapshot.title == "Untitled Project":
        blocked_items.append("Project title has not been finalized yet.")
    if plan_hints:
        blocked_items.extend(flag for flag in plan_hints.contradictionFlags if flag not in blocked_items)
    else:
        blocked_items.extend(flag for flag in snapshot.contradictions if flag not in blocked_items)

    current_goal = snapshot.currentObjective or _goal_for_stage(stage)
    current_task = _clean_message(user_message) or snapshot.director.currentTask or "Continue the conversation."

    return ProjectDirectorState(
        currentGoal=current_goal,
        currentTask=current_task,
        recentlyCompleted=snapshot.recentDecisions[:3],
        outstandingQuestions=outstanding_questions,
        blockedItems=blocked_items,
        recommendedNextStep=_stage_recommendation(stage, substate),
        creativeStage=stage,
        creativeSubstate=substate,
        revision=max(snapshot.director.revision, snapshot.revision) + 1,
    )
