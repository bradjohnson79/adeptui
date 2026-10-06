"""Character Identity service (M3.3)."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..db import Asset
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


# Phase 6 Props workspace: a character can have at most this many props.
# Enforced in create_prop; the frontend mirrors the cap in the UI.
MAX_PROPS_PER_CHARACTER = 4


def _now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z"


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
    return s or f"character-{uuid.uuid4().hex[:8]}"


def _repair_placeholder_identity(row: CharacterProfileRow) -> bool:
    from ..creator_scope.contract import (
        is_placeholder_character_name,
        is_placeholder_character_slug,
    )

    changed = False
    if is_placeholder_character_slug(row.slug) and row.name and not is_placeholder_character_name(row.name):
        row.slug = _slugify(row.name)
        changed = True
    return changed


def _loads(raw: str | None, default: Any) -> Any:
    try:
        return json.loads(raw or "") if raw else default
    except Exception:
        return default


def _dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False)


def _err(code: str, message: str, status: int = 400, extra: dict[str, Any] | None = None) -> HTTPException:
    detail: dict[str, Any] = {"code": code, "message": message}
    if extra:
        detail.update(extra)
        detail["details"] = extra
    return HTTPException(status_code=status, detail=detail)


def _check_character_name_collision(
    db: Session,
    *,
    project_id: str,
    name: str,
    exclude_id: str = "",
    making_global: bool = False,
) -> None:
    from ..creator_scope.contract import ENTITY_CHARACTER, CreatorScopeError
    from ..creator_scope.service import require_unique_profile_name

    try:
        require_unique_profile_name(
            db,
            entity_type=ENTITY_CHARACTER,
            name=name,
            owning_project_id=project_id,
            exclude_id=exclude_id,
            making_global=making_global,
        )
    except CreatorScopeError as exc:
        raise _err(exc.code, exc.message, exc.status, extra=exc.extra) from exc


def _read_is_global(body: Any, *, fallback: bool = False) -> bool:
    from ..creator_scope.contract import normalize_is_global

    if body is None:
        return bool(fallback)
    if isinstance(body, dict):
        if body.get("isGlobal") is not None:
            return normalize_is_global(body.get("isGlobal"))
        if body.get("is_global") is not None:
            return normalize_is_global(body.get("is_global"))
        return bool(fallback)
    if getattr(body, "isGlobal", None) is not None:
        return normalize_is_global(body.isGlobal)
    if getattr(body, "is_global", None) is not None:
        return normalize_is_global(body.is_global)
    return bool(fallback)


def _character_is_global(row: CharacterProfileRow) -> bool:
    return bool(getattr(row, "is_global", False))


def _character_visible(row: CharacterProfileRow | None, project_id: str) -> bool:
    if row is None:
        return False
    return row.project_id == project_id or _character_is_global(row)


OWNER_REQUIRED_MESSAGE = "Global characters can only be edited from the project that created them."
PROFILE_NOT_FOUND_MESSAGE = "Character Profile not found."


def _require_visible_profile(db: Session, project_id: str, character_id: str) -> CharacterProfileRow:
    row = db.get(CharacterProfileRow, character_id)
    if row is None:
        healed = _reconcile_missing_local_profile(db, project_id, character_id)
        if healed is not None:
            return healed
        raise _err("NOT_FOUND", PROFILE_NOT_FOUND_MESSAGE, 404)
    if not _character_visible(row, project_id):
        raise _err("NOT_FOUND", PROFILE_NOT_FOUND_MESSAGE, 404)
    return row


def require_owned_profile(db: Session, project_id: str, character_id: str) -> CharacterProfileRow:
    """Visible profiles may be read from any project; mutation/generation requires ownership."""
    row = _require_visible_profile(db, project_id, character_id)
    if row.project_id != project_id:
        raise _err("OWNER_REQUIRED", OWNER_REQUIRED_MESSAGE, 403)
    return row


def _name_from_version_snapshot(row: CharacterVersionRow | None) -> str:
    if row is None:
        return ""
    snap = _loads(row.snapshot_json, {})
    if isinstance(snap, dict):
        return str(snap.get("name") or "").strip()
    return ""


def _character_id_from_asset_meta(raw: str | None) -> str:
    try:
        meta = json.loads(raw or "{}") if raw else {}
    except Exception:
        return ""
    if not isinstance(meta, dict):
        return ""
    cid = str(meta.get("characterId") or meta.get("character_id") or "").strip()
    if cid:
        return cid
    library = meta.get("library") if isinstance(meta.get("library"), dict) else {}
    return str(library.get("characterId") or library.get("character_id") or "").strip()


def _character_name_from_project_assets(db: Session, project_id: str, character_id: str) -> str:
    cid = str(character_id or "").strip()
    if not cid:
        return ""
    assets = (
        db.query(Asset)
        .filter(Asset.project_id == project_id, Asset.prompt_meta_json.contains(cid))
        .all()
    )
    for asset in assets:
        try:
            meta = json.loads(asset.prompt_meta_json or "{}")
        except Exception:
            continue
        if not isinstance(meta, dict):
            continue
        name = str(meta.get("characterName") or meta.get("character_name") or "").strip()
        if name:
            return name
    return ""


def _project_claims_character(db: Session, project_id: str, character_id: str) -> bool:
    """True when this project already owns assets/jobs bound to the canonical character id."""
    refs = (
        db.query(CharacterReferenceAssetRow)
        .filter(CharacterReferenceAssetRow.character_profile_id == character_id)
        .all()
    )
    for ref in refs:
        asset_id = str(getattr(ref, "asset_id", "") or "").strip()
        if not asset_id:
            continue
        asset = db.get(Asset, asset_id)
        if asset is not None and str(getattr(asset, "project_id", "") or "") == project_id:
            return True
    from ..db import Job

    job = (
        db.query(Job)
        .filter(Job.project_id == project_id, Job.params_json.contains(character_id))
        .first()
    )
    if job is not None:
        return True
    asset = (
        db.query(Asset)
        .filter(Asset.project_id == project_id, Asset.prompt_meta_json.contains(character_id))
        .first()
    )
    return asset is not None


def _reconcile_missing_local_profile(
    db: Session, project_id: str, character_id: str
) -> CharacterProfileRow | None:
    """Recreate a missing profile row when this project already has that canonical identity.

    Does not invent a new character id, does not match by display name, and never
    re-homes a foreign Global character.
    """
    cid = str(character_id or "").strip()
    if not cid:
        return None
    from ..creator_scope.contract import ENTITY_CHARACTER
    from ..creator_scope.service import is_entity_deleted

    if is_entity_deleted(db, entity_type=ENTITY_CHARACTER, entity_id=cid):
        return None
    existing = db.get(CharacterProfileRow, cid)
    if existing is not None:
        return None
    versions = (
        db.query(CharacterVersionRow)
        .filter(CharacterVersionRow.character_profile_id == cid)
        .order_by(CharacterVersionRow.version_number.desc())
        .all()
    )
    traits = (
        db.query(CharacterTraitRow)
        .filter(CharacterTraitRow.character_profile_id == cid)
        .all()
    )
    refs = (
        db.query(CharacterReferenceAssetRow)
        .filter(CharacterReferenceAssetRow.character_profile_id == cid)
        .all()
    )
    claimed = _project_claims_character(db, project_id, cid)
    if not versions and not traits and not refs and not claimed:
        return None
    if not claimed:
        return None
    latest = versions[0] if versions else None
    name = (
        _name_from_version_snapshot(latest)
        or _character_name_from_project_assets(db, project_id, cid)
        or "Character"
    )
    now = _now()
    vid = latest.id if latest is not None else str(uuid.uuid4())
    if latest is None:
        db.add(
            CharacterVersionRow(
                id=vid,
                character_profile_id=cid,
                version_number=1,
                version_label="v1",
                change_summary="Reconciled missing Character Profile",
                status="DRAFT",
                snapshot_json=_dumps({"name": name}),
                created_at=now,
            )
        )
    profile = CharacterProfileRow(
        id=cid,
        project_id=project_id,
        name=name,
        slug=_slugify(name),
        role="",
        description="",
        visual_description="",
        visual_style="",
        apparent_age="",
        species_or_type="human",
        gender_presentation="",
        cultural_background="",
        height_description="",
        body_type="",
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
        is_global=False,
        created_at=now,
        updated_at=now,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    _reattach_orphaned_character_assets(db, profile)
    _sync_character_scope(db, profile)
    return profile


def _reattach_orphaned_character_assets(db: Session, profile: CharacterProfileRow) -> None:
    existing = (
        db.query(CharacterReferenceAssetRow)
        .filter(CharacterReferenceAssetRow.character_profile_id == profile.id)
        .count()
    )
    if existing:
        return
    assets = (
        db.query(Asset)
        .filter(
            Asset.project_id == profile.project_id,
            Asset.prompt_meta_json.contains(profile.id),
        )
        .order_by(Asset.created_at.desc())
        .all()
    )
    picked: Asset | None = None
    for asset in assets:
        if str(asset.kind or "") not in {"", "image"}:
            continue
        filename = str(asset.filename or "").lower()
        tag = str(asset.tag or "").lower()
        if "crs" in filename or "front" in filename or tag == "character_reference":
            picked = asset
            break
    if picked is None:
        for asset in assets:
            if str(asset.kind or "") in {"", "image"}:
                picked = asset
                break
    if picked is None:
        return
    db.add(
        CharacterReferenceAssetRow(
            id=str(uuid.uuid4()),
            character_profile_id=profile.id,
            character_version_id=profile.active_version_id,
            asset_id=picked.id,
            reference_role="hero_identity",
            view_angle="",
            framing="",
            approval_status="approved",
            canonical=True,
            source_type="library",
            generation_lineage_json="{}",
            notes="Reconnected from Library after missing profile row",
            created_at=_now(),
        )
    )
    db.commit()


def _heal_orphaned_character_identities(db: Session, project_id: str) -> None:
    assets = (
        db.query(Asset)
        .filter(Asset.project_id == project_id, Asset.prompt_meta_json.contains("characterId"))
        .all()
    )
    seen: set[str] = set()
    for asset in assets:
        cid = _character_id_from_asset_meta(getattr(asset, "prompt_meta_json", None))
        if not cid or cid in seen:
            continue
        seen.add(cid)
        from ..creator_scope.contract import ENTITY_CHARACTER
        from ..creator_scope.service import is_entity_deleted

        if is_entity_deleted(db, entity_type=ENTITY_CHARACTER, entity_id=cid):
            continue
        if db.get(CharacterProfileRow, cid) is None:
            _reconcile_missing_local_profile(db, project_id, cid)


def _sync_character_scope(db: Session, row: CharacterProfileRow) -> None:
    try:
        from ..creator_scope.service import sync_scope
        from ..creator_scope.contract import ENTITY_CHARACTER

        identity = ""
        try:
            identity = str(resolve_approved_reference(db, row.id, "hero_identity") or "").strip()
        except Exception:
            identity = ""
        if not identity:
            try:
                identity = str(resolve_approved_reference(db, row.id, "hero_portrait") or "").strip()
            except Exception:
                identity = ""
        if not identity:
            try:
                from .cc_v2 import load_state

                state = load_state(db, row.id)
                front = ((state.get("views") or {}).get("front") or {}) if isinstance(state, dict) else {}
                identity = str(front.get("assetId") or "").strip()
                if not identity:
                    identity = str(((state.get("sheet") or {}) if isinstance(state, dict) else {}).get("assetId") or "").strip()
            except Exception:
                identity = identity or ""
        sync_scope(
            db,
            entity_type=ENTITY_CHARACTER,
            entity_id=row.id,
            owning_project_id=row.project_id,
            is_global=_character_is_global(row),
            tag=row.slug or row.name,
            name=row.name,
            identity_asset_id=identity,
        )
    except Exception:
        pass


def _check_character_tag_collision(
    db: Session,
    *,
    project_id: str,
    name: str,
    slug: str,
    exclude_id: str = "",
    making_global: bool = False,
) -> None:
    from ..creator_scope.contract import ENTITY_CHARACTER, canonical_tag
    from ..creator_scope.service import find_tag_collision

    token = canonical_tag(slug or name)
    if not token:
        return
    hit = find_tag_collision(
        db,
        entity_type=ENTITY_CHARACTER,
        tag=token,
        exclude_id=exclude_id,
        owning_project_id=project_id,
        making_global=making_global,
    )
    if hit is not None:
        raise _err(
            "TAG_COLLISION",
            f"@{token} is already used by {hit.name or 'another character'} "
            f"{'as a Global asset' if hit.is_global else 'in this project'}. Choose a different name.",
            409,
        )
    from sqlalchemy import or_

    rows = (
        db.query(CharacterProfileRow)
        .filter(
            or_(
                CharacterProfileRow.project_id == project_id,
                CharacterProfileRow.is_global.is_(True),
            )
        )
        .all()
    )
    for row in rows:
        if exclude_id and row.id == exclude_id:
            continue
        other = canonical_tag(row.slug or row.name).lower()
        if other != token:
            continue
        if row.project_id == project_id or _character_is_global(row) or making_global:
            raise _err(
                "TAG_COLLISION",
                f"@{token} is already used by {row.name or 'another character'} "
                f"{'as a Global asset' if _character_is_global(row) else 'in this project'}. Choose a different name.",
                409,
            )


# CDX-007: canonical identity references must point at real project image
# assets. Extension check is a lenient secondary signal for legacy rows where
# kind was not stamped; kind=="image" is the primary signal.
IMAGE_FILE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".bmp",
    ".avif",
    ".tif",
    ".tiff",
    ".heic",
}


def _validate_project_image_asset(db: Session, project_id: str, asset_id: str) -> Asset:
    """Validate that asset_id exists, belongs to project_id, and is an image.

    Raises typed 4xx HTTPException (CDX-007) so a crafted request cannot make a
    foreign/nonexistent/non-image asset the canonical identity reference.
    """
    asset = db.get(Asset, str(asset_id))
    if not asset:
        raise _err("ASSET_NOT_FOUND", f"Asset {asset_id} does not exist.", 404)
    if asset.project_id != project_id:
        raise _err("ASSET_NOT_IN_PROJECT", f"Asset {asset_id} does not belong to this project.", 400)
    ext = Path(asset.filename or asset.path or "").suffix.lower()
    if asset.kind != "image" and ext not in IMAGE_FILE_EXTENSIONS:
        raise _err("ASSET_NOT_IMAGE", f"Asset {asset_id} is not an image.", 400)
    return asset


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
        # Phase 6 Props workspace: legacy DBs created before the Props
        # workspace lack the generation_job_id column on character_props.
        prop_rows = conn.execute(text("PRAGMA table_info(character_props)")).fetchall()
        if prop_rows and not any(r[1] == "generation_job_id" for r in prop_rows):
            conn.execute(text("ALTER TABLE character_props ADD COLUMN generation_job_id VARCHAR(36)"))
            conn.commit()
        profile_rows = conn.execute(text("PRAGMA table_info(character_profiles)")).fetchall()
        if profile_rows and not any(r[1] == "is_global" for r in profile_rows):
            conn.execute(text("ALTER TABLE character_profiles ADD COLUMN is_global BOOLEAN NOT NULL DEFAULT 0"))
            conn.commit()
        voice_rows = conn.execute(text("PRAGMA table_info(voice_profiles)")).fetchall()
        if voice_rows and not any(r[1] == "approved_voice_reference_asset_id" for r in voice_rows):
            conn.execute(
                text("ALTER TABLE voice_profiles ADD COLUMN approved_voice_reference_asset_id VARCHAR(36)")
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
        is_global=_character_is_global(profile),
        isGlobal=_character_is_global(profile),
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def list_profiles(db: Session, project_id: str) -> list[CharacterProfileOut]:
    from sqlalchemy import or_

    from ..creator_scope.contract import is_ephemeral_creator_fixture

    _heal_orphaned_character_identities(db, project_id)
    rows = (
        db.query(CharacterProfileRow)
        .filter(
            or_(
                CharacterProfileRow.project_id == project_id,
                CharacterProfileRow.is_global.is_(True),
            )
        )
        .order_by(CharacterProfileRow.updated_at.desc())
        .all()
    )
    seen: set[str] = set()
    out: list[CharacterProfileOut] = []
    for row in rows:
        if row.id in seen:
            continue
        seen.add(row.id)
        if is_ephemeral_creator_fixture(row.name or row.slug):
            continue
        if row.project_id == project_id and _repair_placeholder_identity(row):
            db.commit()
            _sync_character_scope(db, row)
        out.append(to_out(db, row))
    return out


def get_profile(db: Session, project_id: str, character_id: str) -> CharacterProfileOut:
    row = _require_visible_profile(db, project_id, character_id)
    if row.project_id == project_id and _repair_placeholder_identity(row):
        db.commit()
        db.refresh(row)
        _sync_character_scope(db, row)
    return to_out(db, row)


def get_profile_by_id(db: Session, character_id: str) -> CharacterProfileOut:
    """Reference durability: resolve a stored character id even after Global is turned off."""
    row = db.get(CharacterProfileRow, character_id)
    if not row:
        raise _err("NOT_FOUND", "Character Profile not found.", 404)
    return to_out(db, row)


def create_profile(db: Session, project_id: str, body: CharacterProfileCreate) -> CharacterProfileOut:
    now = _now()
    cid = str(uuid.uuid4())
    vid = str(uuid.uuid4())
    slug = body.slug.strip() or _slugify(body.name)
    is_global = _read_is_global(body, fallback=False)
    _check_character_name_collision(
        db,
        project_id=project_id,
        name=body.name,
        making_global=is_global,
    )
    _check_character_tag_collision(
        db,
        project_id=project_id,
        name=body.name,
        slug=slug,
        making_global=is_global,
    )
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
        is_global=is_global,
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
    _sync_character_scope(db, profile)
    return to_out(db, profile)


def update_profile(
    db: Session, project_id: str, character_id: str, body: CharacterProfileUpdate
) -> CharacterProfileOut:
    row = require_owned_profile(db, project_id, character_id)
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
    from ..creator_scope.contract import (
        is_placeholder_character_name,
        is_placeholder_character_slug,
    )

    next_global = _read_is_global(body, fallback=_character_is_global(row))
    if "isGlobal" in data or "is_global" in data:
        next_global = _read_is_global(body, fallback=_character_is_global(row))
    incoming_name = str(data.get("name") or "").strip() if "name" in data else ""
    if incoming_name and is_placeholder_character_name(incoming_name) and not is_placeholder_character_name(row.name):
        data.pop("name", None)
        incoming_name = ""
    next_name = incoming_name or str(row.name or "")
    next_slug = str(getattr(row, "slug", "") or "")
    if is_placeholder_character_slug(next_slug) and next_name and not is_placeholder_character_name(next_name):
        next_slug = _slugify(next_name)
        row.slug = next_slug
    _check_character_name_collision(
        db,
        project_id=project_id,
        name=next_name,
        exclude_id=row.id,
        making_global=next_global,
    )
    _check_character_tag_collision(
        db,
        project_id=project_id,
        name=next_name,
        slug=next_slug,
        exclude_id=row.id,
        making_global=next_global,
    )
    row.is_global = next_global
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
        # Completeness law: never surface INCOMPLETE on the profile itself; the
        # detailed coverage report stays internal for advanced views.
        row.status = "DRAFT" if cov.status == "INCOMPLETE" else cov.status
    db.commit()
    db.refresh(row)
    _sync_character_scope(db, row)
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
    # CDX-007: the canonical reference must point at a real project image asset.
    _validate_project_image_asset(db, project_id, body.asset_id)
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
        # Completeness law: a saved character with a valid name is valid. Keep the
        # detailed coverage report internal; never surface INCOMPLETE on the profile.
        profile.status = "DRAFT" if cov.status == "INCOMPLETE" else cov.status
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
        # Completeness law: never surface INCOMPLETE on the profile itself.
        profile.status = "DRAFT" if cov.status == "INCOMPLETE" else cov.status
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
    owner_confirmed: bool = False,
) -> dict[str, Any]:
    """Mark a generated candidate as the canonical approved Character Reference Sheet.

    One transaction: exact selected sheet → canonical hero → persist CRS revision →
    production-ready. Previous canon stays authoritative if commit fails.

    Production Canon Approval Law: replacing persist CRS / approved canon requires
    ownerConfirmed from the live Character Creator Approve control. This is not a
    character-name special case.
    """
    profile = db.get(CharacterProfileRow, character_id)
    if not profile or profile.project_id != project_id:
        raise _err("NOT_FOUND", "Character Profile not found.", 404)
    if profile.status in ("LOCKED", "ARCHIVED"):
        raise _err("LOCKED_VERSION", "Cannot approve references for a locked profile.", 409)
    if reference_role not in ALL_REFERENCE_ROLES:
        raise _err("INVALID_REFERENCE_ROLE", f"Unknown reference role: {reference_role}")

    from .crs_service import load_persisted_crs

    persisted = load_persisted_crs(db, character_id)
    has_persist_canon = bool(
        persisted.get("approved_sheet_asset_id") or int(persisted.get("crs_revision") or 0)
    )
    if has_persist_canon and not owner_confirmed:
        raise _err(
            "PRODUCTION_CANON_PROTECTED",
            "Approving or replacing this character's look requires the owner Approve button in Character Creator.",
            403,
        )

    _validate_project_image_asset(db, project_id, asset_id)

    generation_used = source_type not in ("upload", "library")
    lineage = json.dumps(
        {
            "generationUsed": generation_used,
            "sourceType": source_type,
            "originalAssetId": asset_id,
            "approvedAt": _now(),
        }
    )

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

    rid = None
    if already_canonical:
        for row in existing:
            if row.asset_id == asset_id:
                row.approval_status = "approved"
                row.canonical = True
                row.source_type = source_type
                row.generation_lineage_json = lineage
                rid = row.id
    else:
        rid = str(uuid.uuid4())
        db.add(
            CharacterReferenceAssetRow(
                id=rid,
                character_profile_id=character_id,
                character_version_id=profile.active_version_id,
                asset_id=asset_id,
                reference_role=reference_role,
                approval_status="approved",
                canonical=True,
                source_type=source_type,
                generation_lineage_json=lineage,
                notes=notes,
                created_at=_now(),
            )
        )

    profile.updated_at = _now()
    profile.approval_status = "approved"
    profile.status = "APPROVED"

    from .crs_service import persist_crs_in_session

    try:
        if reference_role in {"hero_identity", "hero_portrait"}:
            from ..scene_references.reference_eligibility import stamp_aligned_role

            hero_asset = db.get(Asset, asset_id)
            if hero_asset is not None:
                stamp_aligned_role(hero_asset, "character")
        crs_payload = persist_crs_in_session(db, profile, asset_id=asset_id)
        _set_pack_hero_no_commit(db, project_id, character_id, asset_id, crs_payload)
        db.commit()
    except Exception:
        db.rollback()
        raise

    try:
        from ..codirector.conversation.project_cache import invalidate_cache_sections

        invalidate_cache_sections(db, project_id, ["characters"])
    except Exception:
        pass

    return {
        "characterId": character_id,
        "referenceId": rid,
        "assetId": asset_id,
        "referenceRole": reference_role,
        "canonical": True,
        "approvalStatus": "approved",
        "replaced": bool(existing) and not already_canonical,
        "generationUsed": generation_used,
        "sourceType": source_type,
        "productionReady": True,
        "crsRevision": int(crs_payload.get("crs_revision") or 0),
        "approvedSheetAssetId": asset_id,
        "atTag": f"@{profile.name}" if profile.name else None,
    }


def _set_pack_hero_no_commit(
    db: Session,
    project_id: str,
    character_id: str,
    asset_id: str,
    crs_payload: dict[str, Any] | None = None,
) -> None:
    """Align visual-sheet pack hero with the approved sheet without committing."""
    from .visual_sheet import PACK_TRAIT_KEY, _dumps, _load_pack_raw

    pack = _load_pack_raw(db, character_id)
    if not pack:
        return
    previous_hero = str(pack.get("approvedHeroIdentity") or "").strip()
    pack.setdefault("roleAssets", {})["hero_identity"] = asset_id
    pack["approvedHeroIdentity"] = asset_id
    revision = None
    if crs_payload:
        pack["crsRevision"] = crs_payload.get("crs_revision")
        revision = crs_payload.get("crs_revision")

    def _stamp_approved(items: list) -> None:
        for item in items:
            if not isinstance(item, dict):
                continue
            keys = {str(item.get("sheetAssetId") or ""), str(item.get("assetId") or "")}
            if asset_id in keys:
                item["status"] = "approved"
                item["approvalStatus"] = "approved"
                item["approved"] = True
                if revision is not None:
                    item["revision"] = revision

    candidates = list(pack.get("candidates") or [])
    previous = list(pack.get("previousCandidates") or [])
    _stamp_approved(candidates)
    _stamp_approved(previous)
    if previous_hero and previous_hero != asset_id:
        already = any(
            isinstance(item, dict)
            and previous_hero in {str(item.get("sheetAssetId") or ""), str(item.get("assetId") or "")}
            for item in previous
        )
        if not already:
            previous.append(
                {
                    "sheetAssetId": previous_hero,
                    "assetId": previous_hero,
                    "status": "approved",
                    "approvalStatus": "approved",
                    "approved": True,
                    "revision": pack.get("crsRevision") if revision is None else max(int(revision or 1) - 1, 1),
                }
            )
        for item in previous:
            if not isinstance(item, dict):
                continue
            keys = {str(item.get("sheetAssetId") or ""), str(item.get("assetId") or "")}
            if previous_hero in keys and not item.get("approved"):
                item["status"] = "approved"
                item["approvalStatus"] = "approved"
                item["approved"] = True
    pack["candidates"] = [c for c in candidates if not (isinstance(c, dict) and asset_id in {str(c.get("sheetAssetId") or ""), str(c.get("assetId") or "")})]
    pack["previousCandidates"] = previous
    existing = (
        db.query(CharacterTraitRow)
        .filter(
            CharacterTraitRow.character_profile_id == character_id,
            CharacterTraitRow.key == PACK_TRAIT_KEY,
        )
        .all()
    )
    profile = db.get(CharacterProfileRow, character_id)
    for row in existing:
        db.delete(row)
    db.add(
        CharacterTraitRow(
            id=str(uuid.uuid4()),
            character_profile_id=character_id,
            character_version_id=profile.active_version_id if profile else None,
            category="visual_sheet",
            key=PACK_TRAIT_KEY,
            value=_dumps(pack),
            provenance="PROPOSED_BY_CHARACTER_CREATOR",
        )
    )


def _sync_pack_role_asset(db: Session, project_id: str, character_id: str, asset_id: str) -> None:
    """CDX-003: keep the visual-sheet pack roleAssets aligned with the canonical
    approved reference so owner-approve and gate readers resolve the exact asset
    the owner approved (not the first-completed candidate).

    Best-effort: if no pack exists the canonical reference rows remain the
    source of truth.
    """
    try:
        from .visual_sheet import _load_pack_raw, _save_pack

        pack = _load_pack_raw(db, character_id)
        if not pack:
            return
        pack.setdefault("roleAssets", {})["hero_identity"] = asset_id
        _save_pack(db, project_id, character_id, pack)
    except Exception:
        # Pack sync is best-effort; canonical reference rows remain the truth.
        pass


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
    from ..creator_scope.contract import normalize_profile_name

    clean = name.strip()
    lowered = normalize_profile_name(clean)

    from sqlalchemy import or_

    visible = (
        db.query(CharacterProfileRow)
        .filter(
            or_(
                CharacterProfileRow.project_id == project_id,
                CharacterProfileRow.is_global.is_(True),
            )
        )
        .all()
    )
    owned = [r for r in visible if r.project_id == project_id]
    globals_other = [r for r in visible if r.project_id != project_id]
    search_order = owned + globals_other

    for r in search_order:
        if r.name and r.name == clean:
            return r
    slug = _slugify(clean)
    for r in search_order:
        if r.slug and r.slug == slug:
            return r
    for r in search_order:
        if r.name and normalize_profile_name(r.name) == lowered:
            return r
        if r.slug and r.slug.lower() == lowered:
            return r

    compact = re.sub(r"[^a-z0-9]", "", lowered)
    if compact:
        for r in search_order:
            if r.name and re.sub(r"[^a-z0-9]", "", r.name.lower()) == compact:
                return r
            if r.slug and re.sub(r"[^a-z0-9]", "", r.slug.lower()) == compact:
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
    # Phase 6 Props workspace: enforce a maximum of 4 props per character so
    # the creator-facing surface stays focused. A 5th prop is rejected with a
    # clear 400 — the UI also disables the add button at 4, but the backend
    # remains the authority.
    existing_count = (
        db.query(CharacterPropRow)
        .filter(CharacterPropRow.character_profile_id == character_id)
        .count()
    )
    if existing_count >= MAX_PROPS_PER_CHARACTER:
        raise _err(
            "PROP_LIMIT_REACHED",
            f"A character can have at most {MAX_PROPS_PER_CHARACTER} props. "
            "Remove one before adding another.",
            400,
        )
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
    # If the caller supplied an existing Library asset (upload / library
    # pick), register it as a character-associated Library asset so it lives
    # in the character's library folder without duplicating the binary.
    if body.library_asset_id:
        _assign_prop_library_asset(db, project_id, character_id, body.library_asset_id)
    return {"id": pid, "name": body.name, "prop_type": body.prop_type}


def update_prop(
    db: Session, project_id: str, character_id: str, prop_id: str, body: "PropUpdate"
) -> dict[str, Any]:
    """Patch an existing prop's editable fields (name, description, etc.).

    Does not touch approval_status or generation_job_id. If a new
    library_asset_id is supplied, registers it as a character-associated
    Library asset (no binary duplication).
    """
    from .schemas import PropUpdate  # local import to avoid cycle at module load

    assert isinstance(body, PropUpdate)
    profile = db.get(CharacterProfileRow, character_id)
    if not profile or profile.project_id != project_id:
        raise _err("NOT_FOUND", "Character Profile not found.", 404)
    row = db.get(CharacterPropRow, prop_id)
    if not row or row.character_profile_id != character_id:
        raise _err("NOT_FOUND", "Prop not found.", 404)
    data = body.model_dump(exclude_unset=True)
    new_asset_id: str | None = None
    for key, value in data.items():
        if key == "library_asset_id":
            new_asset_id = value  # apply after row update
            continue
        if value is not None:
            setattr(row, key, value)
    if new_asset_id is not None:
        row.library_asset_id = new_asset_id
    profile.updated_at = _now()
    db.commit()
    if new_asset_id:
        _assign_prop_library_asset(db, project_id, character_id, new_asset_id)
    return {
        "id": row.id,
        "name": row.name,
        "prop_type": row.prop_type,
        "description": row.description,
        "library_asset_id": row.library_asset_id,
        "approval_status": row.approval_status,
    }


def _assign_prop_library_asset(
    db: Session, project_id: str, character_id: str, asset_id: str
) -> None:
    """Register an existing Library image as a character-associated asset.

    Uses project_library.service.assign_asset with entity_type="character"
    and entity_id=characterId so the prop image lives in the character's
    library folder. The binary is NOT duplicated — the same Asset row is
    classified into the character's folder.
    """
    try:
        from ..db import Asset
        from ..project_library.service import assign_asset

        asset = db.get(Asset, asset_id)
        if not asset or asset.project_id != project_id:
            return
        profile = db.get(CharacterProfileRow, character_id)
        entity_name = (profile.name if profile else "") or "Character"
        assign_asset(
            db,
            asset,
            entity_type="character",
            entity_name=entity_name,
            entity_id=character_id,
            classified_by="character_props",
            hints={"purpose": "character_prop"},
        )
    except Exception:
        # Library classification is best-effort: a failure here (e.g. minimal
        # test DB without the library taxonomy) must not break prop creation
        # or approval. The prop row remains the source of truth.
        return


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
            "generation_job_id": getattr(r, "generation_job_id", None),
        }
        for r in rows
    ]


def delete_prop(db: Session, project_id: str, character_id: str, prop_id: str) -> dict[str, Any]:
    """Delete a single prop row.

    Deletes ONLY the character_props row. The associated Library image (if
    any) remains a reusable project resource — consistent with
    delete_profile, which never deletes shared Library assets.
    """
    profile = db.get(CharacterProfileRow, character_id)
    if not profile or profile.project_id != project_id:
        raise _err("NOT_FOUND", "Character Profile not found.", 404)
    row = db.get(CharacterPropRow, prop_id)
    if not row or row.character_profile_id != character_id:
        raise _err("NOT_FOUND", "Prop not found.", 404)
    name = row.name
    db.delete(row)
    profile.updated_at = _now()
    db.commit()
    return {"deleted": True, "id": prop_id, "name": name}


def approve_prop(
    db: Session, project_id: str, character_id: str, prop_id: str
) -> dict[str, Any]:
    """Mark a prop as approved (saved) and ensure its Library image is
    registered as a character-associated Library asset.

    No binary duplication: the existing Library Asset row is classified into
    the character's library folder via project_library.service.assign_asset.
    """
    profile = db.get(CharacterProfileRow, character_id)
    if not profile or profile.project_id != project_id:
        raise _err("NOT_FOUND", "Character Profile not found.", 404)
    row = db.get(CharacterPropRow, prop_id)
    if not row or row.character_profile_id != character_id:
        raise _err("NOT_FOUND", "Prop not found.", 404)
    if not row.library_asset_id:
        raise _err(
            "NO_PROP_IMAGE",
            "Generate or attach a prop image before approving.",
            400,
        )
    row.approval_status = "approved"
    profile.updated_at = _now()
    db.commit()
    _assign_prop_library_asset(db, project_id, character_id, row.library_asset_id)
    return {
        "id": row.id,
        "name": row.name,
        "approval_status": row.approval_status,
        "library_asset_id": row.library_asset_id,
    }


def generate_prop_image(
    db: Session, project_id: str, character_id: str, prop_id: str
) -> dict[str, Any]:
    """Enqueue a single reference-locked image job for a prop.

    Reuses the existing image-generation enqueue path
    (storyboard_jobs.enqueue_imagegen_job) — does NOT invent a new
    generator. The character's canonical hero_identity sheet is the
    reference (reference-locked via zimage.ref_edit) and the prop
    description is the prompt. Stores the job id on the prop row so the
    frontend can poll get_prop_status.
    """
    from ..db import Asset, Job
    from ..storyboard_jobs import enqueue_imagegen_job

    profile = db.get(CharacterProfileRow, character_id)
    if not profile or profile.project_id != project_id:
        raise _err("NOT_FOUND", "Character Profile not found.", 404)
    row = db.get(CharacterPropRow, prop_id)
    if not row or row.character_profile_id != character_id:
        raise _err("NOT_FOUND", "Prop not found.", 404)

    # Resolve the character's canonical hero_identity sheet (reference).
    hero_asset_id = resolve_approved_reference(db, character_id, "hero_identity")
    if not hero_asset_id:
        raise _err(
            "NO_CHARACTER_SHEET",
            "Generate and approve a Character Sheet first — props are "
            "reference-locked to the character's canonical look.",
            400,
        )
    hero_asset = db.get(Asset, hero_asset_id)
    if not hero_asset or hero_asset.project_id != project_id or hero_asset.kind != "image":
        raise _err("NO_CHARACTER_SHEET", "Character Sheet asset is missing or invalid.", 400)

    # Build a focused prop prompt from the character profile + prop fields.
    profile_out = get_profile(db, project_id, character_id)
    prop_prompt = _build_prop_prompt(profile_out.model_dump(), row)

    body: dict[str, Any] = {
        "prompt": prop_prompt,
        "negative_prompt": (
            "blonde hair, aqua eyes, blue eyes, child, sexualized, low quality, "
            "watermark, collage, grid, multiple views, text"
        ),
        "width": 1024,
        "height": 1024,
        "tag": f"prop_{(row.name or 'prop').replace(' ', '_').lower()}",
        "modelFamilyPreference": "zimage",
        "purpose": "character_prop",
        "presetId": "builtin-character-prop",
        "source_asset_id": hero_asset_id,
        "denoise": 0.68,
        "creativeContext": {
            "objective": "character_prop",
            "characterId": character_id,
            "propId": prop_id,
            "workflowKey": "zimage.ref_edit",
            "referenceAssetId": hero_asset_id,
            "referenceLocked": True,
            "referenceFidelityMode": "zimage_ref_edit",
        },
    }
    job = enqueue_imagegen_job(db, project_id, body)

    # Record the pending job on the prop row.
    row.generation_job_id = job.id  # type: ignore[attr-defined]
    row.approval_status = "draft"
    db.commit()
    return {
        "id": row.id,
        "name": row.name,
        "jobId": job.id,
        "status": job.status,
    }


def get_prop_status(
    db: Session, project_id: str, character_id: str, prop_id: str
) -> dict[str, Any]:
    """Poll a prop generation job and link the output asset when done.

    Returns the prop row plus the live job status and the output asset id
    (with a thumbnail URL) once the job completes. When the job is done the
    prop's library_asset_id is set and the asset is registered as a
    character-associated Library asset (no binary duplication).
    """
    from ..db import Job

    profile = db.get(CharacterProfileRow, character_id)
    if not profile or profile.project_id != project_id:
        raise _err("NOT_FOUND", "Character Profile not found.", 404)
    row = db.get(CharacterPropRow, prop_id)
    if not row or row.character_profile_id != character_id:
        raise _err("NOT_FOUND", "Prop not found.", 404)

    job_id = getattr(row, "generation_job_id", None)
    job_status = None
    output_asset_id = row.library_asset_id

    if job_id:
        job = db.get(Job, job_id)
        if job:
            job_status = job.status
            if job.status == "done" and not row.library_asset_id:
                import json as _json

                params = _json.loads(job.params_json or "{}")
                aid = params.get("output_asset_id")
                if aid:
                    row.library_asset_id = aid
                    db.commit()
                    output_asset_id = aid
                    _assign_prop_library_asset(db, project_id, character_id, aid)
            elif job.status in ("done", "failed", "cancelled"):
                # Clear the pending job pointer once terminal.
                row.generation_job_id = None  # type: ignore[attr-defined]
                db.commit()

    return {
        "id": row.id,
        "name": row.name,
        "prop_type": row.prop_type,
        "description": row.description,
        "library_asset_id": output_asset_id,
        "approval_status": row.approval_status,
        "jobId": job_id,
        "jobStatus": job_status,
    }


def _build_prop_prompt(profile: dict[str, Any], prop_row: CharacterPropRow) -> str:
    """Compose a focused prop-image prompt from the character profile + prop fields.

    The character's canonical identity is preserved (reference-locked); the
    prop description specifies the accessory to render. Keeps the prompt
    concise and creator-language-friendly.
    """
    name = (profile.get("name") or "the character").strip()
    visual = (profile.get("visual_description") or "").strip()
    prop_name = (prop_row.name or "an accessory").strip()
    prop_desc = (prop_row.description or "").strip()
    prop_type = (prop_row.prop_type or "").strip()
    colors = (prop_row.colors or "").strip()
    materials = (prop_row.materials or "").strip()

    bits: list[str] = []
    bits.append(f"A single focused product-style reference image of {prop_name}")
    if prop_type:
        bits.append(f"({prop_type})")
    bits.append(f"for the character {name}.")
    if prop_desc:
        bits.append(prop_desc)
    if materials:
        bits.append(f"Materials: {materials}.")
    if colors:
        bits.append(f"Colors: {colors}.")
    if visual:
        bits.append(f"Character visual context: {visual}.")
    bits.append(
        "Reference-locked to the character's canonical look — preserve the "
        "character's identity, skin tone, hair, and style. Clean simple "
        "background, soft studio light, the prop is the clear subject."
    )
    return " ".join(bits)[:1800]


def service_resolve_approved_reference(
    db: Session, character_id: str, role: str = "hero_identity"
) -> str | None:
    """Local alias for resolve_approved_reference (kept here to avoid a
    circular import with the module-level resolve_approved_reference below
    when generate_prop_image is called)."""
    return resolve_approved_reference(db, character_id, role=role)


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
    # Current approved voice stays on the character until the new draft is approved.
    profile.updated_at = now
    db.commit()
    db.refresh(row)
    return row, True


def _provider_binding(lineage: Any) -> dict[str, Any]:
    if not isinstance(lineage, dict):
        return {}
    binding = lineage.get("providerBinding")
    return binding if isinstance(binding, dict) else {}


def provider_voice_binding(voice: Any) -> dict[str, str] | None:
    """Saved ElevenLabs identity. Display name is never used as the voice id."""
    if isinstance(voice, dict):
        lineage = voice.get("lineage") if isinstance(voice.get("lineage"), dict) else {}
        provider = str(voice.get("provider") or "")
        name = str(voice.get("voiceName") or voice.get("name") or "")
        model = str(voice.get("providerModelId") or voice.get("model_id") or "")
        explicit = str(voice.get("providerVoiceId") or "")
    else:
        lineage = _loads(getattr(voice, "lineage_json", None), {})
        provider = str(getattr(voice, "provider", "") or "")
        name = str(getattr(voice, "name", "") or "")
        model = str(getattr(voice, "model_id", "") or "")
        explicit = ""
    binding = _provider_binding(lineage)
    provider_id = str(binding.get("provider") or provider or "").strip().lower()
    voice_id = str(binding.get("providerVoiceId") or explicit or "").strip()
    if provider_id != "elevenlabs" or not voice_id:
        return None
    return {
        "provider": "elevenlabs",
        "providerVoiceId": voice_id,
        "voiceName": str(binding.get("voiceName") or name or ""),
        "providerModelId": str(binding.get("providerModelId") or model or ""),
    }


def _character_voice_rows(db: Session, character_id: str) -> list[VoiceProfileRow]:
    return (
        db.query(VoiceProfileRow)
        .filter(VoiceProfileRow.character_profile_id == character_id)
        .order_by(VoiceProfileRow.version_number.desc())
        .all()
    )


def _row_is_elevenlabs(row: VoiceProfileRow) -> bool:
    if str(getattr(row, "provider", "") or "").strip().lower() == "elevenlabs":
        return True
    return provider_voice_binding(row) is not None


def unassign_active_voice(db: Session, project_id: str, character_id: str) -> dict[str, Any]:
    """Clear the character's current voice. Saved profiles and audio stay."""

    profile = _require_visible_profile(db, project_id, character_id)
    profile.active_voice_profile_id = None
    profile.updated_at = _now()
    db.commit()
    return active_voice_authority(db, project_id, character_id)


