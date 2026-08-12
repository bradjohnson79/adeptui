"""Creative deliverable lifecycle — PREVIEW never becomes approved silently."""

from __future__ import annotations

from .schemas import (
    ArtifactReadinessAssessment,
    CollaborationOwnership,
    CreativeDeliverable,
    CreativeDeliverableStatus,
    PartnershipProjectBundle,
)


def create_preview_deliverable(
    bundle: PartnershipProjectBundle,
    assessment: ArtifactReadinessAssessment,
    *,
    project_id: str,
) -> CreativeDeliverable:
    title_map = {
        "story_template": "Story template preview",
        "pitch_summary": "Pitch preview",
        "treatment": "Treatment preview",
        "marketing_brief": "Marketing brief preview",
    }
    preview = (assessment.preview_hook or "").strip()
    d = CreativeDeliverable(
        project_id=project_id,
        type=assessment.artifact_type,
        title=title_map.get(assessment.artifact_type, f"{assessment.artifact_type} preview"),
        ownership_mode=assessment.ownership_mode,
        current_author="CO_DIRECTOR",
        status=CreativeDeliverableStatus.PREVIEW,
        content="",  # full content empty until draft
        preview_content=preview,
        why_now=assessment.why_now,
        approval_required=True,
        assumptions=["Preview only — not approved project content."],
    )
    # Replace prior preview of same type
    bundle.deliverables = [
        x
        for x in bundle.deliverables
        if not (x.type == d.type and x.status == CreativeDeliverableStatus.PREVIEW)
    ]
    bundle.deliverables.append(d)
    bundle.last_preview_id = d.id
    return d


def expand_preview_to_draft(
    bundle: PartnershipProjectBundle,
    deliverable_id: str,
    content: str,
    *,
    field_marks: dict[str, str] | None = None,
    assumptions: list[str] | None = None,
) -> CreativeDeliverable | None:
    for d in bundle.deliverables:
        if d.id != deliverable_id:
            continue
        if d.status == CreativeDeliverableStatus.LOCKED:
            return None
        if d.status == CreativeDeliverableStatus.PREVIEW:
            d.status = CreativeDeliverableStatus.DRAFT
        else:
            d.status = CreativeDeliverableStatus.IN_REVIEW
        d.content = content
        d.revision_count += 1
        d.revision_history.append(content[:2000])
        if field_marks:
            d.field_marks = field_marks
        if assumptions:
            d.assumptions = assumptions
        d.approval_required = True
        return d
    return None


def revise_deliverable(
    bundle: PartnershipProjectBundle,
    deliverable_id: str,
    content: str,
) -> CreativeDeliverable | None:
    for d in bundle.deliverables:
        if d.id != deliverable_id:
            continue
        if d.status == CreativeDeliverableStatus.LOCKED:
            return None
        d.content = content
        d.status = CreativeDeliverableStatus.IN_REVIEW
        d.revision_count += 1
        d.revision_history.append(content[:2000])
        return d
    return None


def set_deliverable_status(
    bundle: PartnershipProjectBundle,
    deliverable_id: str,
    status: CreativeDeliverableStatus,
) -> CreativeDeliverable | None:
    for d in bundle.deliverables:
        if d.id != deliverable_id:
            continue
        # PREVIEW cannot jump to APPROVED/LOCKED
        if d.status == CreativeDeliverableStatus.PREVIEW and status in {
            CreativeDeliverableStatus.APPROVED,
            CreativeDeliverableStatus.LOCKED,
        }:
            return None
        d.status = status
        if status == CreativeDeliverableStatus.APPROVED:
            d.approval_required = False
        return d
    return None


def is_locked(bundle: PartnershipProjectBundle, deliverable_type: str) -> bool:
    return any(
        d.type == deliverable_type and d.status == CreativeDeliverableStatus.LOCKED for d in bundle.deliverables
    )


def can_rewrite(bundle: PartnershipProjectBundle, deliverable_type: str) -> bool:
    return not is_locked(bundle, deliverable_type)


def structure_only_for_user_leads(ownership: CollaborationOwnership) -> bool:
    return ownership == CollaborationOwnership.USER_LEADS
