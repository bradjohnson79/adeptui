"""Partnership composition guidance — preview + whyNow required for major offers."""

from __future__ import annotations

from .ownership import ownership_guidance
from .schemas import (
    ArtifactReadinessAssessment,
    ArtifactRecommendedAction,
    ContextualQuestionCandidate,
    CreativeDeliverable,
    MarketingStrategyProfile,
    PitchPackage,
    ProjectVisionProfile,
)
from .vision import vision_guidance
from .marketing import marketing_guidance


def partnership_composition_guidance(
    *,
    readiness: list[ArtifactReadinessAssessment],
    preview: CreativeDeliverable | None,
    vision: ProjectVisionProfile,
    pitch: PitchPackage | None,
    marketing: MarketingStrategyProfile,
    questions: list[ContextualQuestionCandidate],
    personal_destination: bool,
) -> str:
    lines = [
        "Hands-on partnership rules:",
        "- When enough info exists, show a useful PREVIEW (hook/snippet) before asking to build a large artifact.",
        "- Always explain whyNow in plain language.",
        "- Never treat drafts or previews as approved.",
        "- Role ≠ authorship; respect ownership modes.",
        "- No premature pitch/marketing during fragile emergence.",
    ]
    for a in readiness:
        if a.recommended_action == ArtifactRecommendedAction.WAIT:
            lines.append(f"Artifact {a.artifact_type}: WAIT — {a.why_now}")
            continue
        lines.append(ownership_guidance(a.ownership_mode, a.artifact_type))
        if a.why_now:
            lines.append(f"whyNow ({a.artifact_type}): {a.why_now}")
        if a.preview_hook:
            lines.append(f"Preview hook to surface: {a.preview_hook}")
            lines.append(
                "Offer actions after preview: Short pitch / Story template / Keep developing "
                "(or Create draft / Build together / Keep listening)."
            )
        if a.recommended_action == ArtifactRecommendedAction.SHOW_PREVIEW:
            lines.append("Do NOT only say 'I can create X' — show the preview first.")
    if preview and preview.preview_content:
        lines.append(f"Active preview ({preview.type}, status=PREVIEW): {preview.preview_content}")
        lines.append(f"Preview whyNow: {preview.why_now}")
    lines.append(vision_guidance(vision))
    if pitch:
        lines.append(f"Pitch draft status={pitch.status}: logline={pitch.logline[:160]}")
        lines.append("Ask whether it captures the project; offer revise/expand/reject — never silent approve.")
    lines.append(marketing_guidance(marketing, personal_destination))
    if questions:
        lines.append(f"Timed question (if not interrupting flow): {questions[0].question}")
    return "\n".join(lines)


def partnership_conversation_actions(
    *,
    readiness: list[ArtifactReadinessAssessment],
    has_preview: bool,
    has_draft: bool,
    has_pitch: bool,
    research_available: bool,
) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = [{"id": "continue_explaining", "label": "Continue explaining"}]
    ready_types = {a.artifact_type for a in readiness if a.recommended_action.value != "WAIT"}
    if "story_template" in ready_types or has_preview:
        actions.append({"id": "create_story_template", "label": "Create story template"})
    if "pitch_summary" in ready_types or has_pitch:
        actions.append({"id": "prepare_short_pitch", "label": "Prepare short pitch"})
    if has_draft:
        actions.append({"id": "review_draft", "label": "Review draft"})
    if has_preview and not has_draft:
        actions.append({"id": "expand_preview", "label": "Expand preview into draft"})
    if research_available:
        actions.append({"id": "research_comparables", "label": "Research similar works"})
    # keep 2–4 + continue
    out = [actions[0]]
    for a in actions[1:]:
        if len(out) >= 4:
            break
        out.append(a)
    return out


def format_preview_reply_enrichment(preview: CreativeDeliverable, assessment: ArtifactReadinessAssessment | None) -> str:
    why = preview.why_now or (assessment.why_now if assessment else "")
    hook = preview.preview_content or ""
    if not hook:
        return ""
    return (
        f" Possible central hook:\n{hook}\n\n"
        f"{why} I can turn this into a short pitch, a story template, or we can keep developing."
    )