def active_voice_authority(db: Session, project_id: str, character_id: str) -> dict[str, Any]:
    """The character's one active voice. No pointer means no Character Voice."""
    profile = _require_visible_profile(db, project_id, character_id)
    active: dict[str, Any] | None = None
    if profile.active_voice_profile_id:
        row = db.get(VoiceProfileRow, profile.active_voice_profile_id)
        if row and row.character_profile_id == character_id:
            active = voice_to_dict(row, character_name=profile.name)
    binding = provider_voice_binding(active) if active else None
    reference_id = str((active or {}).get("approvedVoiceReferenceAssetId") or "")
    if active is None:
        provider = ""
    elif binding:
        provider = "elevenlabs"
    else:
        provider = "local"
    return {
        "provider": provider,
        "activeVoiceProfileId": profile.active_voice_profile_id or "",
        "voiceName": (binding or {}).get("voiceName") or (active or {}).get("name") or "",
        "providerVoiceId": (binding or {}).get("providerVoiceId") or "",
        "providerModelId": (binding or {}).get("providerModelId") or (active or {}).get("model_id") or "",
        "approvedVoiceReferenceAssetId": reference_id,
        "approvedVoiceReferenceAssetName": voice_reference_asset_name(db, reference_id),
        "approved": bool(
            active
            and (
                binding
                or str(active.get("approval_status") or "").lower() == "approved"
            )
        ),
        "activeVoice": active,
    }


