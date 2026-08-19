"""Character Reference System (CRS) service — platform-level resolver.

Builds on the existing Character Identity service to provide a first-class
CRS that resolves @Character and #ERS references across the platform.

Product Law:
  THE CRS DEFINES WHAT THE CHARACTER LOOKS LIKE.
  THE JSON DEFINES WHAT ADEPT UI KNOWS ABOUT THAT VISUAL CANON.
  @KORRI RESOLVES BOTH.
  CO-DIRECTOR USES THE CANON. IT DOES NOT REINVENT THE CHARACTER FROM PROSE.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from .crs_schema import (
    CRSStatus,
    CharacterCanon,
    CharacterReferenceSummary,
    CharacterRenderDomain,
    ConfidenceMap,
    FidelityReport,
    FidelityVerdict,
    GenerationConditioningPacket,
    IdentityLock,
    IdentityLocks,
    NegativeIdentityRule,
    ReferenceRole,
    VisualReference,
    VisualReferences,
)
from .models import CharacterProfileRow, CharacterReferenceAssetRow, CharacterTraitRow

CRS_CANON_TRAIT_KEY = "crs_canon"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_persisted_crs(db: Session, character_id: str) -> dict[str, Any]:
    row = (
        db.query(CharacterTraitRow)
        .filter(
            CharacterTraitRow.character_profile_id == character_id,
            CharacterTraitRow.key == CRS_CANON_TRAIT_KEY,
        )
        .order_by(CharacterTraitRow.id.desc())
        .first()
    )
    if not row or not row.value:
        return {}
    try:
        data = json.loads(row.value)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def persist_crs_in_session(
    db: Session,
    profile: CharacterProfileRow,
    *,
    asset_id: str,
) -> dict[str, Any]:
    """Write persisted CRS JSON without committing (caller owns the transaction)."""
    existing = load_persisted_crs(db, profile.id)
    revision = int(existing.get("crs_revision") or 0) + 1
    payload = {
        "schema_version": 1,
        "character_id": profile.id,
        "name": profile.name,
        "tag": f"@{profile.name}",
        "crs_revision": revision,
        "approved_sheet_asset_id": asset_id,
        "approved_sheet_revision": revision,
        "approved_at": _now(),
        "production_ready": True,
    }
    for row in (
        db.query(CharacterTraitRow)
        .filter(
            CharacterTraitRow.character_profile_id == profile.id,
            CharacterTraitRow.key == CRS_CANON_TRAIT_KEY,
        )
        .all()
    ):
        db.delete(row)
    db.add(
        CharacterTraitRow(
            id=str(uuid.uuid4()),
            character_profile_id=profile.id,
            character_version_id=profile.active_version_id,
            category="crs",
            key=CRS_CANON_TRAIT_KEY,
            value=json.dumps(payload, ensure_ascii=False),
            importance="canonical",
            canonical=True,
            provenance="PROPOSED_BY_CHARACTER_CREATOR",
        )
    )
    return payload


def get_crs_summary(
    db: Session,
    project_id: str,
    character_id: str,
) -> CharacterReferenceSummary | None:
    """Get a compact CRS summary for a character.
    
    Law 19: Compact summary for Co-Director, not the entire canon.
    """
    profile = db.get(CharacterProfileRow, character_id)
    if not profile or profile.project_id != project_id:
        return None

    persisted = load_persisted_crs(db, character_id)
    
    refs = (
        db.query(CharacterReferenceAssetRow)
        .filter(CharacterReferenceAssetRow.character_profile_id == character_id)
        .all()
    )
    
    approved_refs = [r for r in refs if r.approval_status == "approved"]
    ref_count = len(refs)
    has_approved = len(approved_refs) > 0 or bool(persisted.get("approved_sheet_asset_id"))
    
    if ref_count == 0 and not persisted:
        coverage = "none"
    elif ref_count <= 1:
        coverage = "single"
    else:
        coverage = "multi_view"
    
    revision = int(persisted.get("crs_revision") or 0)
    approved_asset = persisted.get("approved_sheet_asset_id") or (
        approved_refs[0].asset_id if approved_refs else None
    )

    crs_status = CRSStatus()
    if has_approved:
        crs_status.status = "approved"
        crs_status.crs_revision = revision
        crs_status.reference_coverage = coverage
        crs_status.visual_canon_ready = True
        crs_status.confidence_summary = (
            "Multi-view reference established" if coverage == "multi_view"
            else "Single reference established"
        )
    elif ref_count > 0:
        crs_status.status = "draft"
        crs_status.crs_revision = revision
        crs_status.reference_coverage = coverage
        crs_status.confidence_summary = "References pending approval"
    
    render_domain = CharacterRenderDomain()
    if profile.visual_style:
        style_lower = profile.visual_style.lower()
        if "anime" in style_lower or "illustration" in style_lower:
            render_domain.character_style = "cinematic_anime"
        elif "photo" in style_lower or "realistic" in style_lower:
            render_domain.character_style = "cinematic_photoreal"
    
    return CharacterReferenceSummary(
        character_id=character_id,
        name=profile.name,
        tag=f"@{profile.name}",
        crs_revision=revision,
        canon_status=crs_status,
        reference_coverage=coverage,
        render_domain=render_domain,
        has_approved_reference=has_approved,
        approved_reference_asset_id=approved_asset,
    )


def get_character_canon(
    db: Session,
    project_id: str,
    character_id: str,
) -> CharacterCanon | None:
    """Get the full structured Character Canon for a character.
    
    This is the JSON that @Character resolves to.
    It tells Adept UI what is known about the visual identity.
    """
    from .service import get_profile, to_out
    
    try:
        profile_out = get_profile(db, project_id, character_id)
    except Exception:
        return None
    
    profile = profile_out.model_dump()
    skin = profile.get("skin") or {}
    hair = profile.get("hair") or {}
    continuity = profile.get("continuity") or {}
    motion = profile.get("motion") or {}
    
    # Build canon
    canon = CharacterCanon(
        name=profile.get("name", ""),
        tag=f"@{profile.get('name', '')}",
        species_or_type=profile.get("species_or_type", "human"),
        skin=skin,
        hair=hair,
        body_proportions={
            "height": profile.get("height_description", ""),
            "body_type": profile.get("body_type", ""),
        },
    )
    
    # Render domain
    style = (profile.get("visual_style") or "").lower()
    if "anime" in style or "illustration" in style:
        canon.render_domain.character_style = "cinematic_anime"
    elif "photo" in style or "realistic" in style:
        canon.render_domain.character_style = "cinematic_photoreal"
    
    # Identity locks from continuity
    locked_features = continuity.get("locked_features") or []
    forbid_invention = continuity.get("forbid_invention") or []
    for feat in locked_features:
        canon.identity_locks.locked.append(
            IdentityLock(trait=feat, category="immutable")
        )
    for rule in forbid_invention:
        canon.negative_rules.append(
            NegativeIdentityRule(rule=rule, category="invention")
        )
    
    # References
    refs = (
        db.query(CharacterReferenceAssetRow)
        .filter(CharacterReferenceAssetRow.character_profile_id == character_id)
        .all()
    )
    for ref in refs:
        role = _map_reference_role(ref.reference_role or "")
        visual_ref = VisualReference(
            asset_id=ref.asset_id,
            role=role,
            notes=ref.notes or "",
        )
        canon.identity_locks.flexible.append(role) if role == "expression_sheet" else None
    
    return canon


def _map_reference_role(role: str) -> ReferenceRole:
    """Map existing reference roles to CRS roles."""
    mapping = {
        "hero_identity": "primary_identity",
        "reference_image": "primary_identity",
        "full_body_front": "full_body_front",
        "full_body_side_left": "full_body_side",
        "full_body_side_right": "full_body_side",
        "full_body_back": "full_body_rear",
        "closeup_front": "portrait",
        "neutral_portrait": "portrait",
        "expression_sheet": "expression_sheet",
        "turnaround_sheet": "turnaround_sheet",
        "wardrobe_reference": "wardrobe",
    }
    return mapping.get(role, "primary_identity")  # type: ignore[return-value]


def estimate_crs_revision(profile: CharacterProfileRow) -> int:
    """Estimate the CRS revision from profile versioning."""
    if profile.active_version_id:
        try:
            import uuid
            return int(uuid.UUID(profile.active_version_id).version) if profile.active_version_id else 0
        except Exception:
            return 1
    return 0


def build_conditioning_packet(
    db: Session,
    project_id: str,
    character_id: str,
    *,
    prompt: str = "",
    generator: str = "",
    ers_id: str = "",
    aspect_ratio: str = "16:9",
) -> GenerationConditioningPacket | None:
    """Build a shared GenerationConditioningPacket from CRS.
    
    Combines CRS + approved references + identity locks + render domain
    into a single packet consumable by any generator adapter.
    """
    from datetime import datetime, timezone
    
    summary = get_crs_summary(db, project_id, character_id)
    if not summary:
        return None
    
    canon = get_character_canon(db, project_id, character_id)
    
    # Collect approved reference assets
    all_refs = []
    selected = []
    
    try:
        from .models import CharacterReferenceAssetRow
        refs = (
            db.query(CharacterReferenceAssetRow)
            .filter(CharacterReferenceAssetRow.character_profile_id == character_id)
            .all()
        )
        approved = [r for r in refs if r.approval_status == "approved" or r.canonical]
        candidates = approved if approved else refs
        
        for ref in candidates:
            if ref.asset_id:
                all_refs.append(ref.asset_id)
        
        # Select best reference: hero_identity preferred
        if summary.approved_reference_asset_id:
            selected.append(summary.approved_reference_asset_id)
        elif all_refs:
            selected.append(all_refs[0])
    except Exception:
        pass
    
    # Identity locks
    locks = []
    neg_rules = []
    if canon:
        for lock in canon.identity_locks.locked:
            locks.append(lock.trait)
        for rule in canon.negative_rules:
            neg_rules.append(rule.rule)
    
    now = datetime.now(timezone.utc).isoformat()
    
    return GenerationConditioningPacket(
        character_id=character_id,
        character_name=summary.name,
        character_tag=summary.tag,
        crs_revision=summary.crs_revision,
        render_domain=summary.render_domain,
        identity_locks=locks,
        negative_rules=neg_rules,
        selected_reference_assets=selected,
        all_reference_assets=all_refs,
        ers_id=ers_id,
        prompt=prompt,
        generator=generator,
        aspect_ratio=aspect_ratio,
        generated_at=now,
    )


def resolve_character_for_generation(
    db: Session,
    project_id: str,
    character_name: str,
) -> dict[str, Any] | None:
    """Resolve a character name for generation.
    
    Combines resolve_character_by_name + resolve_approved_reference + CRS summary.
    Returns a dict suitable for inclusion in generation context.
    """
    try:
        from .service import resolve_character_by_name, resolve_approved_reference
        
        profile = resolve_character_by_name(db, project_id, character_name)
        if not profile:
            return None
        
        char_id = str(profile.id)
        approved_asset_id = resolve_approved_reference(db, char_id)
        summary = get_crs_summary(db, project_id, char_id)
        
        result: dict[str, Any] = {
            "character_id": char_id,
            "name": profile.name,
            "tag": f"@{profile.name}",
            "approved_casting_asset_id": approved_asset_id or "",
            "crs_revision": summary.crs_revision if summary else 0,
            "has_approved_reference": bool(approved_asset_id),
        }
        
        if summary:
            result["render_domain"] = summary.render_domain.model_dump() if summary.render_domain else {}
            result["reference_coverage"] = summary.reference_coverage
            result["visual_canon_ready"] = summary.canon_status.visual_canon_ready if summary.canon_status else False
        
        return result
    except Exception:
        return None
