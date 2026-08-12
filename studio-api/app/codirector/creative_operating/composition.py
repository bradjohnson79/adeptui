"""Creator-facing prompt blocks — natural Co-Director voice, no engineer jargon."""

from __future__ import annotations

from .contracts import (
    INITIATIVE_LABELS,
    CoDirectorCreativeDecision,
    CreativeOperatingBundle,
)
from .canon_safety import separation_prompt_block
from .disagreement import disagreement_prompt_block

COACHING_DOCTRINE = """
Co-Director coaching doctrine (internal):
The creator wants a creative partner who stays with the project, sees what makes it powerful,
organizes everything important, notices what is missing, and helps the work advance naturally.
Do not flatter generically. Demonstrate interest through specific observations and explain why they matter.
Do not interrupt creative flow with premature criticism. During discovery, protect momentum.
Never dump specialist output into chat. Speak as one coherent Co-Director voice.
Never promote interpretations or possibilities to confirmed canon without creator approval.
Stay one meaningful development unit ahead — not ten.
""".strip()


def creative_operating_prompt_block(
    decision: CoDirectorCreativeDecision | None,
    bundle: CreativeOperatingBundle | None = None,
    *,
    lifecycle_stage: str | None = None,
    specialists_for_stage: list[str] | None = None,
) -> str:
    if decision is None:
        return ""
    lines = [
        "Creative operating decision (compose from this; never expose internals):",
        f"- Need: {decision.userNeed}",
        f"- Stage: {decision.creativeStage}",
        f"- Initiative: {INITIATIVE_LABELS.get(decision.initiativeLevel, decision.initiativeLevel)}",
        f"- Posture: {decision.responsePosture}",
        f"- Format: {decision.projectFormat}",
        f"- Listening-only: {'yes' if decision.listeningOnly else 'no'}",
        f"- Question budget this turn: {decision.questionBudget}",
    ]
    if lifecycle_stage:
        lines.append(f"- Production stage (where we are): {lifecycle_stage}")
        lines.append(
            "- Always know: what is ready, what is blocked, and what comes next. "
            "Never rush generation before the creative foundation exists."
        )
    if specialists_for_stage:
        lines.append(
            "- Behind-the-scenes specialists available now (never name them unless useful): "
            + ", ".join(specialists_for_stage[:6])
        )
    if decision.strongestCreativeInsights:
        lines.append("- Specific observations to weave in: " + "; ".join(decision.strongestCreativeInsights[:2]))
    if decision.initiativeLevel == "QUIET_PARTNER" or decision.listeningOnly:
        lines.append(
            "- Quiet / listening: acknowledge specific material; ask zero questions unless clarification "
            "is essential; do not push treatments, episode plans, or production checklists."
        )
    elif decision.initiativeLevel == "COLLABORATIVE_PARTNER":
        lines.append(
            "- Collaborative: stay conversational; at natural pauses offer at most one or two useful options; "
            "do not over-direct."
        )
    elif decision.initiativeLevel == "PROACTIVE_PRODUCER":
        lines.append(
            "- Proactive Producer: surface one strong missing element and why it matters now; "
            "stay one meaningful step ahead — not a production checklist or distant overplanning."
        )
    elif decision.initiativeLevel == "HANDS_ON_CO_CREATOR":
        lines.append(
            "- Hands-On Co-Creator: concrete previews/drafts are welcome as proposed or exploratory; "
            "ask authorship or ownership before major writing; never take control of the creator's work."
        )
    if decision.surfacedQuestion and decision.questionBudget > 0:
        lines.append(f"- At most one question (if natural): {decision.surfacedQuestion}")
    elif decision.listeningOnly:
        lines.append("- Do not ask a question; invite continuation softly.")
    if decision.forwardSuggestion and not decision.listeningOnly:
        lines.append(
            f"- Optional exploratory next step (not canon): {decision.forwardSuggestion.suggestion}"
        )
        lines.append(f"  Why it fits: {decision.forwardSuggestion.whyItFits}")
    if decision.creativeOpening and not decision.listeningOnly:
        lines.append(
            f"- Strongest opening: {decision.creativeOpening.missingDimension} "
            f"({decision.creativeOpening.whyItMatters})"
        )
    sep = separation_prompt_block(decision.importantNewKnowledge)
    if sep:
        lines.append(sep)
    dis = disagreement_prompt_block(decision.disagreement or (bundle.lastDisagreement if bundle else None))
    if dis:
        lines.append(dis)
    lines.append(
        "Reply shape when appropriate: warm acknowledgement → one or two specific creative observations "
        "→ meaningful interpretation → invitation to continue → optional soft next steps. "
        "Vary the shape; do not use a rigid template every turn. "
        "Never use empty praise such as 'unique and compelling' or 'great idea' without a project-specific observation."
    )
    return "\n".join(lines)


def soft_next_step_invitations(
    decision: CoDirectorCreativeDecision | None,
    *,
    lifecycle_next_steps: list[str] | None = None,
) -> list[str]:
    if decision is None or decision.listeningOnly:
        return ["Keep telling the story"]
    if lifecycle_next_steps:
        # Stage-aware chips take priority when lifecycle is available
        out = list(lifecycle_next_steps[:4])
        if "Keep telling the story" not in out and decision.userNeed == "LISTEN":
            out.insert(0, "Keep telling the story")
        return out[:4]
    options = ["Keep telling the story"]
    if decision.userNeed in {"DEVELOPMENT", "ENCOURAGEMENT", "LISTEN"}:
        options.append("Explore the character")
    if decision.projectFormat == "EPISODIC_SERIES":
        options.append("Develop the next installment")
    elif decision.projectFormat in {"FEATURE_FILM", "SHORT_FILM", "ANIMATION"}:
        options.append("Clarify the next sequence")
    elif decision.projectFormat == "DOCUMENTARY":
        options.append("Map the missing perspective")
    elif decision.projectFormat == "GAME":
        options.append("Define the next quest beat")
    else:
        options.append("Shape the next development beat")
    if decision.creativeStage in {"STRUCTURING", "REFINING", "PRODUCING"}:
        options.append("Build a working treatment")
    options.append("Review the Project Bible")
    # Dedup preserve order, max 4
    seen: set[str] = set()
    out: list[str] = []
    for o in options:
        if o in seen:
            continue
        seen.add(o)
        out.append(o)
        if len(out) >= 4:
            break
    return out
