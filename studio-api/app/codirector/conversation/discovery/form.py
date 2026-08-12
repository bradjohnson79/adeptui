"""Adaptive discovery questions from project gaps — never a giant generic questionnaire."""

from __future__ import annotations

from .schemas import (
    CreativeTemperature,
    DiscoveryQuestion,
    DiscoveryWikiCandidate,
    LivingProjectBrief,
    WikiCandidateCategory,
)


def generate_discovery_questions(
    *,
    project_id: str,
    user_message: str,
    brief: LivingProjectBrief,
    candidates: list[DiscoveryWikiCandidate],
    temperature: CreativeTemperature,
) -> list[DiscoveryQuestion]:
    budget = max(0, min(temperature.question_budget, 6))
    if budget <= 0:
        return []

    existing_cats = {c.category for c in candidates}
    fields = brief.fields or {}
    qs: list[DiscoveryQuestion] = []

    def add(question: str, explanation: str, category: str, gap: str, options: list[str] | None = None) -> None:
        if len(qs) >= budget:
            return
        qs.append(
            DiscoveryQuestion(
                project_id=project_id,
                question=question,
                explanation=explanation,
                category=category,
                options=options or ["Not decided yet"],
                allow_custom_answer=True,
                required=False,
                priority=50 - len(qs),
                source_gap_ids=[gap],
            )
        )

    # Project-specific anchors from message
    snippet = (user_message or "").strip()[:80]
    if WikiCandidateCategory.CHARACTER not in existing_cats and "main_characters" not in fields:
        add(
            f"Who stands at the center of the story you just described{f' around “{snippet}…”' if snippet else ''}?",
            "Naming the center helps continuity and later casting/visual work without freezing the whole cast.",
            "character",
            "gap:character",
        )
    if WikiCandidateCategory.LOCATION not in existing_cats and "setting" not in fields:
        add(
            "Where does this story primarily unfold, and what sensory detail should never be lost?",
            "A stable place language keeps tone and visuals coherent as scenes multiply.",
            "location",
            "gap:location",
        )
    if "central_conflict" not in fields:
        add(
            "What consequence makes the opening situation impossible to ignore?",
            "Clarifying stakes protects the emotional engine when pacing questions appear later.",
            "conflict",
            "gap:conflict",
            ["Intimate personal cost", "World-scale consequence", "Both intertwined", "Not decided yet"],
        )
    if WikiCandidateCategory.WORLD_RULE not in existing_cats:
        add(
            "Is there any rule the world must obey (what it never does)?",
            "Anti-rules and continuity promises prevent later production from softening the idea.",
            "world_rule",
            "gap:world_rule",
        )
    if temperature.stage.value in {"EXPLORATION", "FORMATION"} and "audience_experience" not in fields:
        add(
            "What do you want the audience to feel in the first ten minutes?",
            "Audience feeling guides tone, music, and shot language once production begins.",
            "audience",
            "gap:audience",
        )

    return qs[:budget]
