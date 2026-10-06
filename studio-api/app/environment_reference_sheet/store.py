"""JSON storage for Environment Reference Sheets."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import EnvironmentReferenceSheet


def _root() -> Path:
    try:
        from ..config import settings

        base = Path(settings.data_dir)
    except Exception:
        base = Path(__file__).resolve().parents[3] / "data"
    return base / "environment_reference_sheet"


def project_dir(project_id: str) -> Path:
    path = _root() / project_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def sheets_dir(project_id: str) -> Path:
    path = project_dir(project_id) / "sheets"
    path.mkdir(parents=True, exist_ok=True)
    return path


def exports_dir(project_id: str, sheet_id: str) -> Path:
    path = project_dir(project_id) / "exports" / sheet_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return path


def save_sheet(sheet: EnvironmentReferenceSheet) -> Path:
    return _write_json(sheets_dir(sheet.projectId) / f"{sheet.sheetId}.json", sheet.model_dump(mode="json"))


def load_sheet(project_id: str, sheet_id: str) -> EnvironmentReferenceSheet | None:
    payload = _read_json(sheets_dir(project_id) / f"{sheet_id}.json", None)
    if not isinstance(payload, dict):
        return None
    try:
        return EnvironmentReferenceSheet.model_validate(payload)
    except Exception:
        return None


def _parse_updated_at(value: Any) -> datetime:
    """Parse a sheet ``updatedAt`` (UTC ISO-8601, e.g. 2026-08-14T18:07:10Z).

    Malformed or missing timestamps resolve to the Unix epoch so they sort as
    the OLDEST sheets — a sheet whose age cannot be established must never be
    selected as the "newest" fallback by downstream callers.
    """
    text = str(value or "").strip()
    if not text:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def sheet_is_global(sheet: EnvironmentReferenceSheet) -> bool:
    return bool(getattr(sheet, "isGlobal", False))


def sync_environment_scope(db: Any, sheet: EnvironmentReferenceSheet) -> None:
    from ..creator_scope.contract import ENTITY_ENVIRONMENT
    from ..creator_scope.service import sync_scope

    identity = str(getattr(sheet, "ers_composite_asset_id", None) or "").strip()
    sync_scope(
        db,
        entity_type=ENTITY_ENVIRONMENT,
        entity_id=sheet.sheetId,
        owning_project_id=sheet.projectId,
        is_global=sheet_is_global(sheet),
        tag=getattr(sheet, "canonicalTag", None) or sheet.name,
        name=sheet.name,
        identity_asset_id=identity,
    )


def list_visible_sheets(db: Any, project_id: str) -> list[EnvironmentReferenceSheet]:
    from ..creator_scope.contract import ENTITY_ENVIRONMENT
    from ..creator_scope.service import list_visible_scope

    local = list_sheets(project_id)
    for sheet in local:
        try:
            sync_environment_scope(db, sheet)
        except Exception:
            pass
    extra: list[EnvironmentReferenceSheet] = []
    seen = {s.sheetId for s in local}
    for row in list_visible_scope(db, project_id, entity_type=ENTITY_ENVIRONMENT):
        if row.owning_project_id == project_id or not row.is_global:
            continue
        if row.entity_id in seen:
            continue
        sheet = load_sheet(row.owning_project_id, row.entity_id)
        if sheet is None or not sheet_is_global(sheet):
            continue
        seen.add(sheet.sheetId)
        extra.append(sheet)
    sheets = local + extra
    from ..creator_scope.contract import is_ephemeral_creator_fixture

    sheets = [s for s in sheets if not is_ephemeral_creator_fixture(getattr(s, "name", ""))]
    sheets.sort(
        key=lambda s: (
            _parse_updated_at(s.updatedAt).timestamp(),
            str(getattr(s, "sheetId", "") or ""),
        ),
        reverse=True,
    )
    return sheets


def sheet_is_project_reference(sheet: Any) -> bool:
    """True only when the sheet already has a real Environment Reference Sheet visual.

    A name, description, reference input, or generation attempt is not enough.
    Direct approval and a successful generation both store the official visual.
    """
    composite = str(getattr(sheet, "ers_composite_asset_id", "") or "").strip()
    if composite:
        return True
    rendered = getattr(getattr(sheet, "composition", None), "renderedAssetIds", None) or {}
    if isinstance(rendered, dict):
        for key in ("composite", "png", "sheet"):
            if str(rendered.get(key) or "").strip():
                return True
    return False


def find_reusable_environment_draft(
    sheets: list[EnvironmentReferenceSheet],
    *,
    project_id: str,
    name: str,
) -> EnvironmentReferenceSheet | None:
    """Reuse this project's unfinished sheet so a failed start does not occupy the name."""
    token = str(name or "").strip().lower()
    if not token:
        return None
    matches = [
        sheet
        for sheet in sheets
        if str(getattr(sheet, "projectId", "") or "") == project_id
        and str(getattr(sheet, "name", "") or "").strip().lower() == token
        and not sheet_is_project_reference(sheet)
    ]
    if not matches:
        return None
    matches.sort(key=lambda sheet: str(getattr(sheet, "updatedAt", "") or ""), reverse=True)
    return matches[0]


