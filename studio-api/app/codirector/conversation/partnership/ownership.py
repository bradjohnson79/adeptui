"""Collaboration ownership resolution — role ≠ authorship."""

from __future__ import annotations

from ..relationship.schemas import CoDirectorRelationshipProfile
from .schemas import CollaborationOwnership, ProductionCollaborationProfile

_ASSISTANCE_TO_OWNERSHIP: dict[str, CollaborationOwnership] = {
    "advise": CollaborationOwnership.USER_LEADS,
    "USER_LEADS": CollaborationOwnership.USER_LEADS,
    "create_with_me": CollaborationOwnership.CO_CREATE,
    "CO_CREATE": CollaborationOwnership.CO_CREATE,
    "first_drafts": CollaborationOwnership.CODIRECTOR_LEADS,
    "CODIRECTOR_LEADS": CollaborationOwnership.CODIRECTOR_LEADS,
    "take_the_lead": CollaborationOwnership.CODIRECTOR_EXECUTES,
    "CODIRECTOR_EXECUTES": CollaborationOwnership.CODIRECTOR_EXECUTES,
    "ask_each_stage": CollaborationOwnership.ASK_EACH_TIME,
    "ASK_EACH_TIME": CollaborationOwnership.ASK_EACH_TIME,
}

_STAGE_FIELD: dict[str, str] = {
    "concept_development": "concept_development",
    "story_template": "concept_development",
    "discovery": "discovery_brief",
    "discovery_brief": "discovery_brief",
    "research": "research",
    "treatment": "treatment",
    "outline": "story_outline",
    "story_outline": "story_outline",
    "character": "character_development",
    "character_development": "character_development",
    "world": "worldbuilding",
    "worldbuilding": "worldbuilding",
    "screenplay": "screenplay",
    "script": "screenplay",
    "revision": "revision",
    "visual": "visual_development",
    "visual_development": "visual_development",
    "production_plan": "production_planning",
    "production_planning": "production_planning",
    "marketing": "marketing",
    "marketing_brief": "marketing",
    "pitch": "pitch_package",
    "pitch_summary": "pitch_package",
    "pitch_package": "pitch_package",
    "festival": "festival_submission",
    "release": "release_strategy",
}


def ownership_from_assistance_choice(choice: str) -> CollaborationOwnership:
    key = (choice or "").strip()
    return _ASSISTANCE_TO_OWNERSHIP.get(key, CollaborationOwnership.CO_CREATE)


def apply_default_ownership(
    collab: ProductionCollaborationProfile,
    default: CollaborationOwnership,
) -> ProductionCollaborationProfile:
    """Seed stage fields from a default assistance depth (onboarding / preference change)."""
    collab.default_ownership = default
    for field in (
        "concept_development",
        "discovery_brief",
        "treatment",
        "story_outline",
        "character_development",
        "worldbuilding",
        "screenplay",
        "revision",
        "visual_development",
        "production_planning",
        "marketing",
        "pitch_package",
        "festival_submission",
        "release_strategy",
        "research",
    ):
        setattr(collab, field, default)
    return collab


def sync_from_relationship(
    collab: ProductionCollaborationProfile,
    relationship: CoDirectorRelationshipProfile,
) -> ProductionCollaborationProfile:
    default = getattr(relationship, "default_ownership", None)
    if isinstance(default, CollaborationOwnership):
        collab.default_ownership = default
    elif isinstance(default, str) and default in CollaborationOwnership.__members__:
        collab.default_ownership = CollaborationOwnership(default)
        apply_default_ownership(collab, collab.default_ownership)
    return collab


def resolve_ownership(
    collab: ProductionCollaborationProfile,
    artifact_or_stage: str,
) -> CollaborationOwnership:
    field = _STAGE_FIELD.get((artifact_or_stage or "").lower().strip(), "")
    if field and hasattr(collab, field):
        return getattr(collab, field)
    return collab.default_ownership or CollaborationOwnership.ASK_EACH_TIME


def may_create_full_draft(ownership: CollaborationOwnership, *, user_authorized: bool) -> bool:
    if ownership == CollaborationOwnership.USER_LEADS:
        return False
    if ownership == CollaborationOwnership.ASK_EACH_TIME:
        return user_authorized
    if ownership in {CollaborationOwnership.CODIRECTOR_LEADS, CollaborationOwnership.CODIRECTOR_EXECUTES}:
        return True
    if ownership == CollaborationOwnership.CO_CREATE:
        return user_authorized
    return False


def may_show_preview(ownership: CollaborationOwnership) -> bool:
    # Preview is lightweight and always allowed except when user insists on leading with zero CD authorship —
    # still allow preview as suggestion, not full draft.
    return True


def ownership_guidance(ownership: CollaborationOwnership, artifact_type: str) -> str:
    label = artifact_type.replace("_", " ")
    if ownership == CollaborationOwnership.USER_LEADS:
        return (
            f"Ownership: USER_LEADS for {label}. Advise, organize, and document. "
            "Do not write the full artifact unless the user asks. A short preview hook is OK."
        )
    if ownership == CollaborationOwnership.CO_CREATE:
        return f"Ownership: CO_CREATE for {label}. Draft sections collaboratively after a useful preview."
    if ownership == CollaborationOwnership.CODIRECTOR_LEADS:
        return (
            f"Ownership: CODIRECTOR_LEADS for {label}. After a useful preview and permission, "
            "prepare a strong first draft with assumptions labeled. Never treat as approved."
        )
    if ownership == CollaborationOwnership.CODIRECTOR_EXECUTES:
        return (
            f"Ownership: CODIRECTOR_EXECUTES for {label}. Direction confirmed — execute production artifacts. "
            "Do not rewrite LOCKED deliverables."
        )
    return f"Ownership: ASK_EACH_TIME for {label}. Show a useful preview, then ask before building the full draft."