def voice_reference_asset_name(db: Session, asset_id: str) -> str:
    """Creator-facing name for a voice-reference Library asset (tag or filename)."""
    if not asset_id:
        return ""
    asset = db.get(Asset, str(asset_id))
    if asset is None:
        return ""
    return str(getattr(asset, "tag", "") or getattr(asset, "filename", "") or "")


def set_approved_voice_reference(
    db: Session,
    project_id: str,
    character_id: str,
    *,
    asset_id: str,
) -> dict[str, Any]:
    """Point the active voice profile at an approved Library audio asset.

    The file stays in the Library. Only its asset id is stored on the voice.
    When the character has no saved voice yet, a minimal approved LIBRARY
    VoiceProfileRow is created to carry the reference — still the canonical
    voice store, never a parallel database. An existing active voice keeps
    its provider binding untouched; only the reference pointer is attached.
    """
    profile = _require_visible_profile(db, project_id, character_id)
    asset = db.get(Asset, str(asset_id))
    if asset is None:
        raise _err("ASSET_NOT_FOUND", "That audio is not in the Library.", 404)
    if str(asset.project_id) not in {str(profile.project_id), str(project_id)}:
        raise _err("ASSET_NOT_IN_PROJECT", "That audio belongs to another project.", 400)
    if str(getattr(asset, "kind", "") or "") != "audio":
        raise _err("ASSET_NOT_AUDIO", "Choose an audio asset for the voice reference.", 400)
    row: VoiceProfileRow | None = None
    if profile.active_voice_profile_id:
        candidate = db.get(VoiceProfileRow, profile.active_voice_profile_id)
        if candidate is not None and candidate.character_profile_id == character_id:
            row = candidate
    now = _now()
    if row is None:
        row = VoiceProfileRow(
            id=str(uuid.uuid4()),
            project_id=str(profile.project_id),
            character_profile_id=character_id,
            version_number=_next_voice_version_number(db, character_id),
            name=str(asset.tag or asset.filename or "Library voice"),
            source_mode="LIBRARY",
            provider="",
            model_id="",
            status="APPROVED",
            approval_status="approved",
            approved_preview_asset_id=asset.id,
            created_at=now,
            updated_at=now,
            approved_at=now,
        )
        db.add(row)
        profile.active_voice_profile_id = row.id
        profile.updated_at = now
    row.approved_voice_reference_asset_id = asset.id
    row.updated_at = now
    db.commit()
    return {
        "ok": True,
        "characterId": character_id,
        "voiceProfileId": row.id,
        "approvedVoiceReferenceAssetId": asset.id,
        "approvedVoiceReferenceAssetName": voice_reference_asset_name(db, asset.id),
        "mock": False,
    }


