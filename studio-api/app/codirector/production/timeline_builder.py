"""Create or update a real Timeline BatchBlock from a prepared SceneProductionSpec."""

from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from .contracts import ResolvedReference, SceneProductionSpec
from .errors import TimelineShotCreationError
from .generator_validator import normalize_generator_config, normalize_generator_id
from .timed_regions import parse_explicit_timed_regions

_NAMED_SCENE_RE = re.compile(r"\bnamed\s+([^.,\n]+)", re.I)
_TECHNICAL_SCENE_NAME_RE = re.compile(
    r"\b(hydration|repair\s+fresh|certification|\bcert\b|e2e|playwright|"
    r"unit\s+test|smoke\s+test|qa\s+test|debug\s+scene|canonical\s+tag)\b"
    r"|fresh\s+\d{6,}"
    r"|\d{10,}",
    re.I,
)
_SHEET_SUFFIX_RE = re.compile(
    r"\s+((environment|prop|character)\s+)?reference\s+sheet$|\s+(ers|prs|crs)$|\s+png$",
    re.I,
)
_GENERIC_FILENAMES = frozenset({"front.png", "back.png", "image.png", "sheet.png", "p.png", "hero.png"})


def _clean_story_token(raw: str) -> str:
    text = re.sub(r"\s+", " ", str(raw or "")).strip()
    text = _SHEET_SUFFIX_RE.sub("", text).strip(" -–—")
    text = re.sub(r"(?<=[a-z])Png$", "", text)
    return text[:60].strip()


def is_technical_scene_name(name: str | None) -> bool:
    token = re.sub(r"\s+", " ", str(name or "")).strip()
    if not token:
        return True
    if token.lower() in {"timeline scene", "new scene", "scene"}:
        return True
    return bool(_TECHNICAL_SCENE_NAME_RE.search(token))


def _explicit_creator_title(text: str) -> str:
    match = _NAMED_SCENE_RE.search(text or "")
    if not match:
        return ""
    name = _clean_story_token(match.group(1))
    name = re.sub(r"\s+(using|where|with|for)\s+.*$", "", name, flags=re.I).strip()
    if len(name) < 3 or len(name) > 60:
        return ""
    if is_technical_scene_name(name):
        return ""
    return name


def _story_scene_name(spec: SceneProductionSpec) -> str:
    intent = spec.director_intent
    env = ""
    subjects: list[str] = []
    if intent is not None:
        env = _clean_story_token(intent.environment.name)
        subjects = [_clean_story_token(item.name) for item in intent.subjects if _clean_story_token(item.name)]
    if not env:
        for ref in spec.references:
            if ref.asset_type == "environment":
                env = _clean_story_token(ref.display_name or ref.query)
                if env:
                    break
    if not subjects:
        for ref in spec.references:
            if ref.asset_type in {"prop", "character"}:
                token = _clean_story_token(ref.display_name or ref.query)
                if token and token not in subjects:
                    subjects.append(token)
    shot = str(spec.camera.shot_type or spec.camera_intent or "").strip().lower()
    if env and subjects:
        return f"{subjects[0]} at {env}"
    if env and shot == "establishing":
        return f"{env} Establishing"
    if env:
        return env
    if subjects:
        return subjects[0]
    opening = _clean_story_token((intent.opening_state if intent is not None else "") or spec.scene_intent)
    if opening and not is_technical_scene_name(opening) and len(opening.split()) <= 8:
        return opening
    if shot == "establishing":
        return "Establishing Shot"
    return "New Scene"


def _scene_name(spec: SceneProductionSpec) -> str:
    """Creator-facing title from the shot, not from cert/debug 'named …' clauses."""
    explicit = _explicit_creator_title(spec.source_user_prompt or "")
    if explicit:
        return explicit
    return _story_scene_name(spec)


def _distinctive_filename(filename: str) -> bool:
    token = (filename or "").strip().lower()
    if not token or token in _GENERIC_FILENAMES:
        return False
    return bool(re.search(r"[a-z]{5,}", token))


def _adopt_visible_asset(db: Session, project_id: str, source: Any) -> str:
    from ...config import settings
    from ...db import Asset

    filename = str(getattr(source, "filename", "") or "").strip()
    if _distinctive_filename(filename):
        local = (
            db.query(Asset)
            .filter(Asset.project_id == project_id, Asset.filename == filename)
            .first()
        )
        if local is not None:
            return str(local.id)
    src_path = Path(str(getattr(source, "path", "") or ""))
    if not src_path.is_file():
        return ""
    dest_dir = Path(settings.data_dir) / "assets" / project_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    new_id = str(uuid.uuid4())
    dest = dest_dir / f"{new_id}{src_path.suffix or '.png'}"
    shutil.copy2(src_path, dest)
    asset = Asset(
        id=new_id,
        project_id=project_id,
        tag=str(getattr(source, "tag", "") or ""),
        kind=str(getattr(source, "kind", "") or "image"),
        filename=filename or dest.name,
        path=str(dest),
        parent_asset_id=str(source.id),
    )
    db.add(asset)
    db.flush()
    return new_id


