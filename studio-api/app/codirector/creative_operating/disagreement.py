"""Professional disagreement synthesis — specialists never speak to creator."""

from __future__ import annotations

from .contracts import ProfessionalDisagreement, ProfessionalSpecialistResult


def synthesize_disagreement(
    *,
    topic: str,
    specialist_results: list[ProfessionalSpecialistResult] | None = None,
    positions: dict[str, str] | None = None,
    conflict_type: str = "creative",
) -> ProfessionalDisagreement | None:
    """Orchestrator synthesizes one coherent recommendation from department views."""
    pos: dict[str, str] = dict(positions or {})
    evidence: list[str] = []
    if specialist_results:
        for r in specialist_results:
            if r.conflicts:
                pos.setdefault(r.specialistId, "; ".join(r.conflicts[:2]))
            elif r.recommendedAction:
                pos.setdefault(r.specialistId, r.recommendedAction)
            evidence.extend(r.evidenceIds[:3])
    if len(pos) < 2:
        return None

    # Heuristic synthesis — prefer continuity/canon caution + creative value.
    continuity_hit = any(
        k in {"script-supervisor", "continuity-analyst", "project-bible-steward", "bible-manager"}
        for k in pos
    )
    producer_hit = "producer" in pos
    creative_hit = any(k in {"story-editor", "screenwriter", "storyteller", "director"} for k in pos)

    parts: list[str] = []
    if creative_hit:
        parts.append("The creative impulse is strong")
    if producer_hit:
        parts.append("the installment may already be overloaded")
    if continuity_hit:
        parts.append("confirming it now could create a continuity problem")
    if not parts:
        parts.append("Departments see this differently")

    recommendation = (
        ", but ".join(parts[:2])
        + (f", and {parts[2]}" if len(parts) > 2 else "")
        + ". A better path may be to foreshadow now and reveal later — unless you want to decide otherwise."
    )
    # Clean leading artifacts
    recommendation = recommendation[0].upper() + recommendation[1:] if recommendation else recommendation

    return ProfessionalDisagreement(
        topic=topic or "Creative disagreement",
        specialistPositions=pos,
        evidenceIds=evidence[:12],
        conflictType=conflict_type,
        synthesizedRecommendation=recommendation,
        requiresCreatorDecision=True,
    )


def disagreement_prompt_block(d: ProfessionalDisagreement | None) -> str:
    if d is None:
        return ""
    return (
        "Department disagreement (synthesize in one Co-Director voice; never quote specialists by role):\n"
        f"- Topic: {d.topic}\n"
        f"- Recommendation: {d.synthesizedRecommendation}\n"
        f"- Requires creator decision: {'yes' if d.requiresCreatorDecision else 'no'}"
    )