def assign_provider_voice(
    db: Session,
    project_id: str,
    character_id: str,
    *,
    provider_voice_id: str,
    voice_name: str = "",
    model_id: str = "",
    voice_profile_id: str | None = None,
) -> dict[str, Any]:
    """Approve an ElevenLabs voice profile and make it the character's active voice.

    A Local profile is never rewritten. Switching back to Local reactivates that row.
    """
    profile = _require_visible_profile(db, project_id, character_id)
    vid = (provider_voice_id or "").strip()
    if not vid:
        raise _err("ELEVENLABS_VALIDATION", "Choose an ElevenLabs voice before saving.", 400)
    rows = _character_voice_rows(db, character_id)
    row = None
    if voice_profile_id:
        candidate = get_voice_or_none(db, project_id, character_id, voice_profile_id)
        if candidate and _row_is_elevenlabs(candidate):
            row = candidate
    if row is None:
        row = next((item for item in rows if _row_is_elevenlabs(item)), None)
    now = _now()
    if row is None:
        row = VoiceProfileRow(
            id=str(uuid.uuid4()),
            project_id=str(profile.project_id),
            character_profile_id=character_id,
            version_number=_next_voice_version_number(db, character_id),
            name=voice_name or "ElevenLabs voice",
            source_mode="PROVIDER",
            provider="elevenlabs",
            model_id=model_id or "",
            status="APPROVED",
            approval_status="approved",
            created_at=now,
            updated_at=now,
            approved_at=now,
        )
        db.add(row)
    lineage = _loads(row.lineage_json, {})
    lineage["providerBinding"] = {
        "provider": "elevenlabs",
        "providerVoiceId": vid,
        "voiceName": voice_name or row.name or "",
        "providerModelId": model_id or row.model_id or "",
    }
    row.provider = "elevenlabs"
    row.source_mode = row.source_mode or "PROVIDER"
    row.status = "APPROVED"
    row.approval_status = "approved"
    row.approved_at = row.approved_at or now
    if model_id:
        row.model_id = model_id
    if voice_name:
        row.name = voice_name
    row.lineage_json = json.dumps(lineage, ensure_ascii=False)
    row.updated_at = now
    profile.active_voice_profile_id = row.id
    profile.updated_at = now
    db.commit()
    db.refresh(row)
    return voice_to_dict(row, character_name=profile.name)