def _project_local_asset_id(db: Session, project_id: str, asset_id: str) -> str:
    if not asset_id:
        return ""
    from ...db import Asset

    row = db.get(Asset, asset_id)
    if row is None:
        return ""
    if str(row.project_id) == project_id:
        return asset_id
    filename = str(getattr(row, "filename", "") or "")
    if _distinctive_filename(filename):
        hit = (
            db.query(Asset)
            .filter(Asset.project_id == project_id, Asset.filename == filename)
            .first()
        )
        if hit is not None:
            return str(hit.id)
    adopted = _adopt_visible_asset(db, project_id, row)
    if adopted:
        return adopted
    return ""


def _usage_for(asset_type: str) -> str:
    if asset_type == "environment":
        return "environment"
    if asset_type == "character":
        return "identity"
    return "prop"


def _existing_binding_id(
    db: Session,
    project_id: str,
    scene_id: str,
    asset_id: str,
    reference_type: str = "",
) -> str:
    from ...scene_references import repository as ref_repo

    wanted_type = str(reference_type or "").strip().lower()
    for row in ref_repo.list_bindings(db, project_id, scope_type="scene", scope_id=scene_id):
        if str(getattr(row, "asset_id", "") or "") != asset_id:
            continue
        if wanted_type and str(getattr(row, "reference_type", "") or "").strip().lower() != wanted_type:
            continue
        return str(row.id)
    return ""


def _attach_reference(
    db: Session,
    *,
    project_id: str,
    scene_id: str,
    ref: ResolvedReference,
) -> dict[str, str]:
    from ...scene_references.service import attach

    asset_id = _project_local_asset_id(db, project_id, ref.bindable_asset_id or ref.asset_id)
    if not asset_id:
        raise TimelineShotCreationError(
            f"{ref.display_name or ref.query} was resolved but its Library asset is not in this project.",
            details={"query": ref.query, "assetId": ref.bindable_asset_id or ref.asset_id},
        )
    reference_type = ref.asset_type or "prop"
    # Check-first dedupe: retries and re-prepares reuse the existing binding
    # instead of attempting a duplicate attach.
    existing_first = _existing_binding_id(db, project_id, scene_id, asset_id, reference_type)
    if existing_first:
        return {
            "binding_id": existing_first,
            "asset_id": asset_id,
            "identity_id": ref.entity_id or "",
            "reference_sheet_id": ref.reference_sheet_id or "",
            "tag": ref.canonical_tag or "",
            "prompt_name": ref.display_name or ref.query,
            "type": reference_type,
        }
    alias = (ref.canonical_tag or "").lstrip("@#%*") or ref.display_name or ref.query
    body = {
        "asset_id": asset_id,
        "scope_type": "scene",
        "scope_id": scene_id,
        "reference_type": reference_type,
        "usage_modes": [_usage_for(reference_type)],
        "alias": alias,
        "identity_id": ref.entity_id or None,
        "enabled": True,
    }
    try:
        result = attach(db, project_id, body, actor="codirector")
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        existing_id = _existing_binding_id(db, project_id, scene_id, asset_id, reference_type)
        if existing_id:
            return {
                "binding_id": existing_id,
                "asset_id": asset_id,
                "identity_id": ref.entity_id or "",
                "reference_sheet_id": ref.reference_sheet_id or "",
                "tag": ref.canonical_tag or "",
                "prompt_name": ref.display_name or ref.query,
                "type": reference_type,
            }
        detail = getattr(exc, "detail", None)
        if isinstance(detail, dict) and detail.get("code") == "CROSS_PROJECT_ASSET_DENIED":
            raise TimelineShotCreationError(
                f"{ref.display_name or ref.query} could not be bound: the asset is not in this project.",
                details={"query": ref.query, "assetId": asset_id},
            ) from exc
        raise TimelineShotCreationError(
            f"{ref.display_name or ref.query} could not be bound: {exc}",
            details={"query": ref.query},
        ) from exc
    binding_id = str(
        (result or {}).get("id")
        or (result or {}).get("bindingId")
        or ((result or {}).get("binding") or {}).get("id")
        or ""
    )
    if not binding_id:
        raise TimelineShotCreationError(
            f"{ref.display_name or ref.query} attached without a binding id.",
            details={"result": result},
        )
    return {
        "binding_id": binding_id,
        "asset_id": str((result or {}).get("asset_id") or asset_id),
        "identity_id": str((result or {}).get("identity_id") or ref.entity_id or ""),
        "reference_sheet_id": ref.reference_sheet_id or "",
        "tag": ref.canonical_tag or "",
        "prompt_name": ref.display_name or ref.query,
        "type": reference_type,
    }


def _find_existing_batch(master: Any, request_id: str, batch_index: int | None = None) -> Any | None:
    if not request_id:
        return None
    for batch in master.batchBlocks or []:
        meta = getattr(batch, "migrationMetadata", None) or {}
        if str(meta.get("sourceProductionRequestId") or "") != request_id:
            continue
        if batch_index is None:
            return batch
        if int(meta.get("sourceProductionBatchIndex") or 0) == batch_index:
            return batch
    return None


def create_or_update_shot_from_spec(
    db: Session,
    spec: SceneProductionSpec,
    references: list[ResolvedReference],
    compiled_prompt: str,
    batch_prompts: list[str] | None = None,
) -> tuple[str, str, int, str]:
    """Author a Film Timeline shot. This does not render."""

    from ...film_timeline.codirector_bridge import author_shot_from_spec

    _ = batch_prompts
    return author_shot_from_spec(db, spec, references, compiled_prompt)
