"""Project-level Prop Creator — PropEntity profiles, generate, approve, delete."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ..db import Asset, Job
from ..scene_creator.generation import list_local_generator_families
from ..creator_scope.contract import is_ephemeral_creator_fixture, strip_machine_notes
from ..spatial_map.ers_contracts import (
    GeneratorSourceSelection,
    PropCandidate,
    PropEntity,
    normalize_prop_tag,
)
from ..spatial_map.ers_persistence import (
    delete_prop_entity,
    list_prop_entities,
    load_prop_entities_by_ids,
    load_prop_entity_anywhere,
    load_prop_entity_by_id,
    save_prop_entity,
)
from .generation import (
    api_image_models_configured,
    build_prop_candidate_plans,
    persist_generator_selection,
)
from .prompt import compile_prop_prompt

logger = logging.getLogger(__name__)


class PropCreatorError(Exception):
    def __init__(self, message: str, status_code: int = 400, code: str = "", extra: dict[str, Any] | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.extra = extra or {}


def is_approved(prop: PropEntity) -> bool:
    return bool((prop.approved_asset_id or "").strip())


def visual_identity_id(prop: PropEntity) -> str:
    return (prop.approved_asset_id or "").strip() or (prop.library_asset_id or "").strip()


def _prop_is_global(prop: PropEntity) -> bool:
    return bool(getattr(prop, "is_global", False) or getattr(prop, "isGlobal", False))


def _sync_prop_scope(db: Session, prop: PropEntity) -> None:
    from ..creator_scope.contract import ENTITY_PROP
    from ..creator_scope.service import sync_scope

    sync_scope(
        db,
        entity_type=ENTITY_PROP,
        entity_id=prop.id,
        owning_project_id=prop.project_id,
        is_global=_prop_is_global(prop),
        tag=(prop.canonical_tag or prop.display_label or prop.tag),
        name=prop.display_label or prop.tag,
        identity_asset_id=visual_identity_id(prop),
    )


def _check_prop_tag_collision(
    db: Session,
    *,
    project_id: str,
    tag: str,
    exclude_id: str = "",
    making_global: bool = False,
) -> None:
    from ..creator_scope.contract import ENTITY_PROP, canonical_tag
    from ..creator_scope.service import find_tag_collision

    token = canonical_tag(tag)
    if not token:
        return
    hit = find_tag_collision(
        db,
        entity_type=ENTITY_PROP,
        tag=token,
        exclude_id=exclude_id,
        owning_project_id=project_id,
        making_global=making_global,
    )
    if hit is not None:
        raise PropCreatorError(
            f"#{token} is already used by {hit.name or 'another prop'} "
            f"{'as a Global asset' if hit.is_global else 'in this project'}. Choose a different name.",
            409,
        )
    for prop in list_visible_props(db, project_id):
        if exclude_id and prop.id == exclude_id:
            continue
        other = canonical_tag(prop.tag or prop.display_label).lower()
        if other != token.lower():
            continue
        if prop.project_id == project_id or _prop_is_global(prop) or making_global:
            raise PropCreatorError(
                f"#{token} is already used by {prop.display_label or 'another prop'} "
                f"{'as a Global asset' if _prop_is_global(prop) else 'in this project'}. Choose a different name.",
                409,
            )


def unique_tag(db: Session, project_id: str, label: str, *, exclude_id: str = "") -> str:
    """Internal database slug only. Never generator-facing. Collision suffixes stay here."""
    base = normalize_prop_tag(label)
    tags = {p.tag for p in list_prop_entities(db, project_id) if p.id != exclude_id}
    if base not in tags:
        return base
    for i in range(2, 80):
        candidate = f"{base}-{i}"
        if candidate not in tags:
            return candidate
    return f"{base}-{__import__('uuid').uuid4().hex[:6]}"


def _check_prop_name_collision(
    db: Session,
    *,
    project_id: str,
    name: str,
    exclude_id: str = "",
    making_global: bool = False,
) -> None:
    from ..creator_scope.contract import ENTITY_PROP, CreatorScopeError
    from ..creator_scope.service import require_unique_profile_name

    try:
        require_unique_profile_name(
            db,
            entity_type=ENTITY_PROP,
            name=name,
            owning_project_id=project_id,
            exclude_id=exclude_id,
            making_global=making_global,
        )
    except CreatorScopeError as exc:
        raise PropCreatorError(exc.message, exc.status, exc.code, extra=exc.extra) from exc


def list_visible_props(db: Session, project_id: str) -> list[PropEntity]:
    from ..creator_scope.contract import ENTITY_PROP
    from ..creator_scope.service import list_visible_scope

    local = list_prop_entities(db, project_id)
    for prop in local:
        try:
            _sync_prop_scope(db, prop)
        except Exception:
            pass
    visible = list_visible_scope(db, project_id, entity_type=ENTITY_PROP)
    extra_ids = [row.entity_id for row in visible if row.owning_project_id != project_id and row.is_global]
    extras = [p for p in load_prop_entities_by_ids(db, extra_ids) if _prop_is_global(p)]
    seen: set[str] = {p.id for p in local}
    out = list(local)
    for prop in extras:
        if prop.id in seen:
            continue
        seen.add(prop.id)
        out.append(prop)
    return [p for p in out if not is_ephemeral_creator_fixture(p.display_label or p.tag)]


def list_props(db: Session, project_id: str, *, approved_only: bool = False) -> list[PropEntity]:
    props = list_visible_props(db, project_id)
    if approved_only:
        props = [p for p in props if is_approved(p)]
    props.sort(key=lambda p: (p.display_label or p.tag or "").lower())
    return props


def require_owned_prop(db: Session, project_id: str, prop_id: str) -> PropEntity:
    """Resolve a prop for mutation.

    ORDER 18 Owner law: Global props are editable (save / regenerate PRS) from ANY
    project. Non-global props still require the home project. Delete stays
    home-only via delete_prop(). Compare project ids normalized (strip) to avoid
    false 403 when the current project IS home.
    """
    prop = get_prop(db, project_id, prop_id)
    home = str(prop.project_id or "").strip()
    current = str(project_id or "").strip()
    if home == current:
        return prop
    if _prop_is_global(prop):
        return prop
    raise PropCreatorError(
        "This prop can only be edited from the project that created it.",
        403,
        "OWNER_REQUIRED",
    )


def get_prop(db: Session, project_id: str, prop_id: str) -> PropEntity:
    prop = load_prop_entity_by_id(db, project_id, prop_id)
    if prop is None:
        prop = load_prop_entity_anywhere(db, prop_id)
    if prop is None:
        raise PropCreatorError("Prop not found.", 404)
    if prop.project_id != project_id and not _prop_is_global(prop):
        raise PropCreatorError("Prop not found.", 404)
    owner_id = prop.project_id
    _sanitize_prop_human_fields(prop)
    _sync_candidates(db, owner_id, prop)
    save_prop_entity(db, owner_id, prop)
    if getattr(prop, "mode", "standard") == "advanced":
        from .advanced_service import sync_advanced_on_get

        prop = sync_advanced_on_get(db, owner_id, prop)
    return prop


def _detach_primary_reference(prop: PropEntity) -> None:
    removed = str(prop.reference_asset_id or "").strip()
    prop.reference_asset_id = None
    if not removed:
        return
    if str(prop.library_asset_id or "").strip() == removed:
        prop.library_asset_id = ""
    if str(prop.approved_asset_id or "").strip() == removed:
        prop.approved_asset_id = None
    if str(getattr(prop, "primary_approved_asset_id", "") or "").strip() == removed:
        prop.primary_approved_asset_id = None


def _sanitize_prop_human_fields(prop: PropEntity) -> None:
    prop.description = strip_machine_notes(prop.description)
    notes = strip_machine_notes(prop.notes)
    # Notes are not a second Description. Drop leftover machine-only strings.
    if notes == prop.description:
        prop.notes = ""
    else:
        prop.notes = notes


def create_or_update_prop(
    db: Session,
    project_id: str,
    *,
    prop_id: str = "",
    name: str = "",
    visual_style: str | None = None,
    description: str | None = None,
    reference_asset_id: str | None = None,
    clear_reference: bool = False,
    generator: dict[str, Any] | None = None,
    use_as_identity: bool = False,
    identity_asset_id: str = "",
    mode: str | None = None,
    advanced_type: str | None = None,
    primary_prompt: str | None = None,
    hero_optional: bool | None = None,
    is_global: bool | None = None,
) -> PropEntity:
    existing = None
    if prop_id:
        existing = load_prop_entity_by_id(db, project_id, prop_id) or load_prop_entity_anywhere(db, prop_id)
        if existing is None:
            raise PropCreatorError("Prop not found.", 404)
        # ORDER 18: Global props may be edited from any project; persist on home.
        home = str(existing.project_id or "").strip()
        current = str(project_id or "").strip()
        if home != current and not _prop_is_global(existing):
            raise PropCreatorError(
                "This prop can only be edited from the project that created it.",
                403,
                "OWNER_REQUIRED",
            )
    label = (name or (existing.display_label if existing else "")).strip()
    if not label:
        raise PropCreatorError("Name is required to save a Prop.")
    next_global = _prop_is_global(existing) if existing is not None and is_global is None else bool(is_global)
    prop = existing or PropEntity(project_id=project_id)
    owner_id = prop.project_id or project_id
    _check_prop_name_collision(
        db,
        project_id=owner_id,
        name=label,
        exclude_id=prop.id,
        making_global=next_global,
    )
    renamed = bool(existing) and label != (existing.display_label or "").strip()
    prop.display_label = label
    from ..creator_scope.identity_tag import looks_like_collision_alias, prompt_canonical_tag

    if existing is None:
        if not str(prop.tag or "").strip():
            prop.tag = unique_tag(db, owner_id, label, exclude_id=prop.id)
        prop.canonical_tag = prompt_canonical_tag("prop", label)
    elif renamed:
        # Intentional identity rename: one canonical rewrite. Never mint a collision suffix.
        prop.canonical_tag = prompt_canonical_tag("prop", label)
        if not str(prop.tag or "").strip():
            prop.tag = unique_tag(db, owner_id, label, exclude_id=prop.id)
    else:
        if not str(prop.tag or "").strip():
            prop.tag = unique_tag(db, owner_id, label, exclude_id=prop.id)
        stored = str(prop.canonical_tag or "").strip()
        if not stored or looks_like_collision_alias(stored, label):
            prop.canonical_tag = prompt_canonical_tag("prop", label, stored)
    _check_prop_tag_collision(
        db,
        project_id=owner_id,
        tag=prop.tag,
        exclude_id=prop.id,
        making_global=next_global,
    )
    prop.is_global = next_global
    prop.isGlobal = next_global
    if visual_style is not None:
        prop.visual_style = (visual_style or "").strip()
    if description is not None:
        prop.description = strip_machine_notes(description)
    else:
        prop.description = strip_machine_notes(prop.description)
    _sanitize_prop_human_fields(prop)
    if clear_reference:
        _detach_primary_reference(prop)
    elif reference_asset_id is not None:
        prop.reference_asset_id = (reference_asset_id or "").strip() or None
    if generator:
        prop.generator = GeneratorSourceSelection.model_validate(generator)
    if mode is not None or advanced_type is not None or primary_prompt is not None or hero_optional is not None:
        from .advanced_service import apply_advanced_fields

        apply_advanced_fields(
            prop,
            mode=mode,
            advanced_type=advanced_type,
            primary_prompt=primary_prompt,
            hero_optional=hero_optional,
        )
    save_prop_entity(db, owner_id, prop)
    _sync_prop_scope(db, prop)
    if use_as_identity:
        return use_as_prop_identity(
            db,
            owner_id,
            prop.id,
            asset_id=identity_asset_id or (prop.reference_asset_id or ""),
            source_type="library",
        )
    return prop


def generate_candidates(
    db: Session,
    project_id: str,
    prop_id: str,
    *,
    local_enabled: bool = True,
    api_enabled: bool = False,
    local_family: str = "",
    api_model: str = "",
    candidate_count: int = 4,
    generator_sources: dict[str, Any] | None = None,
) -> PropEntity:
    prop = require_owned_prop(db, project_id, prop_id)
    compiled = compile_prop_prompt(prop)
    has_reference = bool((prop.reference_asset_id or "").strip())
    plans = build_prop_candidate_plans(
        local_enabled=local_enabled,
        api_enabled=api_enabled,
        local_family=local_family,
        api_model=api_model,
        has_reference=has_reference,
        candidate_count=candidate_count,
        generator_sources=generator_sources,
    )
    persisted = persist_generator_selection(
        local_enabled=local_enabled,
        api_enabled=api_enabled,
        local_family=local_family,
        api_model=api_model,
        generator_sources=generator_sources,
    )
    prop.generator = GeneratorSourceSelection.model_validate(persisted)

    prop.candidates = _enqueue_plans(db, project_id, prop, compiled, plans)
    save_prop_entity(db, project_id, prop)
    return prop


def retry_candidate(db: Session, project_id: str, prop_id: str, candidate_id: str) -> PropEntity:
    prop = require_owned_prop(db, project_id, prop_id)
    target = next((c for c in prop.candidates if c.id == candidate_id), None)
    if target is None:
        raise PropCreatorError("Candidate not found.")
    compiled = compile_prop_prompt(prop)
    has_reference = bool((prop.reference_asset_id or "").strip())
    if target.source == "api":
        retry_sources: dict[str, Any] = {
            "local": None,
            "api": [
                {
                    "modelId": target.model or target.family,
                    "model": target.model or target.family,
                    "enabled": True,
                    "batchCount": 1,
                    "generationMode": target.conditioning,
                }
            ],
        }
    else:
        retry_sources = {
            "local": [
                {
                    "modelId": target.family or prop.generator.local_family,
                    "family": target.family or prop.generator.local_family,
                    "enabled": True,
                    "batchCount": 1,
                    "generationMode": target.conditioning,
                }
            ],
            "api": None,
        }
    plans = build_prop_candidate_plans(
        local_enabled=target.source != "api",
        api_enabled=target.source == "api",
        local_family=target.family or prop.generator.local_family,
        api_model=target.model,
        has_reference=has_reference,
        candidate_count=1,
        generator_sources=retry_sources,
    )
    replacements = _enqueue_plans(db, project_id, prop, compiled, plans)
    if replacements:
        replacement = replacements[0]
        replacement.index = target.index
        replacement.take_label = target.take_label
        prop.candidates = [replacement if c.id == candidate_id else c for c in prop.candidates]
        save_prop_entity(db, project_id, prop)
    return prop



def _compose_prs_after_approval(db: Session, project_id: str, prop: PropEntity) -> None:
    try:
        from .prs_compose import compose_and_ingest_prs

        sheet = compose_and_ingest_prs(db, project_id, prop)
    except Exception:
        logger.exception("PRS compose failed for prop %s", prop.id)
        return
    if sheet is None:
        return
    prop.prs_asset_id = sheet.id
    save_prop_entity(db, project_id, prop)


def compose_prop_reference_sheet_for_prop(
    db: Session,
    project_id: str,
    prop_id: str,
) -> tuple[PropEntity, str]:
    """Explicit Basic PRS compose. Uses existing compose_and_ingest_prs; never overwrites approved still."""
    prop = require_owned_prop(db, project_id, prop_id)
    if not str(prop.approved_asset_id or "").strip():
        raise PropCreatorError("Use This Prop first, then create a Prop Reference Sheet.", 400)
    from .prs_compose import compose_and_ingest_prs

    owner_id = prop.project_id
    sheet = compose_and_ingest_prs(db, owner_id, prop)
    if sheet is None:
        raise PropCreatorError("Prop Reference Sheet could not be composed from the approved still.", 400)
    prop.prs_asset_id = sheet.id
    save_prop_entity(db, owner_id, prop)
    return prop, sheet.id


def use_as_prop_identity(
    db: Session,
    project_id: str,
    prop_id: str,
    *,
    asset_id: str = "",
    source_type: str = "library",
) -> PropEntity:
    """Point Prop visual identity at an existing Library/upload asset. No byte copy.

    Sets approved_asset_id = asset_id and mirrors library_asset_id. PropEntity.id
    is unchanged. Does not enqueue generation.
    """
    prop = require_owned_prop(db, project_id, prop_id)
    owner_id = str(prop.project_id or project_id).strip()
    aid = (asset_id or prop.reference_asset_id or "").strip()
    if not aid:
        raise PropCreatorError("Attach a reference image before using it as Prop Identity.")
    asset = db.get(Asset, aid)
    # Asset may live on the prop home project even when editing from another workspace.
    if asset is None or str(asset.project_id or "").strip() not in {owner_id, str(project_id or "").strip()}:
        raise PropCreatorError("Reference asset not found.", 404)
    prev = prop.approved_asset_id
    if prev and prev != aid:
        _set_asset_approval(db, owner_id, prev, approved=False)
    prop.approved_asset_id = aid
    prop.library_asset_id = aid
    _set_asset_approval(db, owner_id, aid, approved=True)
    save_prop_entity(db, owner_id, prop)
    # ORDER 16: PRS is optional / button-driven via compose_prop_reference_sheet_for_prop — do not auto-compose on approve.
    return prop


def upload_identity_from_bytes(
    db: Session,
    project_id: str,
    prop_id: str,
    *,
    data: bytes,
    filename: str = "",
    content_type: str = "",
) -> PropEntity:
    """Basic Prop view upload: Library candidate, not auto-approved."""
    import uuid as _uuid

    from .view_upload import SOURCE_UPLOADED, stamp_prop_view_asset, write_prop_image_asset

    prop = require_owned_prop(db, project_id, prop_id)
    asset = write_prop_image_asset(
        db,
        project_id=project_id,
        prop_id=prop.id,
        prop_name=prop.display_label or prop.tag or "Prop",
        view="primary",
        data=data,
        filename=filename,
        content_type=content_type,
        source=SOURCE_UPLOADED,
    )
    stamp_prop_view_asset(
        db,
        asset,
        project_id=project_id,
        prop_id=prop.id,
        prop_name=prop.display_label or prop.tag or "Prop",
        view="primary",
        source=SOURCE_UPLOADED,
    )
    next_index = len(prop.candidates or [])
    candidate = PropCandidate(
        id=str(_uuid.uuid4()),
        prop_id=prop.id,
        index=next_index,
        job_id="",
        asset_id=asset.id,
        status="complete",
        source="local",
        origin=SOURCE_UPLOADED,
        family="upload",
        model="uploaded",
        provenance_label="Uploaded",
        take_label=f"Uploaded look {next_index + 1}",
        conditioning="description_guided",
    )
    prop.candidates = list(prop.candidates or []) + [candidate]
    save_prop_entity(db, project_id, prop)
    return prop


def adopt_identity_from_asset(
    db: Session,
    project_id: str,
    prop_id: str,
    asset_id: str,
    *,
    source_type: str = "uploaded",
) -> PropEntity:
    """Bind an existing Library image as a Basic identity candidate. Not auto-approved."""
    import uuid as _uuid

    from .view_upload import SOURCE_UPLOADED, stamp_prop_view_asset

    prop = require_owned_prop(db, project_id, prop_id)
    aid = (asset_id or "").strip()
    asset = db.get(Asset, aid) if aid else None
    if asset is None:
        from ..creator_scope.service import resolve_readable_asset

        asset = resolve_readable_asset(db, project_id, aid)
    if asset is None:
        raise PropCreatorError("That picture is not in this project's Library.", 404)
    source = SOURCE_UPLOADED if str(source_type or "").strip().lower() in {"upload", "uploaded", SOURCE_UPLOADED} else SOURCE_UPLOADED
    stamp_prop_view_asset(
        db,
        asset,
        project_id=str(asset.project_id or project_id),
        prop_id=prop.id,
        prop_name=prop.display_label or prop.tag or "Prop",
        view="primary",
        source=source,
    )
    next_index = len(prop.candidates or [])
    candidate = PropCandidate(
        id=str(_uuid.uuid4()),
        prop_id=prop.id,
        index=next_index,
        job_id="",
        asset_id=asset.id,
        status="complete",
        source="local",
        origin=source,
        family="upload",
        model="uploaded",
        provenance_label="Uploaded",
        take_label=f"Uploaded look {next_index + 1}",
        conditioning="description_guided",
    )
    prop.candidates = list(prop.candidates or []) + [candidate]
    save_prop_entity(db, project_id, prop)
    return prop


def approve_candidate(db: Session, project_id: str, prop_id: str, candidate_id: str) -> PropEntity:
    prop = require_owned_prop(db, project_id, prop_id)
    candidate = next((c for c in prop.candidates if c.id == candidate_id), None)
    if candidate is None:
        raise PropCreatorError("Candidate not found.")
    if not (candidate.asset_id or "").strip():
        raise PropCreatorError("That look is not ready yet.")
    prev = prop.approved_asset_id
    if prev and prev != candidate.asset_id:
        _set_asset_approval(db, project_id, prev, approved=False)
    prop.approved_asset_id = candidate.asset_id
    prop.library_asset_id = candidate.asset_id
    _set_asset_approval(db, project_id, candidate.asset_id, approved=True)
    save_prop_entity(db, project_id, prop)
    # ORDER 16: PRS is optional / button-driven via compose_prop_reference_sheet_for_prop — do not auto-compose on approve.
    return prop


def _repoint_scene_shots(db: Session, project_id: str, source_id: str, target_id: str) -> int:
    if source_id == target_id:
        return 0
    try:
        from ..spatial_map.ers_persistence import list_scene_shots, save_scene_shot
    except Exception:
        return 0
    changed_n = 0
    for shot in list_scene_shots(db, project_id):
        changed = False
        ids = list(shot.prop_entity_ids or [])
        if source_id in ids:
            shot.prop_entity_ids = [target_id if item == source_id else item for item in ids]
            if target_id in shot.prop_entity_ids:
                shot.prop_entity_ids = list(dict.fromkeys(shot.prop_entity_ids))
            changed = True
        blocking = getattr(getattr(shot, "take_memory", None), "blocking", None)
        if isinstance(blocking, dict):
            block_ids = list(blocking.get("prop_entity_ids") or [])
            if source_id in block_ids:
                blocking["prop_entity_ids"] = list(
                    dict.fromkeys(target_id if item == source_id else item for item in block_ids)
                )
                changed = True
        if changed:
            save_scene_shot(db, project_id, shot)
            changed_n += 1
    return changed_n


def _repoint_scene_bindings(db: Session, source_id: str, target_id: str) -> int:
    if source_id == target_id:
        return 0
    try:
        from ..scene_references.models import SceneReferenceBinding
    except Exception:
        return 0
    n = 0
    rows = (
        db.query(SceneReferenceBinding)
        .filter(SceneReferenceBinding.identity_id == source_id)
        .all()
    )
    for row in rows:
        row.identity_id = target_id
        n += 1
    if n:
        db.commit()
    return n


def _unlink_scene_bindings(db: Session, project_id: str, prop_id: str, *, is_global: bool) -> int:
    try:
        from ..scene_references.models import SceneReferenceBinding
    except Exception:
        return 0
    now_dt = datetime.now(timezone.utc)
    query = db.query(SceneReferenceBinding).filter(SceneReferenceBinding.identity_id == prop_id)
    if not is_global:
        query = query.filter(SceneReferenceBinding.project_id == project_id)
    n = 0
    for row in query.all():
        row.identity_id = None
        row.enabled = False
        if getattr(row, "deleted_at", None) is None:
            row.deleted_at = now_dt
        row.updated_by = "prop-delete"
        n += 1
    return n


def merge_duplicate_prop(
    db: Session,
    project_id: str,
    *,
    survivor_id: str,
    duplicate_id: str,
) -> dict[str, Any]:
    """Re-point references from a duplicate Prop onto the canonical survivor, then retire the duplicate."""
    survivor = require_owned_prop(db, project_id, survivor_id)
    duplicate = require_owned_prop(db, project_id, duplicate_id)
    shots = _repoint_scene_shots(db, project_id, duplicate.id, survivor.id)
    bindings = _repoint_scene_bindings(db, duplicate.id, survivor.id)
    deleted = delete_prop(db, project_id, duplicate.id, confirm_cross_project=True)
    return {
        "ok": True,
        "survivorId": survivor.id,
        "removedId": duplicate.id,
        "shotsRepointed": shots,
        "bindingsRepointed": bindings,
        "libraryAssetsKept": True,
        "deleted": deleted,
    }


def delete_prop(
    db: Session,
    project_id: str,
    prop_id: str,
    *,
    confirm_cross_project: bool = False,
) -> dict[str, Any]:
    prop = get_prop(db, project_id, prop_id)
    if str(prop.project_id or "").strip() != str(project_id or "").strip():
        raise PropCreatorError("Global props can only be deleted from the project that created them.", 403)
    from ..creator_scope.contract import ENTITY_PROP, CreatorScopeError
    from ..creator_scope.service import delete_scope, require_delete_safety

    try:
        require_delete_safety(
            db,
            entity_type=ENTITY_PROP,
            entity_id=prop.id,
            owning_project_id=project_id,
            is_global=_prop_is_global(prop),
            confirm_cross_project=confirm_cross_project,
        )
    except CreatorScopeError as exc:
        raise PropCreatorError(exc.message, exc.status, exc.code) from exc
    unlinked = _unlink_spatial_props(
        db, project_id, prop.id, is_global=_prop_is_global(prop)
    )
    shots_unlinked = _unlink_scene_shots(
        db, project_id, prop.id, is_global=_prop_is_global(prop)
    )
    bindings_unlinked = _unlink_scene_bindings(
        db, project_id, prop.id, is_global=_prop_is_global(prop)
    )
    deleted = delete_prop_entity(db, project_id, prop.id)
    if deleted is None:
        raise PropCreatorError("Prop not found.", 404)
    delete_scope(db, entity_type=ENTITY_PROP, entity_id=prop.id)
    return {
        "ok": True,
        "prop_id": prop.id,
        "library_assets_kept": True,
        "spatial_unlinked": unlinked,
        "shots_unlinked": shots_unlinked,
        "bindings_unlinked": bindings_unlinked,
    }


def workspace(db: Session, project_id: str, *, prop_id: str = "") -> dict[str, Any]:
    props = list_props(db, project_id)
    selected = None
    if prop_id:
        selected = next((p for p in props if p.id == prop_id), None)
        if selected is None:
            selected = get_prop(db, project_id, prop_id)
            props = list_props(db, project_id)
    return {
        "props": [p.model_dump() for p in props],
        "selected_prop": selected.model_dump() if selected else None,
        "api_generation_available": api_image_models_configured(),
        "local_families": list_local_generator_families(has_reference=False),
    }


def _fail_api_candidate_error(plan: dict[str, Any], detail: str = "") -> str:
    model = plan.get("hosted_model_id") or plan.get("model") or plan.get("model_id") or "unknown"
    provider = plan.get("provider_id") or "unknown provider"
    extra = f" {detail}" if detail else ""
    return (
        f"No certified API route for {model} ({provider}). "
        "This row was not redirected to a local generator. "
        "Add a provider in Setup or pick a discovered cloud model that can execute."
        f"{extra}"
    )


def _enqueue_api_job(db: Session, project_id: str, body: dict[str, Any], plan: dict[str, Any]) -> Any:
    """Run the hosted model or fail this row. Never substitute a local family."""
    from ..storyboard_jobs import enqueue_imagegen_job

    hosted = str(plan.get("hosted_model_id") or plan.get("model_id") or plan.get("model") or "").strip()
    if not hosted:
        raise PropCreatorError(_fail_api_candidate_error(plan, "No modelId was provided."))
    body["source"] = "api"
    body["model"] = hosted
    body["lockModelFamily"] = True
    body["providerPreference"] = "cloud"
    body["hostedModelId"] = hosted
    body.pop("forceWorkflowKey", None)
    body.pop("allow_force_workflow_key", None)
    body.pop("kieImageModelId", None)
    body.pop("falImageModelId", None)
    job = enqueue_imagegen_job(db, project_id, body)
    try:
        params = json.loads(job.params_json or "{}")
    except Exception:
        params = {}
    runtime = params.get("imageRuntime") if isinstance(params.get("imageRuntime"), dict) else {}
    runtime_key = str(runtime.get("workflowKey") or "")
    provider = str(runtime.get("provider") or "").strip().lower()
    cloud_paid = bool(params.get("cloudPaid"))
    hosted_ok = provider in {"kie", "fal"} or bool(params.get("kieImageModelId") or params.get("falImageModelId"))
    already_imagen = runtime_key.startswith("imagen.")
    if not cloud_paid and not hosted_ok and not already_imagen:
        job.status = "failed"
        job.message = (
            "API model " + hosted + " resolved to local workflow " + (runtime_key or "unknown") + "; "
            "refusing silent Comfy/Z-Image substitute."
        )
        db.commit()
        db.refresh(job)
        raise PropCreatorError(job.message)
    return job



def _enqueue_plans(
    db: Session,
    project_id: str,
    prop: PropEntity,
    compiled: dict[str, Any],
    plans: list[dict[str, Any]],
) -> list[PropCandidate]:
    from ..storyboard_jobs import enqueue_imagegen_job

    candidates: list[PropCandidate] = []
    for plan in plans:
        workflow_key = plan.get("workflow_key") or (
            f"{plan['family']}.ref_edit"
            if plan["conditioning"] == "reference_conditioned"
            else f"{plan['family']}.txt2img"
        )
        body: dict[str, Any] = {
            "prompt": compiled["prompt"],
            "negative_prompt": compiled["negative_prompt"],
            "width": 1024,
            "height": 1024,
            "modelFamilyPreference": plan["family"],
            "model": plan.get("model_id") or plan["model"],
            "lockModelFamily": True,
            "seed": plan["seed"],
            "tag": f"prop_{prop.tag or prop.id[:8]}_c{plan['index'] + 1}",
            "purpose": "project_prop",
            "creativeContext": {
                "objective": "project_prop",
                "propId": prop.id,
                "sheetId": "",
                "workflowKey": workflow_key,
                "candidateIndex": plan["index"],
                "conditioning": plan["conditioning"],
                "visualStyle": compiled["visual_style"],
                "providerKind": plan["source"],
                "hostedModelId": plan.get("hosted_model_id"),
                "providerId": plan.get("provider_id") or "",
                "modelId": plan.get("model_id") or plan["model"],
                "batchIndex": plan.get("batch_index") or (plan["index"] + 1),
                "batchOf": plan.get("batch_of") or 1,
            },
        }
        if plan["conditioning"] == "reference_conditioned" and prop.reference_asset_id:
            body["source_asset_id"] = prop.reference_asset_id
            body["denoise"] = 0.55
            ctx = body["creativeContext"]
            ctx["referenceAssetId"] = prop.reference_asset_id
            ctx["referenceLocked"] = True
            ctx["referenceFidelityMode"] = f"{plan['family']}_ref_edit"
        job_id = f"failed_prop_cand_{plan['index']}"
        status = "failed"
        error = ""
        try:
            if plan["source"] == "api":
                job = _enqueue_api_job(db, project_id, body, plan)
                if (job.status or "").lower() in {"failed", "error"}:
                    job_id = job.id
                    error = job.message or _fail_api_candidate_error(plan)
                else:
                    job_id = job.id
                    status = "queued"
                    error = ""
            else:
                body["source"] = "local"
                body["providerPreference"] = "local"
                if workflow_key:
                    body["forceWorkflowKey"] = workflow_key
                    body["allow_force_workflow_key"] = True
                job = enqueue_imagegen_job(db, project_id, body)
                job_id = job.id
                status = "queued"
                error = ""
        except PropCreatorError as exc:
            logger.error("Prop API candidate failed honestly: %s", exc)
            error = str(exc)
        except Exception as exc:
            logger.error("Prop candidate enqueue failed: %s", exc)
            error = str(exc)
            if plan["source"] == "api":
                error = _fail_api_candidate_error(plan, str(exc))
        candidates.append(
            PropCandidate(
                prop_id=prop.id,
                index=plan["index"],
                job_id=job_id,
                status=status,  # type: ignore[arg-type]
                source=plan["source"],
                family=plan["family"],
                model=plan["model"],
                seed=plan["seed"],
                provenance_label=plan["provenance_label"],
                conditioning=plan["conditioning"],
                take_label=f"Look {plan['index'] + 1}",
                error=error,
            )
        )
    return candidates


def _sync_candidates(db: Session, project_id: str, prop: PropEntity) -> None:
    for candidate in prop.candidates:
        aid = str(candidate.asset_id or "").strip()
        # Uploaded / adopted looks have an asset and no generation job. Never
        # mark them failed just because job_id is empty.
        if aid:
            if candidate.status not in {"complete", "failed"}:
                candidate.status = "complete"
            continue
        if candidate.status in {"complete", "failed"} and candidate.asset_id:
            continue
        job_id = candidate.job_id
        if not job_id or job_id.startswith("failed_"):
            candidate.status = "failed"
            continue
        job = db.get(Job, job_id)
        if job is None or job.project_id != project_id:
            continue
        status = (job.status or "").lower()
        if status in {"done", "completed", "complete", "success"}:
            asset_id = _job_asset_id(job)
            candidate.asset_id = asset_id or candidate.asset_id
            if candidate.asset_id:
                candidate.status = "complete"
                if isinstance(getattr(job, "progress", None), (int, float)):
                    candidate.progress = float(job.progress)
            else:
                # Terminal job with no registered asset — fail honestly (never park generating).
                candidate.status = "failed"
                candidate.error = candidate.error or job.message or "Job finished without an output asset."
                if isinstance(getattr(job, "progress", None), (int, float)):
                    candidate.progress = float(job.progress)
        elif status in {"failed", "error", "cancelled"}:
            candidate.status = "failed"
            candidate.error = job.message or candidate.error
        elif status in {"running", "preview"}:
            candidate.status = "generating"
        else:
            candidate.status = "queued"
        # Honest Job.progress / stage / message only - never invent.
        if isinstance(getattr(job, "progress", None), (int, float)):
            candidate.progress = float(job.progress)
        stage = str(getattr(job, "stage", None) or "").strip()
        message = str(getattr(job, "message", None) or "").strip()
        if stage:
            candidate.job_stage = stage
        if message:
            candidate.job_message = message


def _job_asset_id(job: Job) -> str | None:
    try:
        params = json.loads(job.params_json or "{}")
    except Exception:
        params = {}
    asset_id = params.get("output_asset_id")
    return str(asset_id) if asset_id else None


def _set_asset_approval(db: Session, project_id: str, asset_id: str, *, approved: bool) -> None:
    asset = db.get(Asset, asset_id)
    if asset is None or asset.project_id != project_id:
        return
    asset.production_approval = "approved" if approved else "none"
    try:
        labels = json.loads(asset.labels_json or "[]")
    except Exception:
        labels = []
    if not isinstance(labels, list):
        labels = []
    labels = [str(x) for x in labels if x]
    if approved and "approved_prop" not in labels:
        labels.append("approved_prop")
    if not approved:
        labels = [x for x in labels if x != "approved_prop"]
    asset.labels_json = json.dumps(labels)
    db.commit()


def _projects_for_unlink(db: Session, project_id: str, *, is_global: bool) -> list[str]:
    if not is_global:
        return [project_id]
    from ..db import Project

    return [str(row.id) for row in db.query(Project).all() if str(row.id or "").strip()]


def _unlink_scene_shots(
    db: Session, project_id: str, prop_id: str, *, is_global: bool = False
) -> int:
    """Drop a deleted PropEntity id from saved SceneShot lists. Keep the shot."""
    try:
        from ..spatial_map.ers_persistence import list_scene_shots, save_scene_shot
    except Exception:
        return 0
    unlinked = 0
    for pid in _projects_for_unlink(db, project_id, is_global=is_global):
        for shot in list_scene_shots(db, pid):
            changed = False
            ids = list(shot.prop_entity_ids or [])
            if prop_id in ids:
                shot.prop_entity_ids = [item for item in ids if item != prop_id]
                changed = True
            blocking = getattr(getattr(shot, "take_memory", None), "blocking", None)
            if isinstance(blocking, dict):
                block_ids = list(blocking.get("prop_entity_ids") or [])
                if prop_id in block_ids:
                    blocking["prop_entity_ids"] = [item for item in block_ids if item != prop_id]
                    changed = True
            if changed:
                save_scene_shot(db, pid, shot)
                unlinked += 1
    return unlinked


def _unlink_spatial_props(
    db: Session, project_id: str, prop_id: str, *, is_global: bool = False
) -> int:
    try:
        from ..spatial_map.models import SpatialMapDocumentRow
        from ..spatial_map.service import _parse_document, _save_document
    except Exception:
        return 0
    query = db.query(SpatialMapDocumentRow)
    if not is_global:
        query = query.filter(SpatialMapDocumentRow.project_id == project_id)
    unlinked = 0
    for row in query.all():
        doc = _parse_document(row)
        changed = False
        for item in doc.props or []:
            if getattr(item, "propId", None) == prop_id:
                item.propId = None
                changed = True
                unlinked += 1
        if changed:
            _save_document(db, row, doc)
    return unlinked


def _spatial_placements_for_prop(db: Session, project_id: str, prop_id: str) -> int:
    try:
        from ..spatial_map.service import list_documents
        docs = list_documents(db, project_id)
    except Exception:
        return 0
    return sum(1 for doc in docs for item in (doc.props or []) if getattr(item, "propId", None) == prop_id)