def activate_voice_provider(
    db: Session,
    project_id: str,
    character_id: str,
    provider: str,
) -> dict[str, Any]:
    """Point the character at one saved provider without deleting the other."""
    chosen = (provider or "").strip().lower()
    if chosen not in {"local", "elevenlabs"}:
        raise _err("VOICE_PROVIDER_INVALID", "Choose Local or ElevenLabs.", 400)
    profile = _require_visible_profile(db, project_id, character_id)
    rows = _character_voice_rows(db, character_id)
    now = _now()
    if chosen == "elevenlabs":
        row = next((item for item in rows if _row_is_elevenlabs(item) and provider_voice_binding(item)), None)
        if row is None:
            raise _err(
                "CHARACTER_VOICE_NOT_ASSIGNED",
                "Choose an ElevenLabs voice and save it to this character.",
                400,
            )
        if str(row.approval_status or "").lower() != "approved":
            row.status = "APPROVED"
            row.approval_status = "approved"
            row.approved_at = now
            row.updated_at = now
        profile.active_voice_profile_id = row.id
    else:
        local = next(
            (
                item
                for item in rows
                if not _row_is_elevenlabs(item) and str(item.approval_status or "").lower() == "approved"
            ),
            None,
        )
        profile.active_voice_profile_id = local.id if local else None
    profile.updated_at = now
    db.commit()
    return active_voice_authority(db, project_id, character_id)


