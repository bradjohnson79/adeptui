"""Discovery response composition guidance (injected into generation, not a second speaker)."""

from __future__ import annotations

from ..relationship.schemas import CoDirectorRelationshipProfile
from .schemas import (
    CreativeIntrigueAssessment,
    CreativeTemperature,
    DiscoveryQuestion,
    DocumentationResult,
)


def discovery_composition_guidance(
    *,
    temperature: CreativeTemperature,
    intrigue: CreativeIntrigueAssessment,
    documentation: DocumentationResult,
    questions: list[DiscoveryQuestion],
    relationship: CoDirectorRelationshipProfile,
    research_hint: str | None = None,
) -> str:
    user = relationship.user_preferred_name or "the creator"
    assistant = relationship.assistant_preferred_name or "Co-Director"
    lines = [
        f"You are {assistant}. Address {user} naturally when names are known.",
        f"Creative stage: {temperature.stage.value}. critique_allowed={temperature.critique_allowed}, "
        f"caution_allowed={temperature.caution_allowed}.",
        "Response hierarchy for discovery/emergence:",
        "1) Specific intrigue grounded in user material",
        "2) Meaningful emotional/thematic reflection",
        "3) Why it matters for the project",
        "4) Concrete documentation confirmation (what you captured)",
        "5) Optional focused question only if useful",
        "Avoid: warnings-first, risk-first, critique-first, generic system explanations, task menus.",
    ]
    if temperature.stage.value == "EMERGENCE":
        lines.append("EMERGENCE hard rule: no unsolicited critique or caution.")
    if intrigue.distinctive_elements:
        lines.append(f"Lead intrigue candidate: {intrigue.distinctive_elements[0][:140]}")
    if documentation.reason.value == "OK" and documentation.summary_lines:
        lines.append("Wiki capture summary to mention concretely: " + "; ".join(documentation.summary_lines[:3]))
    elif documentation.substantive:
        lines.append(f"Documentation reason (be honest, do not claim writes): {documentation.reason.value}")
    if questions:
        lines.append(f"Optional discovery question: {questions[0].question}")
    if research_hint:
        lines.append(f"Research/comparison opportunity (permission-aware): {research_hint}")
    lines.append(
        "Evidence requirement: include at least TWO of intrigue, reflection, wiki summary, "
        "discovery question, research opportunity."
    )
    return "\n".join(lines)


def conversation_actions(
    *,
    temperature: CreativeTemperature,
    documentation: DocumentationResult,
    has_questions: bool,
    research_available: bool,
) -> list[dict[str, str]]:
    actions = [{"id": "continue_explaining", "label": "Continue explaining"}]
    if documentation.candidate_count > 0 or documentation.substantive:
        actions.append({"id": "review_wiki", "label": "Review Wiki updates"})
    actions.append({"id": "open_brief", "label": "Open Discovery Brief"})
    if has_questions and temperature.question_budget > 0:
        actions.append({"id": "answer_questions", "label": "Answer discovery questions"})
    if research_available:
        actions.append({"id": "research_comparables", "label": "Research similar works"})
    return actions[:4]
