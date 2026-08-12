"""Mode-specific context assembly for companion / advisory turns."""

from __future__ import annotations

from typing import Any

from .schemas import (
    CompanionProjectBundle,
    CreativeAdvisoryPlan,
    CreativeBlockAssessment,
    CreativeSupportAssessment,
    StoryDeviationAssessment,
)


def assemble_companion_context(
    *,
    mode: str,
    project_title: str,
    active_goal: str | None,
    support: CreativeSupportAssessment,
    advisory: CreativeAdvisoryPlan,
    deviation: StoryDeviationAssessment | None,
    block: CreativeBlockAssessment | None,
    bundle: CompanionProjectBundle,
    recent_messages: list[dict[str, Any]] | None = None,
    specialist_findings: list[str] | None = None,
) -> str:
    lines = [
        "=== Companion context (ranked) ===",
        f"Project: {project_title}",
        f"Assembler mode: {mode}",
        f"Active goal: {active_goal or support.likely_user_goal}",
        f"Working state (internal): {support.working_state.value}",
        f"Support need: {support.support_needed.value}",
        f"Advisory decision: {bundle.advisoryDecisionState.value}",
    ]
    if support.evidence_spans:
        lines.append("Support evidence: " + " | ".join(support.evidence_spans[:4]))
    if support.suggested_response_strategy:
        lines.append("Strategy: " + "; ".join(support.suggested_response_strategy[:4]))
    if support.should_avoid:
        lines.append("Avoid: " + "; ".join(support.should_avoid[:5]))

    # Principles — highest importance first, capped
    principles = sorted(
        [p for p in bundle.principles if p.status.value not in {"SUPERSEDED", "REJECTED"}],
        key=lambda p: (0 if p.importance.value == "FOUNDATIONAL" else 1 if p.importance.value == "MAJOR" else 2, -p.confidence),
    )[:6]
    if principles:
        lines.append("Relevant story principles:")
        for p in principles:
            conf = "confirmed" if p.creator_confirmed else "inferred"
            lines.append(f"- [{p.status.value}/{p.importance.value}/{conf}] {p.statement}")

    strengths = [s for s in bundle.creatorStrengths if s.status != "rejected"][:3]
    if strengths and support.support_needed.value in {"REFRAME", "ENCOURAGE", "UNBLOCK", "CELEBRATE", "CRITIQUE"}:
        lines.append("Demonstrated creator/project strengths (evidence-backed):")
        for s in strengths:
            lines.append(f"- {s.statement}")

    rps = [r for r in bundle.returnPoints if r.status == "active"][:2]
    if rps and support.support_needed.value in {"UNBLOCK", "REFRAME", "ADVISE"}:
        lines.append("Creative return points:")
        for r in rps:
            lines.append(f"- {r.description} — why: {r.why_it_worked}")

    lens = bundle.creativeLens
    if lens.emotional_tones or lens.artistic_priorities:
        lines.append(
            "Creative lens: "
            + ", ".join((lens.dominant_genres or [])[:2] + (lens.emotional_tones or [])[:2] + (lens.artistic_priorities or [])[:2])
        )

    if advisory.should_advise:
        lines.append(
            "Advisory plan: "
            f"strength={advisory.advisory_strength.value}; "
            f"confirm={advisory.request_confirmation}; "
            f"variant={advisory.preserve_as_variant}; "
            f"canon_write={advisory.canon_write_allowed}; "
            f"no_relitigation={advisory.no_relitigation_after_confirmation}"
        )
    if deviation and deviation.triggered:
        lines.append(f"Proposed change: {deviation.proposed_change}")
        lines.append(f"Problem source: {deviation.problem_source.value}")
        lines.append(f"Deviation type: {deviation.deviation_type.value}")
        if deviation.likely_gains:
            lines.append("Gains: " + "; ".join(deviation.likely_gains[:3]))
        if deviation.likely_losses:
            lines.append("Losses: " + "; ".join(deviation.likely_losses[:3]))
        if deviation.alternative_adjustments:
            lines.append("Alternatives: " + "; ".join(deviation.alternative_adjustments[:3]))
        lines.append(f"Recommendation: {deviation.recommendation}")

    if block:
        lines.append(f"Block type: {block.block_type.value}")
        lines.append(f"First step: {block.recommended_first_step}")

    if specialist_findings:
        lines.append("Specialist findings (subordinate evidence):")
        for item in specialist_findings[:6]:
            lines.append(f"- {item}")

    msgs = recent_messages or []
    if msgs:
        lines.append("Recent messages:")
        for m in msgs[-5:]:
            role = str(m.get("role") or "user")
            content = str(m.get("content") or "").strip()
            if len(content) > 200:
                content = content[:197] + "..."
            lines.append(f"- {role}: {content}")

    lines.append("Do NOT dump full wiki/bible. Do NOT invent canon. Do NOT use generic praise.")
    if advisory.no_relitigation_after_confirmation and bundle.advisoryDecisionState.value in {
        "USER_CONFIRMED_CHANGE",
        "USER_CONFIRMED_KEEP_CURRENT",
        "COLLABORATING_ON_DIRECTION",
        "CANON_UPDATED",
    }:
        lines.append("Creator decision confirmed — support fully; do not re-argue.")
    return "\n".join(lines)


def assembler_mode_for(support: CreativeSupportAssessment, advisory: CreativeAdvisoryPlan, cognitive_mode: str) -> str:
    need = support.support_needed.value
    if advisory.should_advise and advisory.compare_gains_and_losses:
        return "ADVISORY"
    if need == "CRITIQUE":
        return "CRITIQUE"
    if need == "UNBLOCK":
        return "WRITERS_BLOCK"
    if need == "CELEBRATE":
        return "CELEBRATION"
    if need == "EXECUTE":
        return "PRODUCTION_EXECUTION"
    if need in {"ENCOURAGE", "REFRAME", "SIMPLIFY", "INSPIRE"}:
        return "CREATIVE_SUPPORT"
    if cognitive_mode.upper() == "LISTENING":
        return "LISTENING"
    if cognitive_mode.upper() == "PLANNING":
        return "PLANNING"
    return "CREATIVE_SUPPORT"