def generate_elevenlabs_sample(
    db: Session,
    project_id: str,
    character_id: str,
    *,
    text: str,
    provider_voice_id: str,
    model_id: str = "",
    voice_name: str = "",
) -> dict[str, Any]:
    """Playable sample through the direct ElevenLabs adapter. Does not change the saved voice."""
    _require_visible_profile(db, project_id, character_id)
    spoken = (text or "").strip()
    voice_id = (provider_voice_id or "").strip()
    if not spoken:
        raise _err("ELEVENLABS_VALIDATION", "Enter a line to hear this voice.", 400)
    if not voice_id:
        raise _err("CHARACTER_VOICE_NOT_ASSIGNED", "Choose an ElevenLabs voice first.", 400)
    from ..generation_tools.lineage import register_derived_asset
    from ..hosted_providers.adapters.elevenlabs_routed import generate_tts_routed

    try:
        generated = generate_tts_routed(
            text=spoken,
            voice_id=voice_id,
            model_id=(model_id or "").strip() or None,
            surface="voice-studio.sample",
        )
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        message = str(detail.get("message") or "ElevenLabs is currently unavailable. Check your API configuration in Setup.")
        raise _err(str(detail.get("code") or "ELEVENLABS_UNAVAILABLE"), message, int(exc.status_code or 400)) from exc
    proven = dict(generated.get("provenance") or {})
    proven.pop("apiKey", None)
    asset = register_derived_asset(
        db,
        project_id=project_id,
        source_path=generated["path"],
        kind="audio",
        tag="voice",
        parent_asset_id=None,
        op="voice_sample_elevenlabs",
        model=str(generated.get("model") or ""),
        prompt_meta={
            "prompt": spoken,
            "localProvider": False,
            "cloudPaid": True,
            "libraryClass": "audio",
            "audioRole": "voice-sample",
            "voiceName": voice_name,
            "characterId": character_id,
            **proven,
        },
        library_key="audio.voice",
    )
    remembered = remember_voice_sample(
        db,
        project_id,
        character_id,
        asset_id=asset.id,
        provider="elevenlabs",
        provider_voice_id=voice_id,
        model_id=(model_id or "").strip(),
        voice_name=voice_name,
        sample_name=voice_name or "ElevenLabs sample",
    )
    db.commit()
    return {
        "assetId": asset.id,
        "provider": "elevenlabs",
        "voiceName": voice_name,
        "voiceProfileId": remembered["voiceProfileId"],
        "candidateId": remembered["candidateId"],
        "directApi": True,
        "mock": False,
    }


