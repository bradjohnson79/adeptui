"""Canonical Environment Creator save — create or update one ERS entity.

Save persists the Environment Creator form. It does not generate, regenerate,
or detach an existing ERS composite image.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..creator_scope.contract import canonical_tag, normalize_is_global
from .contracts import EnvironmentReferenceSheet, utc_now
from .orchestrator import create_sheet
from .store import (
    check_environment_tag_collision,
    list_sheets,
    load_sheet,
    save_sheet,
    sheet_is_global,
    sync_environment_scope,
)


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def build_environment_creator_plan(payload: dict[str, Any]) -> dict[str, Any]:
    nested = _as_dict(payload.get("plan"))
    name = str(payload.get("name") or nested.get("name") or "").strip()
    prompt = str(
        payload.get("environmentPrompt")
        or payload.get("description")
        or nested.get("environmentPrompt")
        or nested.get("description")
        or ""
    ).strip()
    ref = str(
        payload.get("referenceImageAssetId")
        or nested.get("referenceImageAssetId")
        or ""
    ).strip()
    story = payload.get("storyTheme")
    if story is None:
        story = nested.get("storyTheme")
    aspect = str(payload.get("aspectRatio") or nested.get("aspectRatio") or "16:9").strip() or "16:9"
    generator = str(payload.get("generator") or nested.get("generator") or "gpt-image-2").strip() or "gpt-image-2"
    characters = _as_list(payload.get("characters") if payload.get("characters") is not None else nested.get("characters"))
    props = _as_list(payload.get("props") if payload.get("props") is not None else nested.get("props"))
    return {
        "name": name,
        "isGlobal": bool(
            normalize_is_global(
                payload.get("isGlobal") if payload.get("isGlobal") is not None else payload.get("is_global"),
                default=bool(nested.get("isGlobal") or nested.get("is_global") or False),
            )
        ),
        "environmentPrompt": prompt,
        "referenceImageAssetId": ref or None,
        "storyTheme": story,
        "aspectRatio": aspect,
        "generator": generator,
        "characters": characters,
        "props": props,
    }


def apply_environment_creator_plan(sheet: EnvironmentReferenceSheet, plan: dict[str, Any]) -> EnvironmentReferenceSheet:
    """Write form fields onto an existing sheet without touching the composite."""
    name = str(plan.get("name") or sheet.name or "").strip() or sheet.name
    prompt = str(plan.get("environmentPrompt") or "").strip()
    description = prompt or sheet.description
    next_global = normalize_is_global(plan.get("isGlobal"), default=sheet_is_global(sheet))

    preserved_composite = getattr(sheet, "ers_composite_asset_id", None)
    sheet.name = name
    sheet.description = description
    sheet.isGlobal = bool(next_global)
    sheet.updatedAt = utc_now()

    profile = sheet.profile
    profile.environmentName = name
    profile.description = description
    story = plan.get("storyTheme")
    if isinstance(story, dict):
        theme_label = str(story.get("override") or story.get("label") or "").strip()
    else:
        theme_label = str(story or "").strip()
    if theme_label:
        profile.storyPurpose = theme_label
    profile.creatorNotes = (
        f"aspect={plan.get('aspectRatio') or '16:9'}; "
        f"generator={plan.get('generator') or 'gpt-image-2'}; "
        f"characters={len(_as_list(plan.get('characters')))}; "
        f"props={len(_as_list(plan.get('props')))}"
    )

    details = _as_dict(getattr(sheet.provenance, "details", None))
    details["environmentCreatorPlan"] = plan
    sheet.provenance.details = details
    sheet.provenance.actor = "creator"
    if not str(getattr(sheet.provenance, "note", "") or "").strip():
        sheet.provenance.note = "Environment Creator save"

    if getattr(sheet, "composition", None) is not None:
        sheet.composition.sheetTitle = name

    sheet.ers_composite_asset_id = preserved_composite
    return sheet


def _resolve_existing_sheet(
    db: Session,
    *,
    project_id: str,
    sheet_id: str | None,
    name: str,
) -> EnvironmentReferenceSheet | None:
    sid = str(sheet_id or "").strip()
    if sid:
        from .store import load_visible_sheet

        sheet = load_visible_sheet(db, project_id, sid) or load_sheet(project_id, sid)
        if sheet is not None:
            if sheet.projectId != project_id:
                raise PermissionError("Global environments can only be edited from the project that created them.")
            return sheet
    return None


def upsert_environment_creator_sheet(
    db: Session,
    *,
    project_id: str,
    payload: dict[str, Any],
) -> tuple[EnvironmentReferenceSheet, bool]:
    plan = build_environment_creator_plan(payload)
    name = str(plan.get("name") or "").strip()
    if not name:
        raise ValueError("Give the environment a name, then Save Environment.")

    raw_sheet_id = str(payload.get("sheetId") or payload.get("sheet_id") or "").strip() or None
    existing = _resolve_existing_sheet(db, project_id=project_id, sheet_id=raw_sheet_id, name=name)
    created = existing is None
    next_global = bool(plan.get("isGlobal"))

    try:
        check_environment_tag_collision(
            db,
            project_id=project_id,
            name=name,
            exclude_id=existing.sheetId if existing is not None else "",
            making_global=next_global,
        )
    except ValueError:
        raise

    from ..creator_scope.identity_tag import looks_like_collision_alias, prompt_canonical_tag

    if existing is None:
        sheet = create_sheet(
            project_id=project_id,
            name=name,
            description=str(plan.get("environmentPrompt") or "") or name,
            is_global=next_global,
        )
        sheet.canonicalTag = prompt_canonical_tag("environment", name)
    else:
        sheet = existing
        renamed = name != (existing.name or "").strip()
        stored = str(getattr(sheet, "canonicalTag", "") or "").strip()
        if renamed:
            sheet.canonicalTag = prompt_canonical_tag("environment", name)
        elif not stored or looks_like_collision_alias(stored, name):
            sheet.canonicalTag = prompt_canonical_tag("environment", name, stored)

    apply_environment_creator_plan(sheet, plan)
    save_sheet(sheet)
    sync_environment_scope(db, sheet)
    return sheet, created
