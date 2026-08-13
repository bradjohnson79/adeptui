"""Character Identity service (M3.3)."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .coverage import compute_coverage
from .models import (
    CharacterProfileRow,
    CharacterPropRow,
    CharacterReferenceAssetRow,
    CharacterTraitRow,
    CharacterVersionRow,
    CharacterWardrobeRow,
    VoiceConsentRecordRow,
    VoiceProfileRow,
)
from .roles import ALL_REFERENCE_ROLES
from .schemas import (
    CharacterProfileCreate,
    CharacterProfileOut,
    CharacterProfileUpdate,
    DialogueGenerateRequest,
    PropCreate,
    ReferenceAttach,
    TraitUpsert,
    VoiceConsentCreate,
    VoiceProfileCreate,
    WardrobeCreate,
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z"


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
    return s or f"character-{uuid.uuid4().hex[:8]}"


def _loads(raw: str | None, default: Any) -> Any:
    try:
        return json.loads(raw or "") if raw else default
    except Exception:
        return default


def _dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False)


def _err(code: str, message: str, status: int = 400) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _require_mutable(profile: CharacterProfileRow) -> None:
    if profile.status in ("LOCKED", "ARCHIVED"):
        raise _err("LOCKED_VERSION", "This Character Profile is locked or archived.", 409)
    if profile.approval_status == "approved" and profile.status == "APPROVED":
        # Approved profiles still allow draft revision via new version; block direct silent mutation
        # of core identity fields without creating a revision — callers use create_version.
        pass


def _version_locked(db: Session, version_id: str | None) -> CharacterVersionRow | None:
    if not version_id:
        return None
    row = db.get(CharacterVersionRow, version_id)
    if row and row.status in ("APPROVED", "LOCKED"):
        return row
    return None


def ensure_character_identity_tables() -> None:
    from sqlalchemy import text

    from ..db import Base, engine
    from .models import CHARACTER_IDENTITY_TABLES

    Base.metadata.create_all(bind=engine, tables=CHARACTER_IDENTITY_TABLES)
    # Legacy DBs created before M3.3j may lack trait provenance.
    with engine.connect() as conn:
        rows = conn.execute(text("PRAGMA table_info(character_traits)")).fetchall()
        if rows and not any(r[1] == "provenance" for r in rows):
            conn.execute(
                text(
                    "ALTER TABLE character_traits "
                    "ADD COLUMN provenance VARCHAR(64) NOT NULL DEFAULT 'PROPOSED_BY_CHARACTER_CREATOR'"
                )
            )
            conn.commit()


def _coverage_for(db: Session, profile: CharacterProfileRow):
    refs = (
        db.query(CharacterReferenceAssetRow)
        .filter(CharacterReferenceAssetRow.character_profile_id == profile.id)
        .all()
    )
    roles = [r.reference_role for r in refs]
    wardrobes = (
        db.query(CharacterWardrobeRow)
        .filter(CharacterWardrobeRow.character_profile_id == profile.id)
        .count()
    )
    props_count = (
        db.query(CharacterPropRow)
        .filter(CharacterPropRow.character_profile_id == profile.id)
        .count()
    )
    voice_state = "UNASSIGNED"
    voice_needs_consent = False
    if profile.active_voice_profile_id:
        vp = db.get(VoiceProfileRow, profile.active_voice_profile_id)
        if vp:
            voice_state = vp.source_mode if vp.source_mode else "UNASSIGNED"
            if vp.approval_status == "approved" and voice_state == "UNASSIGNED":
                voice_state = "PRESET"
            if voice_state == "CLONE" and not vp.consent_record_id:
                voice_needs_consent = True
    skin = _loads(profile.skin_json, {})
    hair = _loads(profile.hair_json, {})
    personality = _loads(profile.personality_json, {})
    performance = _loads(profile.performance_json, {})
    continuity = _loads(profile.continuity_json, {})
    has_physical = bool(any(skin.values()) or any(hair.values()) or profile.body_type or profile.height_description)
    has_personality = bool(any(str(v).strip() for v in personality.values() if v is not None))
    has_performance = bool(any(str(v).strip() for v in performance.values() if v is not None))
    has_continuity = bool(continuity.get("notes") or continuity.get("locked_features"))
    return compute_coverage(
        present_roles=roles,
        has_physical_details=has_physical,
        has_personality=has_personality,
        has_performance=has_performance,
        has_wardrobe=wardrobes > 0,
        has_props=props_count > 0,
        voice_state=voice_state,  # type: ignore[arg-type]
        voice_needs_consent=voice_needs_consent,
        continuity_notes=has_continuity,
        profile_status=profile.status,
    )


def to_out(db: Session, profile: CharacterProfileRow, *, include_coverage: bool = True) -> CharacterProfileOut:
    cov = _coverage_for(db, profile) if include_coverage else None
    return CharacterProfileOut(
        id=profile.id,
        project_id=profile.project_id,
        name=profile.name,
        slug=profile.slug,
        role=profile.role,
        description=profile.description,
        apparent_age=profile.apparent_age,
        species_or_type=profile.species_or_type,
        gender_presentation=profile.gender_presentation,
        cultural_background=profile.cultural_background,
        height_description=profile.height_description,
        body_type=profile.body_type,
        visual_description=getattr(profile, "visual_description", "") or "",
        visual_style=getattr(profile, "visual_style", "") or "",
        status=profile.status,  # type: ignore[arg-type]
        approval_status=profile.approval_status,  # type: ignore[arg-type]
        active_version_id=profile.active_version_id,
        active_voice_profile_id=profile.active_voice_profile_id,
        active_wardrobe_id=profile.active_wardrobe_id,
        skin=_loads(profile.skin_json, {}),
        hair=_loads(profile.hair_json, {}),
        personality=_loads(profile.personality_json, {}),
        performance=_loads(profile.performance_json, {}),
        continuity=_loads(profile.continuity_json, {}),
        motion=_loads(getattr(profile, "motion_json", None) or "{}", {}),
        emotion=_loads(getattr(profile, "emotion_json", None) or "{}", {}),
        relationships=_loads(getattr(profile, "relationships_json", None) or "[]", []),
        prompt_package=_loads(getattr(profile, "prompt_package_json", None) or "{}", {}),
        coverage=cov,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def list_profiles(db: Session, project_id: str) -> list[CharacterProfileOut]:
    rows = (
        db.query(CharacterProfileRow)
        .filter(CharacterProfileRow.project_id == project_id)
        .order_by(CharacterProfileRow.updated_at.desc())
        .all()
    )
    return [to_out(db, r) for r in rows]


def get_profile(db: Session, project_id: str, character_id: str) -> CharacterProfileOut:
    row = db.get(CharacterProfileRow, character_id)
    if not row or row.project_id != project_id:
        raise _err("NOT_FOUND", "Character Profile not found.", 404)
    return to_out(db, row)


def create_profile(db: Session, project_id: str, body: CharacterProfileCreate) -> CharacterProfileOut:
    now = _now()
    cid = str(uuid.uuid4())
    vid = str(uuid.uuid4())
    slug = body.slug.strip() or _slugify(body.name)
    profile = CharacterProfileRow(
        id=cid,
        project_id=project_id,
        name=body.name.strip(),
        slug=slug,
        role=body.role,
        description=body.description,
        visual_description=getattr(body, "visual_description", "") or "",
        visual_style=getattr(body, "visual_style", "") or "",
        apparent_age=body.apparent_age,
        species_or_type=body.species_or_type or "human",
        gender_presentation=body.gender_presentation,
        cultural_background=body.cultural_background,
        height_description=body.height_description,
        body_type=body.body_type,
        status="DRAFT",
        approval_status="draft",
        active_version_id=vid,
        skin_json="{}",
        hair_json="{}",
        personality_json="{}",
        performance_json="{}",
        continuity_json="{}",
        motion_json="{}",
        emotion_json="{}",
        relationships_json="[]",
        prompt_package_json="{}",
        created_at=now,
        updated_at=now,
    )
    version = CharacterVersionRow(
        id=vid,
        character_profile_id=cid,
        version_number=1,
        version_label="v1",
        change_summary="Initial draft",
        status="DRAFT",
        snapshot_json=_dumps({"name": body.name}),
        created_at=now,
    )
    db.add(profile)
    db.add(version)
    db.commit()
    db.refresh(profile)
    return to_out(db, profile)


def update_profile(
    db: Session, project_id: str, character_id: str, body: CharacterProfileUpdate
) -> CharacterProfileOut:
    row = db.get(CharacterProfileRow, character_id)
    if not row or row.project_id != project_id:
        raise _err("NOT_FOUND", "Character Profile not found.", 404)
    if row.status in ("LOCKED", "ARCHIVED"):
        raise _err("LOCKED_VERSION", "Cannot mutate a locked or archived Character Profile.", 409)

    # If approved, create a new draft version instead of silently mutating approved snapshot.
    active = _version_locked(db, row.active_version_id)
    if active and active.status in ("APPROVED", "LOCKED"):
        new_vid = str(uuid.uuid4())
        now = _now()
        max_n = (
            db.query(CharacterVersionRow)
            .filter(CharacterVersionRow.character_profile_id == row.id)
            .count()
        )
        db.add(
            CharacterVersionRow(
                id=new_vid,
                character_profile_id=row.id,
                version_number=max_n + 1,
                version_label=f"v{max_n + 1}",
                change_summary="Draft revision from approved version",
                status="DRAFT",
                parent_version_id=active.id,
                snapshot_json=active.snapshot_json,
                created_at=now,
            )
        )
        row.active_version_id = new_vid
        row.status = "DRAFT"
        row.approval_status = "draft"

    data = body.model_dump(exclude_unset=True)
    for key in (
        "name",
        "role",
        "description",
        "apparent_age",
        "species_or_type",
        "gender_presentation",
        "cultural_background",
        "height_description",
        "body_type",
        "visual_description",
        "visual_style",
        "active_wardrobe_id",
        "active_voice_profile_id",
    ):
        if key in data and data[key] is not None:
            setattr(row, key, data[key])
    if body.skin is not None:
        row.skin_json = body.skin.model_dump_json()
    if body.hair is not None:
        row.hair_json = body.hair.model_dump_json()
    if body.personality is not None:
        row.personality_json = body.personality.model_dump_json()
    if body.performance is not None:
        row.performance_json = body.performance.model_dump_json()
    if body.continuity is not None:
        row.continuity_json = body.continuity.model_dump_json()
    if body.motion is not None:
        row.motion_json = body.motion.model_dump_json()
    if body.emotion is not None:
        row.emotion_json = body.emotion.model_dump_json()
    if body.relationships is not None:
        row.relationships_json = _dumps([r.model_dump() for r in body.relationships])
    row.updated_at = _now()
    cov = _coverage_for(db, row)
    if row.status not in ("APPROVED", "LOCKED", "ARCHIVED"):
        row.status = cov.status
    db.commit()
    db.refresh(row)
    return to_out(db, row)


def seed_korri_from_canon(db: Session, project_id: str) -> CharacterProfileOut:
    """Create or refresh Korri from locked korri.v1 canon — no invented traits."""
    from .canon import apply_korri_canon_to_create_defaults

    defaults = apply_korri_canon_to_create_defaults()
    existing = (
        db.query(CharacterProfileRow)
        .filter(CharacterProfileRow.project_id == project_id, CharacterProfileRow.slug == "korri")
        .first()
    )
    if existing:
        character_id = existing.id
    else:
        created = create_profile(
            db,
            project_id,
            CharacterProfileCreate(
                name=defaults["name"],
                slug=defaults["slug"],
                role=defaults["role"],
                apparent_age=defaults["apparent_age"],
                species_or_type=defaults["species_or_type"],
                height_description=defaults["height_description"],
                body_type=defaults["body_type"],
                description="Korri — Human / Sun Sprite Elf Hybrid (Sass Queen). Canon pack korri.v1.",
            ),
        )
        character_id = created.id

    wardrobe = defaults.get("wardrobe") or {}
    row = db.get(CharacterProfileRow, character_id)
    assert row
    # Wardrobe row
    from .models import CharacterWardrobeRow

    w = (
        db.query(CharacterWardrobeRow)
        .filter(CharacterWardrobeRow.character_profile_id == character_id)
        .first()
    )
    if not w:
        wid = str(uuid.uuid4())
        w = CharacterWardrobeRow(
            id=wid,
            character_profile_id=character_id,
            name=wardrobe.get("name") or "Handmade Providence default",
            description=wardrobe.get("description") or "",
            materials=wardrobe.get("materials") or "",
            colors=wardrobe.get("colors") or "",
            footwear=wardrobe.get("footwear") or "",
            accessories=wardrobe.get("accessories") or "",
            approval_status="approved",
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(w)
        row.active_wardrobe_id = wid
    else:
        w.description = wardrobe.get("description") or w.description
        w.materials = wardrobe.get("materials") or w.materials
        w.colors = wardrobe.get("colors") or w.colors
        w.footwear = wardrobe.get("footwear") or w.footwear
        w.accessories = wardrobe.get("accessories") or w.accessories
        w.approval_status = "approved"
        row.active_wardrobe_id = w.id

    row.skin_json = _dumps(defaults.get("skin") or {})
    row.hair_json = _dumps(defaults.get("hair") or {})
    row.personality_json = _dumps(defaults.get("personality") or {})
    row.performance_json = _dumps(defaults.get("performance") or {})
    row.motion_json = _dumps(defaults.get("motion") or {})
    row.emotion_json = _dumps(defaults.get("emotion") or {})
    row.relationships_json = _dumps(defaults.get("relationships") or [])
    row.continuity_json = _dumps(defaults.get("continuity") or {})
    row.role = defaults.get("role") or row.role
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return to_out(db, row)


def list_versions(db: Session, project_id: str, character_id: str) -> list[dict[str, Any]]:
    get_profile(db, project_id, character_id)
    rows = (
        db.query(CharacterVersionRow)
        .filter(CharacterVersionRow.character_profile_id == character_id)
        .order_by(CharacterVersionRow.version_number.asc())
        .all()
    )
    return [
        {
            "id": r.id,
            "character_profile_id": r.character_profile_id,
            "version_number": r.version_number,
            "version_label": r.version_label,
            "change_summary": r.change_summary,
            "status": r.status,
            "parent_version_id": r.parent_version_id,
            "approved_at": r.approved_at,
            "approved_by": r.approved_by,
            "locked_at": r.locked_at,
            "created_at": r.created_at,
        }
        for r in rows
    ]


def approve_version(
    db: Session, project_id: str, character_id: str, version_id: str, *, approved_by: str = "owner"
) -> dict[str, Any]:
    profile = db.get(CharacterProfileRow, character_id)
    if not profile or profile.project_id != project_id:
        raise _err("NOT_FOUND", "Character Profile not found.", 404)
    ver = db.get(CharacterVersionRow, version_id)
    if not ver or ver.character_profile_id != character_id:
        raise _err("NOT_FOUND", "Character version not found.", 404)
    if ver.status == "LOCKED":
        raise _err("LOCKED_VERSION", "Version is already locked.", 409)
    now = _now()
    ver.status = "APPROVED"
    ver.approved_at = now
    ver.approved_by = approved_by
    profile.status = "APPROVED"
    profile.approval_status = "approved"
    profile.active_version_id = ver.id
    profile.updated_at = now
    db.commit()
    return {"id": ver.id, "status": ver.status, "approved_at": ver.approved_at}


def lock_version(db: Session, project_id: str, character_id: str, version_id: str) -> dict[str, Any]:
    profile = db.get(CharacterProfileRow, character_id)
    if not profile or profile.project_id != project_id:
        raise _err("NOT_FOUND", "Character Profile not found.", 404)
    ver = db.get(CharacterVersionRow, version_id)
    if not ver or ver.character_profile_id != character_id:
        raise _err("NOT_FOUND", "Character version not found.", 404)
    now = _now()
    ver.status = "LOCKED"
    ver.locked_at = now
    if ver.approved_at == "":
        ver.approved_at = now
        ver.status = "LOCKED"
    profile.status = "LOCKED"
    profile.active_version_id = ver.id
    profile.updated_at = now
    db.commit()
    return {"id": ver.id, "status": ver.status, "locked_at": ver.locked_at}


def attach_reference(
    db: Session, project_id: str, character_id: str, body: ReferenceAttach
) -> dict[str, Any]:
    profile = db.get(CharacterProfileRow, character_id)
    if not profile or profile.project_id != project_id:
        raise _err("NOT_FOUND", "Character Profile not found.", 404)
    if profile.status in ("LOCKED", "ARCHIVED"):
        raise _err("LOCKED_VERSION", "Cannot attach references to a locked profile.", 409)
    if body.reference_role not in ALL_REFERENCE_ROLES:
        raise _err("INVALID_REFERENCE_ROLE", f"Unknown reference role: {body.reference_role}")
    rid = str(uuid.uuid4())
    row = CharacterReferenceAssetRow(
        id=rid,
        character_profile_id=character_id,
        character_version_id=body.character_version_id or profile.active_version_id,
        asset_id=body.asset_id,
        reference_role=body.reference_role,
        view_angle=body.view_angle,
        framing=body.framing,
        approval_status=body.approval_status,
        canonical=body.canonical,
        source_type=body.source_type,
        generation_lineage_json="{}",
        notes=body.notes,
        created_at=_now(),
    )
    db.add(row)
    profile.updated_at = _now()
    cov = _coverage_for(db, profile)
    # recompute after flush
    db.flush()
    cov = _coverage_for(db, profile)
    if profile.status not in ("APPROVED", "LOCKED", "ARCHIVED"):
        profile.status = cov.status
    db.commit()
    return {
        "id": rid,
        "reference_role": body.reference_role,
        "asset_id": body.asset_id,
        "coverage": cov.model_dump(),
    }


def detach_reference(
    db: Session, project_id: str, character_id: str, asset_id: str
) -> dict[str, Any]:
    profile = db.get(CharacterProfileRow, character_id)
    if not profile or profile.project_id != project_id:
        raise _err("NOT_FOUND", "Character Profile not found.", 404)
    if profile.status in ("LOCKED", "ARCHIVED"):
        raise _err("LOCKED_VERSION", "Cannot detach references from a locked profile.", 409)
    row = (
        db.query(CharacterReferenceAssetRow)
        .filter(
            CharacterReferenceAssetRow.character_profile_id == character_id,
            CharacterReferenceAssetRow.asset_id == asset_id,
        )
        .first()
    )
    if not row:
        return {"ok": True, "detached": None}
    db.delete(row)
    profile.updated_at = _now()
    cov = _coverage_for(db, profile)
    if profile.status not in ("APPROVED", "LOCKED", "ARCHIVED"):
        profile.status = cov.status
    db.commit()
    return {"ok": True, "detached": asset_id}


def approve_character_candidate(
    db: Session,
    project_id: str,
    character_id: str,
    *,
    asset_id: str,
    reference_role: str = "hero_identity",
    source_type: str = "generation",
    notes: str = "Approved casting candidate",
) -> dict[str, Any]:
    """Mark a generated candidate as the canonical approved casting image.

    Demotes any existing canonical reference for the same role, then attaches
    the chosen asset as canonical + approval_status=approved. Does not touch
    other roles or the visual-sheet pack status (owner-approve handles gates).
    Safe to call repeatedly; idempotent if the same asset is already canonical.
    """
    profile = db.get(CharacterProfileRow, character_id)
    if not profile or profile.project_id != project_id:
        raise _err("NOT_FOUND", "Character Profile not found.", 404)
    if profile.status in ("LOCKED", "ARCHIVED"):
        raise _err("LOCKED_VERSION", "Cannot approve references for a locked profile.", 409)
    if reference_role not in ALL_REFERENCE_ROLES:
        raise _err("INVALID_REFERENCE_ROLE", f"Unknown reference role: {reference_role}")

    # Demote any existing canonical reference for this role.
    existing = (
        db.query(CharacterReferenceAssetRow)
        .filter(
            CharacterReferenceAssetRow.character_profile_id == character_id,
            CharacterReferenceAssetRow.reference_role == reference_role,
            CharacterReferenceAssetRow.canonical.is_(True),
        )
        .all()
    )
    already_canonical = False
    for row in existing:
        if row.asset_id == asset_id:
            already_canonical = True
        else:
            row.canonical = False
            row.approval_status = "review"

    if already_canonical:
        # Ensure the existing row is marked approved.
        for row in existing:
            if row.asset_id == asset_id:
                row.approval_status = "approved"
                row.canonical = True
        profile.updated_at = _now()
        db.commit()
        return {
            "characterId": character_id,
            "assetId": asset_id,
            "referenceRole": reference_role,
            "canonical": True,
            "approvalStatus": "approved",
            "replaced": False,
        }

    rid = str(uuid.uuid4())
    row = CharacterReferenceAssetRow(
        id=rid,
        character_profile_id=character_id,
        character_version_id=profile.active_version_id,
        asset_id=asset_id,
        reference_role=reference_role,
        approval_status="approved",
        canonical=True,
        source_type=source_type,
        generation_lineage_json="{}",
        notes=notes,
        created_at=_now(),
    )
    db.add(row)
    profile.updated_at = _now()
    db.commit()
    return {
        "characterId": character_id,
        "referenceId": rid,
        "assetId": asset_id,
        "referenceRole": reference_role,
        "canonical": True,
        "approvalStatus": "approved",
        "replaced": bool(existing),
    }


def list_references(db: Session, project_id: str, character_id: str) -> list[dict[str, Any]]:
    get_profile(db, project_id, character_id)
    # Heal: visual-sheet roleAssets → Character Profile reference rows (category tabs)
    try:
        from .visual_sheet import heal_pack_references

        heal_pack_references(db, project_id, character_id)
    except Exception:
        pass
    rows = (
        db.query(CharacterReferenceAssetRow)
        .filter(CharacterReferenceAssetRow.character_profile_id == character_id)
        .order_by(CharacterReferenceAssetRow.created_at.asc())
        .all()
    )
    return [
        {
            "id": r.id,
            "asset_id": r.asset_id,
            "reference_role": r.reference_role,
            "view_angle": r.view_angle,
            "framing": r.framing,
            "approval_status": r.approval_status,
            "canonical": r.canonical,
            "source_type": r.source_type,
            "notes": r.notes,
            "character_version_id": r.character_version_id,
            "created_at": r.created_at,
        }
        for r in rows
    ]


def resolve_character_by_name(
    db: Session, project_id: str, name: str
) -> CharacterProfileRow | None:
    """Resolve a character profile by display name or slug (case-insensitive).

    Centralizes the name→character resolution that was previously duplicated
    inline in codirector/wiki.py and wiki_intelligence/compiled/page_compiler.py.
    Returns None if no match. Tries exact name, then slug, then case-insensitive.
    """
    if not name or not name.strip():
        return None
    clean = name.strip()
    lowered = clean.lower()

    # Exact name match first.
    row = (
        db.query(CharacterProfileRow)
        .filter(
            CharacterProfileRow.project_id == project_id,
            CharacterProfileRow.name == clean,
        )
        .first()
    )
    if row:
        return row

    # Slug match.
    row = (
        db.query(CharacterProfileRow)
        .filter(
            CharacterProfileRow.project_id == project_id,
            CharacterProfileRow.slug == _slugify(clean),
        )
        .first()
    )
    if row:
        return row

    # Case-insensitive name match.
    rows = (
        db.query(CharacterProfileRow)
        .filter(CharacterProfileRow.project_id == project_id)
        .all()
    )
    for r in rows:
        if r.name and r.name.lower() == lowered:
            return r
        if r.slug and r.slug.lower() == lowered:
            return r

    return None


def resolve_approved_reference(
    db: Session,
    character_id: str,
    role: str = "hero_identity",
) -> str | None:
    """Resolve the canonical/approved reference asset_id for a character role.

    Centralizes the predicate `reference_role == role and (canonical or
    approval_status == "approved")` that was duplicated inline in
    codirector/wiki.py:392 and wiki_intelligence/compiled/page_compiler.py:163.
    Returns the asset_id or None.
    """
    refs = (
        db.query(CharacterReferenceAssetRow)
        .filter(CharacterReferenceAssetRow.character_profile_id == character_id)
        .all()
    )
    for ref in refs:
        if ref.reference_role == role and (ref.canonical or ref.approval_status == "approved"):
            return ref.asset_id
    return None


def coverage(db: Session, project_id: str, character_id: str):
    profile = db.get(CharacterProfileRow, character_id)
    if not profile or profile.project_id != project_id:
        raise _err("NOT_FOUND", "Character Profile not found.", 404)
    return _coverage_for(db, profile)


def create_wardrobe(
    db: Session, project_id: str, character_id: str, body: WardrobeCreate
) -> dict[str, Any]:
    profile = db.get(CharacterProfileRow, character_id)
    if not profile or profile.project_id != project_id:
        raise _err("NOT_FOUND", "Character Profile not found.", 404)
    wid = str(uuid.uuid4())
    now = _now()
    row = CharacterWardrobeRow(
        id=wid,
        character_profile_id=character_id,
        character_version_id=profile.active_version_id,
        name=body.name,
        description=body.description,
        materials=body.materials,
        colors=body.colors,
        footwear=body.footwear,
        jewelry=body.jewelry,
        accessories=body.accessories,
        makeup_state=body.makeup_state,
        hair_state=body.hair_state,
        continuity_rules=body.continuity_rules,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    if not profile.active_wardrobe_id:
        profile.active_wardrobe_id = wid
    profile.updated_at = now
    db.commit()
    return {"id": wid, "name": body.name, "approval_status": "draft"}


def list_wardrobes(db: Session, project_id: str, character_id: str) -> list[dict[str, Any]]:
    get_profile(db, project_id, character_id)
    rows = db.query(CharacterWardrobeRow).filter(CharacterWardrobeRow.character_profile_id == character_id).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "approval_status": r.approval_status,
            "materials": r.materials,
            "colors": r.colors,
            "scene_assignments": _loads(r.scene_assignments_json, []),
        }
        for r in rows
    ]


def create_prop(db: Session, project_id: str, character_id: str, body: PropCreate) -> dict[str, Any]:
    profile = db.get(CharacterProfileRow, character_id)
    if not profile or profile.project_id != project_id:
        raise _err("NOT_FOUND", "Character Profile not found.", 404)
    pid = str(uuid.uuid4())
    row = CharacterPropRow(
        id=pid,
        character_profile_id=character_id,
        character_version_id=profile.active_version_id,
        name=body.name,
        prop_type=body.prop_type,
        description=body.description,
        materials=body.materials,
        colors=body.colors,
        placement=body.placement,
        how_worn=body.how_worn,
        hand_assignment=body.hand_assignment,
        usage_behavior=body.usage_behavior,
        continuity_rules=body.continuity_rules,
        library_asset_id=body.library_asset_id,
        created_at=_now(),
    )
    db.add(row)
    profile.updated_at = _now()
    db.commit()
    return {"id": pid, "name": body.name, "prop_type": body.prop_type}


def list_props(db: Session, project_id: str, character_id: str) -> list[dict[str, Any]]:
    get_profile(db, project_id, character_id)
    rows = db.query(CharacterPropRow).filter(CharacterPropRow.character_profile_id == character_id).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "prop_type": r.prop_type,
            "description": r.description,
            "library_asset_id": r.library_asset_id,
            "approval_status": r.approval_status,
        }
        for r in rows
    ]


def upsert_trait(db: Session, project_id: str, character_id: str, body: TraitUpsert) -> dict[str, Any]:
    profile = db.get(CharacterProfileRow, character_id)
    if not profile or profile.project_id != project_id:
        raise _err("NOT_FOUND", "Character Profile not found.", 404)
    if profile.status in ("LOCKED", "ARCHIVED"):
        raise _err("LOCKED_VERSION", "Cannot mutate a locked or archived Character Profile.", 409)
    existing = (
        db.query(CharacterTraitRow)
        .filter(
            CharacterTraitRow.character_profile_id == character_id,
            CharacterTraitRow.key == body.key,
        )
        .all()
    )
    for row in existing:
        db.delete(row)
    tid = str(uuid.uuid4())
    row = CharacterTraitRow(
        id=tid,
        character_profile_id=character_id,
        character_version_id=body.character_version_id or profile.active_version_id,
        category=body.category,
        key=body.key,
        value=body.value,
        importance=body.importance,
        canonical=body.canonical,
        provenance=body.provenance or "PROPOSED_BY_CHARACTER_CREATOR",
    )
    db.add(row)
    profile.updated_at = _now()
    db.commit()
    return {
        "id": tid,
        "category": body.category,
        "key": body.key,
        "value": body.value,
        "provenance": row.provenance,
    }


def list_traits(db: Session, project_id: str, character_id: str) -> list[dict[str, Any]]:
    get_profile(db, project_id, character_id)
    rows = (
        db.query(CharacterTraitRow)
        .filter(CharacterTraitRow.character_profile_id == character_id)
        .order_by(CharacterTraitRow.category.asc(), CharacterTraitRow.key.asc())
        .all()
    )
    return [
        {
            "id": r.id,
            "category": r.category,
            "key": r.key,
            "value": r.value,
            "importance": r.importance,
            "canonical": r.canonical,
            "provenance": getattr(r, "provenance", "PROPOSED_BY_CHARACTER_CREATOR"),
            "character_version_id": r.character_version_id,
        }
        for r in rows
    ]


def submit_for_review(
    db: Session, project_id: str, character_id: str, *, submitted_by: str = "character-creator"
) -> dict[str, Any]:
    """Mark profile for user review without approving."""
    profile = db.get(CharacterProfileRow, character_id)
    if not profile or profile.project_id != project_id:
        raise _err("NOT_FOUND", "Character Profile not found.", 404)
    if profile.status in ("LOCKED", "ARCHIVED"):
        raise _err("LOCKED_VERSION", "Cannot submit a locked or archived Character Profile.", 409)
    now = _now()
    profile.approval_status = "review"
    profile.updated_at = now
    # Explicitly do NOT set status=APPROVED or approval_status=approved
    db.commit()
    db.refresh(profile)
    cov = _coverage_for(db, profile)
    return {
        "ok": True,
        "characterId": character_id,
        "approvalStatus": profile.approval_status,
        "status": profile.status,
        "submittedBy": submitted_by,
        "coverage": cov.model_dump(),
        "note": "Submitted for user review. Profile is NOT approved.",
    }


def _next_voice_version_number(db: Session, character_id: str) -> int:
    rows = (
        db.query(VoiceProfileRow.version_number)
        .filter(VoiceProfileRow.character_profile_id == character_id)
        .all()
    )
    return (max((r[0] or 0) for r in rows) + 1) if rows else 1


def create_voice_profile(
    db: Session, project_id: str, character_id: str, body: VoiceProfileCreate
) -> dict[str, Any]:
    profile = db.get(CharacterProfileRow, character_id)
    if not profile or profile.project_id != project_id:
        raise _err("NOT_FOUND", "Character Profile not found.", 404)
    vid = str(uuid.uuid4())
    now = _now()
    row = VoiceProfileRow(
        id=vid,
        project_id=project_id,
        character_profile_id=character_id,
        character_version_id=body.character_version_id or profile.active_version_id,
        version_number=_next_voice_version_number(db, character_id),
        name=body.name,
        source_mode=body.source_mode,
        provider=body.provider,
        model_id=body.model_id,
        status="DRAFT",
        approval_status="draft",
        language=body.language,
        accent=body.accent,
        perceived_age=body.perceived_age,
        pitch_description=body.pitch_description,
        pace_description=body.pace_description,
        tone_description=body.tone_description,
        resonance_description=body.resonance_description,
        warmth=body.warmth,
        breathiness=body.breathiness,
        energy=body.energy,
        emotional_range=body.emotional_range,
        pronunciation_notes=body.pronunciation_notes,
        voice_design_prompt=body.voice_design_prompt,
        reference_asset_id=body.reference_asset_id,
        reference_transcript=body.reference_transcript,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    if not profile.active_voice_profile_id:
        profile.active_voice_profile_id = vid
    profile.updated_at = now
    db.commit()
    return voice_to_dict(row)


def fork_draft_voice_profile(
    db: Session,
    project_id: str,
    character_id: str,
    source_voice_id: str,
    *,
    reason: str = "Draft revision from approved voice",
) -> tuple[VoiceProfileRow, bool]:
    """Return a mutable voice row. If source is approved, fork a new draft (never mutate approved)."""
    profile = db.get(CharacterProfileRow, character_id)
    if not profile or profile.project_id != project_id:
        raise _err("NOT_FOUND", "Character Profile not found.", 404)
    src = db.get(VoiceProfileRow, source_voice_id)
    if not src or src.project_id != project_id or src.character_profile_id != character_id:
        raise _err("NOT_FOUND", "Voice Profile not found.", 404)
    if src.approval_status != "approved":
        return src, False

    now = _now()
    vid = str(uuid.uuid4())
    lineage = _loads(src.lineage_json, {})
    lineage = {
        **lineage,
        "forkedFrom": src.id,
        "forkReason": reason,
        "forkedAt": now,
    }
    row = VoiceProfileRow(
        id=vid,
        project_id=project_id,
        character_profile_id=character_id,
        character_version_id=src.character_version_id or profile.active_version_id,
        version_number=_next_voice_version_number(db, character_id),
        name=src.name or "Voice",
        source_mode=src.source_mode,
        provider=src.provider,
        model_id=src.model_id,
        status="DRAFT",
        approval_status="draft",
        language=src.language,
        accent=src.accent,
        perceived_age=src.perceived_age,
        pitch_description=src.pitch_description,
        pace_description=src.pace_description,
        tone_description=src.tone_description,
        resonance_description=src.resonance_description,
        warmth=src.warmth,
        breathiness=src.breathiness,
        energy=src.energy,
        emotional_range=src.emotional_range,
        pronunciation_notes=src.pronunciation_notes,
        voice_design_prompt=src.voice_design_prompt,
        reference_asset_id=src.reference_asset_id,
        reference_transcript=src.reference_transcript,
        approved_preview_asset_id=src.approved_preview_asset_id,
        consent_record_id=src.consent_record_id,
        candidate_asset_ids_json=src.candidate_asset_ids_json or "[]",
        lineage_json=_dumps(lineage),
        created_at=now,
        updated_at=now,
        approved_at="",
    )
    db.add(row)
    profile.active_voice_profile_id = vid
    profile.updated_at = now
    db.commit()
    db.refresh(row)
    return row, True


def voice_to_dict(row: VoiceProfileRow) -> dict[str, Any]:
    lineage = _loads(row.lineage_json, {})
    return {
        "id": row.id,
        "project_id": row.project_id,
        "character_profile_id": row.character_profile_id,
        "character_version_id": row.character_version_id,
        "version_number": row.version_number,
        "name": row.name,
        "source_mode": row.source_mode,
        "provider": row.provider,
        "model_id": row.model_id,
        "status": row.status,
        "approval_status": row.approval_status,
        "language": row.language,
        "accent": row.accent,
        "perceived_age": row.perceived_age,
        "pitch_description": row.pitch_description,
        "pace_description": row.pace_description,
        "tone_description": row.tone_description,
        "resonance_description": row.resonance_description,
        "warmth": row.warmth,
        "breathiness": row.breathiness,
        "energy": row.energy,
        "emotional_range": row.emotional_range,
        "pronunciation_notes": row.pronunciation_notes,
        "voice_design_prompt": row.voice_design_prompt,
        "reference_asset_id": row.reference_asset_id,
        "reference_transcript": row.reference_transcript,
        "approved_preview_asset_id": row.approved_preview_asset_id,
        "consent_record_id": row.consent_record_id,
        "candidate_asset_ids": _loads(row.candidate_asset_ids_json, []),
        "candidates": lineage.get("candidatesMeta") or [],
        "pronunciations": lineage.get("pronunciations") or [],
        "reactions": lineage.get("reactions") or [],
        "designBrief": lineage.get("designBrief"),
        "lineage": lineage,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "approved_at": row.approved_at,
    }


def get_voice_or_none(
    db: Session, project_id: str, character_id: str, voice_id: str
) -> VoiceProfileRow | None:
    get_profile(db, project_id, character_id)
    row = db.get(VoiceProfileRow, voice_id)
    if not row or row.project_id != project_id or row.character_profile_id != character_id:
        return None
    return row


def list_voice_profiles(db: Session, project_id: str, character_id: str) -> list[dict[str, Any]]:
    get_profile(db, project_id, character_id)
    rows = (
        db.query(VoiceProfileRow)
        .filter(
            VoiceProfileRow.project_id == project_id,
            VoiceProfileRow.character_profile_id == character_id,
        )
        .order_by(VoiceProfileRow.version_number.asc())
        .all()
    )
    return [voice_to_dict(r) for r in rows]


def record_consent(
    db: Session, project_id: str, character_id: str, voice_id: str, body: VoiceConsentCreate
) -> dict[str, Any]:
    vp = db.get(VoiceProfileRow, voice_id)
    if not vp or vp.project_id != project_id or vp.character_profile_id != character_id:
        raise _err("NOT_FOUND", "Voice Profile not found.", 404)
    if not body.consent_confirmed or not body.synthetic_generation_allowed:
        raise _err(
            "CONSENT_MISSING",
            "Explicit consent for synthetic generation is required before voice cloning.",
            400,
        )
    cid = str(uuid.uuid4())
    now = _now()
    row = VoiceConsentRecordRow(
        id=cid,
        voice_profile_id=voice_id,
        source_owner_name=body.source_owner_name,
        performer_name=body.performer_name,
        authority_type=body.authority_type,
        consent_confirmed=True,
        commercial_use_allowed=body.commercial_use_allowed,
        synthetic_generation_allowed=True,
        project_scope=body.project_scope,
        restriction_notes=body.restriction_notes,
        confirmation_timestamp=now,
        confirmed_by=body.confirmed_by or "owner",
    )
    db.add(row)
    vp.consent_record_id = cid
    vp.updated_at = now
    db.commit()
    return {
        "id": cid,
        "voice_profile_id": voice_id,
        "consent_confirmed": True,
        "synthetic_generation_allowed": True,
        "confirmation_timestamp": now,
    }


def approve_voice_profile(
    db: Session, project_id: str, character_id: str, voice_id: str
) -> dict[str, Any]:
    vp = db.get(VoiceProfileRow, voice_id)
    if not vp or vp.project_id != project_id or vp.character_profile_id != character_id:
        raise _err("NOT_FOUND", "Voice Profile not found.", 404)
    if vp.approval_status == "approved":
        raise _err("LOCKED_VERSION", "Approved Voice Profiles are immutable. Create a new version.", 409)
    now = _now()
    vp.status = "APPROVED"
    vp.approval_status = "approved"
    vp.approved_at = now
    vp.updated_at = now
    profile = db.get(CharacterProfileRow, character_id)
    if profile:
        profile.active_voice_profile_id = voice_id
        profile.updated_at = now
    db.commit()
    return voice_to_dict(vp)


def prompt_hints(db: Session, project_id: str, character_id: str, *, shot_kind: str = "closeup_front") -> dict[str, Any]:
    """Shot-relevant concise production instructions (not full profile dump)."""
    out = get_profile(db, project_id, character_id)
    refs = list_references(db, project_id, character_id)
    preferred_roles = {
        "closeup_front": ["closeup_front", "closeup_three_quarter_front", "skin_closeup", "hair_front"],
        "rear": ["full_body_back", "closeup_back", "hair_back", "wardrobe_reference"],
        "full_body_walk": ["full_body_front", "full_body_side_left", "pose_sheet", "wardrobe_reference"],
    }.get(shot_kind, ["hero_identity", "closeup_front"])
    selected = [r for r in refs if r["reference_role"] in preferred_roles]
    perf = out.performance or {}
    bits = []
    for key in ("posture", "gait", "resting_facial_expression", "speaking_rhythm"):
        if perf.get(key):
            bits.append(f"{key.replace('_', ' ')}: {perf[key]}")
    personality = out.personality or {}
    if personality.get("speech_style"):
        bits.append(f"speech style: {personality['speech_style']}")
    return {
        "character_id": character_id,
        "character_version_id": out.active_version_id,
        "selected_references": selected[:6],
        "production_instructions": "; ".join(bits)[:800],
        "wardrobe_id": out.active_wardrobe_id,
        "voice_profile_id": out.active_voice_profile_id,
        "coverage": out.coverage.model_dump() if out.coverage else None,
    }


def delete_profile(db: Session, project_id: str, character_id: str) -> dict[str, Any]:
    """Permanently delete a character profile and all owned child records.

    This deletes ONLY character-owned rows from the character_identity schema.
    Shared project assets (Library images, Voice Studio voices) are NOT
    automatically deleted — they remain as reusable project resources.

    Returns the deleted character's name for confirmation UI.
    """
    row = db.get(CharacterProfileRow, character_id)
    if not row or row.project_id != project_id:
        raise _err("NOT_FOUND", "Character Profile not found.", 404)

    name = row.name

    voice_ids = [
        vp[0]
        for vp in db.query(VoiceProfileRow.id)
        .filter(VoiceProfileRow.character_profile_id == character_id)
        .all()
    ]

    if voice_ids:
        db.query(VoiceConsentRecordRow).filter(
            VoiceConsentRecordRow.voice_profile_id.in_(voice_ids)
        ).delete(synchronize_session=False)

    db.query(VoiceProfileRow).filter(
        VoiceProfileRow.character_profile_id == character_id
    ).delete(synchronize_session=False)

    db.query(CharacterTraitRow).filter(
        CharacterTraitRow.character_profile_id == character_id
    ).delete(synchronize_session=False)

    db.query(CharacterPropRow).filter(
        CharacterPropRow.character_profile_id == character_id
    ).delete(synchronize_session=False)

    db.query(CharacterWardrobeRow).filter(
        CharacterWardrobeRow.character_profile_id == character_id
    ).delete(synchronize_session=False)

    db.query(CharacterReferenceAssetRow).filter(
        CharacterReferenceAssetRow.character_profile_id == character_id
    ).delete(synchronize_session=False)

    db.query(CharacterVersionRow).filter(
        CharacterVersionRow.character_profile_id == character_id
    ).delete(synchronize_session=False)

    db.delete(row)
    db.commit()
    return {"deleted": True, "name": name}