def remember_voice_sample(
    db: Session,
    project_id: str,
    character_id: str,
    *,
    asset_id: str,
    provider: str,
    provider_voice_id: str = "",
    model_id: str = "",
    voice_name: str = "",
    sample_name: str = "",
    accent: str = "",
) -> dict[str, Any]:
    """Keep a playable sample on the character without making it the current voice."""

    profile = _require_visible_profile(db, project_id, character_id)
    chosen = (provider or "").strip().lower()
    rows = _character_voice_rows(db, character_id)
    if chosen == "elevenlabs":
        row = next((item for item in rows if _row_is_elevenlabs(item)), None)
    else:
        row = next((item for item in rows if not _row_is_elevenlabs(item)), None)
    now = _now()
    if row is None:
        row = VoiceProfileRow(
            id=str(uuid.uuid4()),
            project_id=str(profile.project_id),
            character_profile_id=character_id,
            version_number=_next_voice_version_number(db, character_id),
            name=voice_name or ("ElevenLabs voice" if chosen == "elevenlabs" else "Voice"),
            source_mode="PROVIDER" if chosen == "elevenlabs" else "DESIGN",
            provider="elevenlabs" if chosen == "elevenlabs" else (provider or "local"),
            model_id=model_id or "",
            accent=accent or "",
            status="DRAFT",
            approval_status="draft",
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        db.flush()
    lineage = _loads(row.lineage_json, {})
    if (
        chosen == "elevenlabs"
        and provider_voice_id
        and str(row.approval_status or "").lower() != "approved"
    ):
        lineage["providerBinding"] = {
            "provider": "elevenlabs",
            "providerVoiceId": provider_voice_id,
            "voiceName": voice_name or row.name or "",
            "providerModelId": model_id or row.model_id or "",
        }
        row.provider = "elevenlabs"
        if model_id:
            row.model_id = model_id
        if voice_name and str(row.approval_status or "").lower() != "approved":
            row.name = voice_name
    if accent and not row.accent:
        row.accent = accent
    meta = list(lineage.get("candidatesMeta") or [])
    candidate_id = str(uuid.uuid4())
    meta.append(
        {
            "id": candidate_id,
            "name": sample_name or f"Sample {len(meta) + 1}",
            "assetId": asset_id,
            "status": "ready",
            "provider": "elevenlabs" if chosen == "elevenlabs" else "local",
            "providerVoiceId": provider_voice_id,
            "modelId": model_id,
            "accent": accent,
            "createdAt": now,
        }
    )
    lineage["candidatesMeta"] = meta
    row.lineage_json = json.dumps(lineage, ensure_ascii=False)
    row.updated_at = now
    db.flush()
    return {"voiceProfileId": row.id, "candidateId": candidate_id}


def _sample_from_candidate(row: VoiceProfileRow, candidate: dict[str, Any]) -> dict[str, Any] | None:
    asset_id = str(candidate.get("assetId") or candidate.get("asset_id") or "")
    candidate_id = str(candidate.get("id") or "")
    if not asset_id or not candidate_id:
        return None
    if str(candidate.get("status") or "").lower() == "rejected":
        return None
    return {
        "id": candidate_id,
        "assetId": asset_id,
        "status": str(candidate.get("status") or "ready"),
        "provider": str(candidate.get("provider") or row.provider or ""),
        "providerVoiceId": str(candidate.get("providerVoiceId") or ""),
        "modelId": str(candidate.get("modelId") or ""),
        "name": str(candidate.get("name") or ""),
        "voiceProfileId": row.id,
        "createdAt": str(candidate.get("createdAt") or ""),
        "orphan": False,
    }


def character_playable_samples(db: Session, project_id: str, character_id: str) -> list[dict[str, Any]]:
    """Saved candidates plus generated ElevenLabs audio that was not linked yet."""

    _require_visible_profile(db, project_id, character_id)
    rows = _character_voice_rows(db, character_id)
    bound_voice_ids: set[str] = set()
    samples: list[dict[str, Any]] = []
    seen_assets: set[str] = set()
    for row in rows:
        lineage = _loads(row.lineage_json, {})
        binding = _provider_binding(lineage)
        voice_id = str(binding.get("providerVoiceId") or "")
        if voice_id:
            bound_voice_ids.add(voice_id)
        for candidate in list(lineage.get("candidatesMeta") or []):
            if not isinstance(candidate, dict):
                continue
            sample = _sample_from_candidate(row, candidate)
            if not sample or sample["assetId"] in seen_assets:
                continue
            seen_assets.add(sample["assetId"])
            samples.append(sample)
    assets = (
        db.query(Asset)
        .filter(Asset.project_id == project_id, Asset.kind == "audio", Asset.tag == "voice")
        .all()
    )
    for asset in assets:
        if asset.id in seen_assets:
            continue
        meta = _loads(asset.prompt_meta_json, {})
        if str(meta.get("op") or "") != "voice_sample_elevenlabs":
            continue
        owner = str(meta.get("characterId") or "")
        voice_id = str(meta.get("providerVoiceId") or "")
        if owner and owner != character_id:
            continue
        if not owner and voice_id not in bound_voice_ids:
            continue
        seen_assets.add(asset.id)
        created = asset.created_at.isoformat() if asset.created_at else ""
        samples.append(
            {
                "id": "",
                "assetId": asset.id,
                "status": "ready",
                "provider": "elevenlabs",
                "providerVoiceId": voice_id,
                "modelId": str(meta.get("model") or meta.get("providerModelId") or ""),
                "name": str(meta.get("voiceName") or "ElevenLabs sample"),
                "voiceProfileId": "",
                "createdAt": created,
                "orphan": True,
            }
        )
    samples.sort(key=lambda item: str(item.get("createdAt") or ""), reverse=True)
    return samples


def approve_generated_voice_asset(
    db: Session,
    project_id: str,
    character_id: str,
    asset_id: str,
    *,
    approved_by: str = "owner",
) -> dict[str, Any]:
    """Approve one generated sample. Link it first when generation stored only the audio."""

    from .voice_creator import approve_voice_candidate

    wanted = (asset_id or "").strip()
    if not wanted:
        raise _err("NOT_FOUND", "That sample could not be found.", 404)
    _require_visible_profile(db, project_id, character_id)
    rows = _character_voice_rows(db, character_id)
    for row in rows:
        lineage = _loads(row.lineage_json, {})
        for candidate in list(lineage.get("candidatesMeta") or []):
            if str(candidate.get("assetId") or "") != wanted:
                continue
            return approve_voice_candidate(
                db,
                project_id,
                character_id,
                row.id,
                candidate_id=str(candidate.get("id") or ""),
                approved_by=approved_by,
            )
    asset = db.get(Asset, wanted)
    if asset is None or str(asset.project_id) != str(project_id):
        raise _err("NOT_FOUND", "That sample could not be found.", 404)
    meta = _loads(asset.prompt_meta_json, {})
    if str(meta.get("op") or "") != "voice_sample_elevenlabs":
        raise _err("INVALID_STATUS", "Only a generated voice sample can be approved this way.", 400)
    owner = str(meta.get("characterId") or "")
    voice_id = str(meta.get("providerVoiceId") or "")
    bound_voice_ids = {
        str(_provider_binding(_loads(row.lineage_json, {})).get("providerVoiceId") or "")
        for row in rows
    }
    bound_voice_ids.discard("")
    if owner and owner != character_id:
        raise _err("NOT_FOUND", "That sample belongs to another character.", 404)
    if not owner and voice_id not in bound_voice_ids:
        raise _err("NOT_FOUND", "That sample is not one of this character's generated voices.", 404)
    remembered = remember_voice_sample(
        db,
        project_id,
        character_id,
        asset_id=wanted,
        provider="elevenlabs",
        provider_voice_id=voice_id,
        model_id=str(meta.get("model") or meta.get("providerModelId") or ""),
        voice_name=str(meta.get("voiceName") or ""),
        sample_name=str(meta.get("voiceName") or "ElevenLabs sample"),
    )
    db.commit()
    return approve_voice_candidate(
        db,
        project_id,
        character_id,
        remembered["voiceProfileId"],
        candidate_id=remembered["candidateId"],
        approved_by=approved_by,
    )


def voice_to_dict(row: VoiceProfileRow, *, character_name: str = "") -> dict[str, Any]:
    lineage = _loads(row.lineage_json, {})
    return {
        "id": row.id,
        "project_id": row.project_id,
        "character_profile_id": row.character_profile_id,
        "characterId": row.character_profile_id,
        "character_id": row.character_profile_id,
        "characterName": character_name,
        "sourceType": row.source_mode,
        "character_version_id": row.character_version_id,
        "version_number": row.version_number,
        "name": row.name,
        "source_mode": row.source_mode,
        "provider": row.provider,
        "model_id": row.model_id,
        "providerVoiceId": _provider_binding(lineage).get("providerVoiceId") or "",
        "voiceName": _provider_binding(lineage).get("voiceName") or row.name,
        "providerModelId": _provider_binding(lineage).get("providerModelId") or row.model_id,
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
        "approvedVoiceReferenceAssetId": row.approved_voice_reference_asset_id,
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


def require_voice_for_character(
    db: Session, project_id: str, character_id: str, voice_id: str
) -> VoiceProfileRow:
    """Resolve a voice that belongs to a visible character.

    Voice rows live on the character's home project. A Global character may be
    viewed from another project without copying the Voice Profile.
    """
    profile = _require_visible_profile(db, project_id, character_id)
    row = db.get(VoiceProfileRow, voice_id)
    if not row or row.character_profile_id != character_id:
        raise _err("NOT_FOUND", "Voice Profile not found.", 404)
    home = str(profile.project_id)
    if str(row.project_id) not in {home, str(project_id)}:
        raise _err("NOT_FOUND", "Voice Profile not found.", 404)
    return row


def get_voice_or_none(
    db: Session, project_id: str, character_id: str, voice_id: str
) -> VoiceProfileRow | None:
    try:
        return require_voice_for_character(db, project_id, character_id, voice_id)
    except HTTPException:
        return None


def list_voice_profiles(db: Session, project_id: str, character_id: str) -> list[dict[str, Any]]:
    profile = _require_visible_profile(db, project_id, character_id)
    rows = (
        db.query(VoiceProfileRow)
        .filter(VoiceProfileRow.character_profile_id == character_id)
        .order_by(VoiceProfileRow.version_number.asc())
        .all()
    )
    return [voice_to_dict(r, character_name=profile.name) for r in rows]


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
    """Approve a draft Voice Profile, or rebind current to an already-approved one.

    Approved profile *contents* stay immutable. The character's
    ``active_voice_profile_id`` is the mutable current/default pointer.
    """
    require_owned_profile(db, project_id, character_id)
    vp = require_voice_for_character(db, project_id, character_id, voice_id)
    now = _now()
    already_approved = str(vp.approval_status or "").lower() == "approved"
    if not already_approved:
        vp.status = "APPROVED"
        vp.approval_status = "approved"
        vp.approved_at = now
        vp.updated_at = now
    profile = db.get(CharacterProfileRow, character_id)
    if profile:
        profile.active_voice_profile_id = voice_id
        profile.updated_at = now
    db.commit()
    return voice_to_dict(vp, character_name=(profile.name if profile else ""))


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


def delete_profile(
    db: Session,
    project_id: str,
    character_id: str,
    *,
    confirm_cross_project: bool = False,
) -> dict[str, Any]:
    """Permanently delete a character profile and all owned child records.

    This deletes ONLY character-owned rows from the character_identity schema.
    Shared project assets (Library images, Voice Studio voices) are NOT
    automatically deleted — they remain as reusable project resources.

    Returns the deleted character's name for confirmation UI.
    """
    row = db.get(CharacterProfileRow, character_id)
    if not row or row.project_id != project_id:
        raise _err("NOT_FOUND", "Character Profile not found.", 404)

    slug = (row.slug or "").strip().lower()
    name_key = (row.name or "").strip().lower()
    if slug == "korri" or name_key == "korri":
        raise _err("PROTECTED_CHARACTER", "Korri cannot be deleted.", 409)

    from ..creator_scope.contract import ENTITY_CHARACTER, CreatorScopeError
    from ..creator_scope.service import delete_scope, mark_entity_deleted, require_delete_safety

    try:
        require_delete_safety(
            db,
            entity_type=ENTITY_CHARACTER,
            entity_id=character_id,
            owning_project_id=project_id,
            is_global=_character_is_global(row),
            confirm_cross_project=confirm_cross_project,
        )
    except CreatorScopeError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.as_detail()) from exc

    name = row.name

    try:
        from ..continuity.models import VisualIdentityRow

        for ident in (
            db.query(VisualIdentityRow)
            .filter(VisualIdentityRow.character_profile_id == character_id)
            .all()
        ):
            ident.character_profile_id = None
            ident.archived = True
            ident.status = "archived"
            ident.updated_at = _now()
    except Exception:
        pass

    try:
        from ..scene_references.models import SceneReferenceBinding

        now_dt = datetime.now(timezone.utc)
        bind_q = db.query(SceneReferenceBinding).filter(
            SceneReferenceBinding.identity_id == character_id,
        )
        if not _character_is_global(row):
            bind_q = bind_q.filter(SceneReferenceBinding.project_id == project_id)
        for binding in bind_q.all():
            binding.identity_id = None
            binding.enabled = False
            if getattr(binding, "deleted_at", None) is None:
                binding.deleted_at = now_dt
            binding.updated_by = "character-delete"
    except Exception:
        pass

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

    mark_entity_deleted(
        db,
        entity_type=ENTITY_CHARACTER,
        entity_id=character_id,
        owning_project_id=project_id,
    )
    db.delete(row)
    db.commit()
    delete_scope(db, entity_type=ENTITY_CHARACTER, entity_id=character_id)

    try:
        from ..codirector.conversation.project_cache import invalidate_cache_sections

        invalidate_cache_sections(db, project_id, ["characters"])
    except Exception:
        pass

    return {"deleted": True, "name": name}