def check_environment_tag_collision(
    db: Any,
    *,
    project_id: str,
    name: str,
    exclude_id: str = "",
    making_global: bool = False,
) -> None:
    from ..creator_scope.contract import ENTITY_ENVIRONMENT, CreatorScopeError, canonical_tag
    from ..creator_scope.service import find_tag_collision, require_unique_profile_name

    try:
        require_unique_profile_name(
            db,
            entity_type=ENTITY_ENVIRONMENT,
            name=name,
            owning_project_id=project_id,
            exclude_id=exclude_id,
            making_global=making_global,
        )
    except CreatorScopeError:
        raise

    token = canonical_tag(name)
    if not token:
        return
    hit = find_tag_collision(
        db,
        entity_type=ENTITY_ENVIRONMENT,
        tag=token,
        exclude_id=exclude_id,
        owning_project_id=project_id,
        making_global=making_global,
    )
    if hit is not None:
        raise ValueError(
            f"#{token} is already used by {hit.name or 'another environment'} "
            f"{'as a Global asset' if hit.is_global else 'in this project'}. Choose a different name."
        )
    for sheet in list_visible_sheets(db, project_id):
        if exclude_id and sheet.sheetId == exclude_id:
            continue
        other = canonical_tag(sheet.name).lower()
        if other != token.lower():
            continue
        if sheet.projectId == project_id or sheet_is_global(sheet) or making_global:
            raise ValueError(
                f"#{token} is already used by {sheet.name or 'another environment'} "
                f"{'as a Global asset' if sheet_is_global(sheet) else 'in this project'}. Choose a different name."
            )


def load_visible_sheet(db: Any, project_id: str, sheet_id: str) -> EnvironmentReferenceSheet | None:
    sheet = load_sheet(project_id, sheet_id)
    if sheet is not None:
        return sheet
    from ..creator_scope.contract import ENTITY_ENVIRONMENT
    from ..creator_scope.service import load_entity_for_reference

    row = load_entity_for_reference(db, entity_type=ENTITY_ENVIRONMENT, entity_id=sheet_id)
    if row is None:
        return None
    sheet = load_sheet(row.owning_project_id, sheet_id)
    if sheet is None:
        return None
    if sheet.projectId == project_id or sheet_is_global(sheet):
        return sheet
    return None


