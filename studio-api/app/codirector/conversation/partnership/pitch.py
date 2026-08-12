"""Pitch package creation — preview-first, recipient-aware, never silently approved."""

from __future__ import annotations

from .schemas import (
    ArtifactReadinessAssessment,
    PartnershipProjectBundle,
    PitchPackage,
    PitchType,
    ProjectDestination,
)


def _pitch_type_for_destination(dest: ProjectDestination) -> PitchType:
    return {
        ProjectDestination.YOUTUBE: PitchType.YOUTUBE,
        ProjectDestination.FILM_FESTIVALS: PitchType.FESTIVAL,
        ProjectDestination.PRODUCER_PITCH: PitchType.PRODUCER,
        ProjectDestination.NETWORK_PITCH: PitchType.NETWORK,
        ProjectDestination.STREAMER_PITCH: PitchType.STREAMER,
        ProjectDestination.INVESTOR_PITCH: PitchType.INVESTOR,
        ProjectDestination.CROWDFUNDING: PitchType.CROWDFUNDING,
    }.get(dest, PitchType.ONE_PARAGRAPH)


def build_pitch_package(
    bundle: PartnershipProjectBundle,
    *,
    project_id: str,
    user_message: str,
    assessment: ArtifactReadinessAssessment | None = None,
    pitch_type: PitchType | None = None,
) -> PitchPackage:
    vision = bundle.vision
    ptype = pitch_type or _pitch_type_for_destination(vision.primary_destination)
    hook = (assessment.preview_hook if assessment else "") or (user_message or "").strip()[:280]
    # Logline: compress hook
    logline = hook
    if len(logline) > 200:
        logline = logline[:197] + "…"

    audience = ", ".join(vision.intended_audience[:3]) if vision.intended_audience else "to be refined"
    diff = []
    if assessment and assessment.supporting_facts:
        diff.append("Grounded in: " + ", ".join(assessment.supporting_facts[:4]))
    diff.append("Distinctive hook drawn from the creator's premise — not a generic genre pitch.")

    short = (
        f"{logline}\n\n"
        f"Audience: {audience}. "
        f"Format/scale: {vision.project_scale}. "
        f"Destination focus: {vision.primary_destination.value}."
    )
    if ptype == PitchType.YOUTUBE:
        short += " Emphasize episodic hooks, retention, and channel-fit rather than festival exclusivity."
    elif ptype == PitchType.FESTIVAL:
        short += " Emphasize cinematic ambition, runtime discipline, and festival positioning."
    elif ptype in {PitchType.PRODUCER, PitchType.NETWORK, PitchType.STREAMER}:
        short += " Emphasize series/feature engine, audience case, and production feasibility."

    pkg = PitchPackage(
        project_id=project_id,
        pitch_type=ptype,
        recipient_type=ptype.value.lower(),
        objective="Test whether the project's strongest promise communicates clearly.",
        logline=logline,
        short_pitch=short,
        audience_case=audience,
        comparable_works=[],
        differentiation=diff,
        production_readiness=["Early development — draft pitch for review only"],
        requested_outcome="Feedback on heart, mystery, clarity, scale, or commercial focus",
        assumptions=[
            "Draft only — not approved.",
            "Comparables omitted until permissioned research.",
        ],
        status="DRAFT",
        why_now=assessment.why_now if assessment else "Enough shape to test the promise.",
    )
    approved = [p for p in bundle.pitches if p.status == "APPROVED"]
    others = [p for p in bundle.pitches if p.status != "APPROVED"]
    bundle.pitches = approved + others[-4:] + [pkg]
    return pkg


def revise_pitch(bundle: PartnershipProjectBundle, pitch_id: str, *, feedback: str) -> PitchPackage | None:
    for p in bundle.pitches:
        if p.id != pitch_id:
            continue
        note = (feedback or "").strip()
        if note:
            p.short_pitch = (p.short_pitch + f"\n\nRevision direction: {note}").strip()
            p.assumptions.append(f"Revised per creator: {note[:120]}")
        p.status = "REVIEW"
        return p
    return None


def approve_pitch(bundle: PartnershipProjectBundle, pitch_id: str) -> PitchPackage | None:
    for p in bundle.pitches:
        if p.id != pitch_id:
            continue
        p.status = "APPROVED"
        return p
    return None