def list_sheets(project_id: str) -> list[EnvironmentReferenceSheet]:
    sheets: list[EnvironmentReferenceSheet] = []
    for path in sheets_dir(project_id).glob("*.json"):
        payload = _read_json(path, None)
        if not isinstance(payload, dict):
            continue
        try:
            sheets.append(EnvironmentReferenceSheet.model_validate(payload))
        except Exception:
            continue
    # Newest-first by parsed updatedAt (CDX-042); filename (sheetId) is the
    # deterministic tiebreaker. Malformed timestamps sort oldest-first.
    sheets.sort(
        key=lambda s: (
            _parse_updated_at(s.updatedAt).timestamp(),
            str(getattr(s, "sheetId", "") or ""),
        ),
        reverse=True,
    )
    return sheets


def canonical_path(project_id: str) -> Path:
    return project_dir(project_id) / "canonical.json"


def get_canonical_sheet_id(project_id: str) -> str | None:
    payload = _read_json(canonical_path(project_id), None)
    if not isinstance(payload, dict):
        return None
    sheet_id = str(payload.get("approvedCanonicalSheetId") or "").strip()
    return sheet_id or None


def set_canonical_sheet_id(
    project_id: str,
    sheet_id: str,
    *,
    updated_by: str = "creator",
    reason: str = "creator_approve",
) -> dict[str, Any]:
    sheet_id = str(sheet_id or "").strip()
    if not sheet_id:
        raise ValueError("approvedCanonicalSheetId is required")
    from .contracts import utc_now

    payload = {
        "approvedCanonicalSheetId": sheet_id,
        "updatedAt": utc_now(),
        "updatedBy": updated_by,
        "reason": reason,
    }
    _write_json(canonical_path(project_id), payload)
    return payload


def clear_canonical_sheet_id(project_id: str) -> None:
    path = canonical_path(project_id)
    if path.is_file():
        path.unlink()


def delete_environment_sheet(db: Session, project_id: str, sheet_id: str, *, confirm_cross_project: bool = False) -> dict[str, Any]:
    from ..creator_scope.contract import ENTITY_ENVIRONMENT, CreatorScopeError
    from ..creator_scope.service import delete_scope, require_delete_safety
    from ..scene_references.models import SceneReferenceBinding

    sheet = load_sheet(project_id, sheet_id)
    if sheet is None:
        raise FileNotFoundError("Environment Reference Sheet not found")
    if sheet.projectId != project_id:
        raise PermissionError("Global environments can only be deleted from the project that created them.")

    is_global = sheet_is_global(sheet)
    name = sheet.name or "Environment"

    require_delete_safety(
        db,
        entity_type=ENTITY_ENVIRONMENT,
        entity_id=sheet_id,
        owning_project_id=project_id,
        is_global=is_global,
        confirm_cross_project=confirm_cross_project,
    )

    # Unlink scene references pointing at this sheet. Global delete clears every project.
    now_dt = datetime.now(timezone.utc)
    try:
        bind_q = db.query(SceneReferenceBinding).filter(
            SceneReferenceBinding.identity_id == sheet_id,
            SceneReferenceBinding.deleted_at.is_(None),
        )
        if not is_global:
            bind_q = bind_q.filter(SceneReferenceBinding.project_id == project_id)
        for b in bind_q.all():
            b.identity_id = None
            b.enabled = False
            b.deleted_at = now_dt
            b.updated_by = "environment-delete"
    except Exception:
        pass

    # Clear canonical pointer if this sheet is the approved canonical sheet
    try:
        canonical_id = get_canonical_sheet_id(project_id)
        if canonical_id == sheet_id:
            clear_canonical_sheet_id(project_id)
    except Exception:
        pass

    # Delete the sheet JSON file and the scope row
    path = sheets_dir(project_id) / f"{sheet_id}.json"
    if path.is_file():
        path.unlink()

    try:
        delete_scope(db, entity_type=ENTITY_ENVIRONMENT, entity_id=sheet_id)
    except Exception:
        pass

    db.commit()
    return {"deleted": True, "sheet_id": sheet_id, "name": name, "library_assets_kept": True}

