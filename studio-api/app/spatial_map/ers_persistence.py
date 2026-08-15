"""Persistence helpers for ERS packages, scene batches, and prop entities.

Stores structured JSON values in ``ProjectTraitRow`` so no DB migration is
required (idempotent with existing tables). All accessors are project-scoped:
queries always filter by ``project_id`` to preserve project isolation
(Build Law #14).

Three trait categories are used:
- ``spatial_ers``   : ``EnvironmentReferencePackage`` keyed by package id
- ``scene_batch``   : ``SceneGenerationBatch`` keyed by batch id
- ``prop_entity``   : ``PropEntity`` keyed by prop id (legacy rows may use tag)

Amendment #3 (SPATIAL AUTHORITY): the ERS package snapshots spatial map
placements at generation time and never writes back to the spatial map.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy.orm import Session

from .ers_contracts import (
    EnvironmentReferencePackage,
    PropEntity,
    SceneGenerationBatch,
    SceneShot,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

ERS_CATEGORY = "spatial_ers"
BATCH_CATEGORY = "scene_batch"
PROP_CATEGORY = "prop_entity"
SHOT_CATEGORY = "scene_shot"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _model_dump_json(model) -> str:
    # Use model_dump_json when available (pydantic v2) so datetimes serialize.
    try:
        return model.model_dump_json()
    except Exception:
        return json.dumps(model.model_dump(mode="json"), ensure_ascii=False, default=str)


def _upsert_trait(
    db: Session,
    *,
    project_id: str,
    category: str,
    key: str,
    value: str,
    provenance: str,
) -> None:
    from ..db import ProjectTraitRow

    existing = (
        db.query(ProjectTraitRow)
        .filter(
            ProjectTraitRow.project_id == project_id,
            ProjectTraitRow.category == category,
            ProjectTraitRow.key == key,
        )
        .first()
    )
    if existing:
        existing.value = value
        existing.provenance = provenance
    else:
        db.add(
            ProjectTraitRow(
                id=str(uuid4()),
                project_id=project_id,
                category=category,
                key=key,
                value=value,
                provenance=provenance,
                created_at=_now(),
            )
        )
    db.commit()


def _delete_trait(db: Session, *, project_id: str, category: str, key: str) -> None:
    from ..db import ProjectTraitRow

    (
        db.query(ProjectTraitRow)
        .filter(
            ProjectTraitRow.project_id == project_id,
            ProjectTraitRow.category == category,
            ProjectTraitRow.key == key,
        )
        .delete(synchronize_session=False)
    )
    db.commit()


def _load_trait_value(db: Session, *, project_id: str, category: str, key: str) -> str | None:
    from ..db import ProjectTraitRow

    row = (
        db.query(ProjectTraitRow)
        .filter(
            ProjectTraitRow.project_id == project_id,
            ProjectTraitRow.category == category,
            ProjectTraitRow.key == key,
        )
        .first()
    )
    return row.value if row else None


def _list_trait_values(db: Session, *, project_id: str, category: str) -> list[str]:
    from ..db import ProjectTraitRow

    rows = (
        db.query(ProjectTraitRow)
        .filter(
            ProjectTraitRow.project_id == project_id,
            ProjectTraitRow.category == category,
        )
        .order_by(ProjectTraitRow.id.desc())
        .all()
    )
    return [row.value for row in rows if row.value]


# ---------------------------------------------------------------------------
# EnvironmentReferencePackage
# ---------------------------------------------------------------------------


def save_ers_package(
    db: Session,
    project_id: str,
    package: EnvironmentReferencePackage,
    *,
    provenance: str = "ers_generate",
) -> None:
    package.updated_at = _now()
    if not package.created_at:
        package.created_at = _now()
    _upsert_trait(
        db,
        project_id=project_id,
        category=ERS_CATEGORY,
        key=package.id,
        value=_model_dump_json(package),
        provenance=provenance,
    )


def load_ers_package(db: Session, project_id: str, package_id: str) -> EnvironmentReferencePackage | None:
    raw = _load_trait_value(db, project_id=project_id, category=ERS_CATEGORY, key=package_id)
    if not raw:
        return None
    try:
        return EnvironmentReferencePackage.model_validate_json(raw)
    except Exception as exc:
        logger.error("Failed to load ERS package %s: %s", package_id, exc)
        return None


def list_ers_packages(db: Session, project_id: str) -> list[EnvironmentReferencePackage]:
    packages: list[EnvironmentReferencePackage] = []
    for raw in _list_trait_values(db, project_id=project_id, category=ERS_CATEGORY):
        try:
            packages.append(EnvironmentReferencePackage.model_validate_json(raw))
        except Exception:
            continue
    return packages


# ---------------------------------------------------------------------------
# SceneGenerationBatch
# ---------------------------------------------------------------------------


def save_scene_batch(db: Session, project_id: str, batch: SceneGenerationBatch) -> None:
    batch.updated_at = _now()
    if not batch.created_at:
        batch.created_at = _now()
    _upsert_trait(
        db,
        project_id=project_id,
        category=BATCH_CATEGORY,
        key=batch.id,
        value=_model_dump_json(batch),
        provenance="scene_generate",
    )


def load_scene_batch(db: Session, project_id: str, batch_id: str) -> SceneGenerationBatch | None:
    raw = _load_trait_value(db, project_id=project_id, category=BATCH_CATEGORY, key=batch_id)
    if not raw:
        return None
    try:
        return SceneGenerationBatch.model_validate_json(raw)
    except Exception as exc:
        logger.error("Failed to load scene batch %s: %s", batch_id, exc)
        return None


def list_scene_batches(db: Session, project_id: str) -> list[SceneGenerationBatch]:
    batches: list[SceneGenerationBatch] = []
    for raw in _list_trait_values(db, project_id=project_id, category=BATCH_CATEGORY):
        try:
            batches.append(SceneGenerationBatch.model_validate_json(raw))
        except Exception:
            continue
    return batches


# ---------------------------------------------------------------------------
# PropEntity
# ---------------------------------------------------------------------------


def save_prop_entity(db: Session, project_id: str, prop: PropEntity) -> None:
    prop.updated_at = _now()
    if not prop.created_at:
        prop.created_at = _now()
    # Prefer stable id key. Drop a leftover tag-keyed row if this prop was saved
    # under the old scheme.
    if prop.tag and prop.tag != prop.id:
        existing_tag = load_prop_entity(db, project_id, prop.tag)
        if existing_tag and existing_tag.id == prop.id:
            _delete_trait(db, project_id=project_id, category=PROP_CATEGORY, key=prop.tag)
    _upsert_trait(
        db,
        project_id=project_id,
        category=PROP_CATEGORY,
        key=prop.id,
        value=_model_dump_json(prop),
        provenance="prop_entity",
    )


def load_prop_entity(db: Session, project_id: str, tag: str) -> PropEntity | None:
    raw = _load_trait_value(db, project_id=project_id, category=PROP_CATEGORY, key=tag)
    if raw:
        try:
            return PropEntity.model_validate_json(raw)
        except Exception as exc:
            logger.error("Failed to load prop entity %s: %s", tag, exc)
            return None
    for prop in list_prop_entities(db, project_id):
        if prop.tag == tag or prop.id == tag:
            return prop
    return None


def load_prop_entity_by_id(db: Session, project_id: str, prop_id: str) -> PropEntity | None:
    raw = _load_trait_value(db, project_id=project_id, category=PROP_CATEGORY, key=prop_id)
    if raw:
        try:
            return PropEntity.model_validate_json(raw)
        except Exception as exc:
            logger.error("Failed to load prop entity %s: %s", prop_id, exc)
            return None
    for prop in list_prop_entities(db, project_id):
        if prop.id == prop_id:
            return prop
    return None


def delete_prop_entity(db: Session, project_id: str, prop_id: str) -> PropEntity | None:
    prop = load_prop_entity_by_id(db, project_id, prop_id)
    if prop is None:
        return None
    _delete_trait(db, project_id=project_id, category=PROP_CATEGORY, key=prop.id)
    if prop.tag and prop.tag != prop.id:
        leftover = load_prop_entity(db, project_id, prop.tag)
        if leftover and leftover.id == prop.id:
            _delete_trait(db, project_id=project_id, category=PROP_CATEGORY, key=prop.tag)
    return prop


def save_scene_shot(db: Session, project_id: str, shot: SceneShot) -> None:
    shot.updated_at = _now()
    if not shot.created_at:
        shot.created_at = _now()
    _upsert_trait(
        db,
        project_id=project_id,
        category=SHOT_CATEGORY,
        key=shot.id,
        value=_model_dump_json(shot),
        provenance="scene_creator",
    )


def load_scene_shot(db: Session, project_id: str, shot_id: str) -> SceneShot | None:
    raw = _load_trait_value(db, project_id=project_id, category=SHOT_CATEGORY, key=shot_id)
    if not raw:
        return None
    try:
        return SceneShot.model_validate_json(raw)
    except Exception as exc:
        logger.error("Failed to load scene shot %s: %s", shot_id, exc)
        return None


def list_scene_shots(db: Session, project_id: str, *, scene_id: str | None = None) -> list[SceneShot]:
    shots: list[SceneShot] = []
    for raw in _list_trait_values(db, project_id=project_id, category=SHOT_CATEGORY):
        try:
            shot = SceneShot.model_validate_json(raw)
        except Exception:
            continue
        if scene_id and shot.scene_id != scene_id:
            continue
        shots.append(shot)
    shots.sort(key=lambda s: s.created_at or "")
    return shots


def list_prop_entities(db: Session, project_id: str) -> list[PropEntity]:
    props: list[PropEntity] = []
    for raw in _list_trait_values(db, project_id=project_id, category=PROP_CATEGORY):
        try:
            props.append(PropEntity.model_validate_json(raw))
        except Exception:
            continue
    return props


def persist_ers_composite_asset(
    db: Session,
    project_id: str,
    *,
    sheet_id: str,
    asset_id: str,
    package_id: str | None = None,
    sheet: Any = None,
    package: Any = None,
) -> dict[str, Any]:
    """Bind a real Library asset as the ERS composite so has_reference can be true.

    Does not generate. Does not rewrite Spatial Map positions.
    """
    asset_id = (asset_id or "").strip()
    sheet_id = (sheet_id or "").strip()
    if not asset_id:
        raise ValueError("ERS persist needs a Library asset id.")
    if not sheet_id:
        raise ValueError("ERS persist needs an Environment Reference Sheet id.")

    from ..db import Asset as AssetRow

    asset = (
        db.query(AssetRow)
        .filter(AssetRow.id == asset_id, AssetRow.project_id == project_id)
        .first()
    )
    if asset is None:
        raise ValueError(
            "Environment Reference Sheet could not persist: Library asset not found."
        )

    from ..environment_reference_sheet.store import load_sheet, save_sheet

    current_sheet = sheet
    if current_sheet is None:
        current_sheet = load_sheet(project_id, sheet_id)
    if current_sheet is None:
        raise ValueError("Environment Reference Sheet not found in this project.")

    rendered = dict(
        getattr(getattr(current_sheet, "composition", None), "renderedAssetIds", None) or {}
    )
    rendered["composite"] = asset_id
    rendered.setdefault("png", asset_id)
    current_sheet.composition.renderedAssetIds = rendered
    current_sheet.ers_composite_asset_id = asset_id
    if current_sheet.status in {"draft", "spatial_pending", "views_pending"}:
        current_sheet.status = "registered"
    save_sheet(current_sheet)

    current_package = package
    if current_package is None and package_id:
        current_package = load_ers_package(db, project_id, package_id)
    if current_package is None:
        packages = [
            p
            for p in list_ers_packages(db, project_id)
            if str((p.metadata or {}).get("sheet_id") or "") == sheet_id
            and not str(p.id).startswith("runtime-")
        ]
        if packages:
            current_package = sorted(
                packages, key=lambda p: p.updated_at or p.created_at or "", reverse=True
            )[0]
    if current_package is not None:
        current_package.ers_composite_asset_id = asset_id
        meta = dict(current_package.metadata or {})
        meta["sheet_id"] = sheet_id
        meta["ers_composite_asset_id"] = asset_id
        current_package.metadata = meta
        save_ers_package(db, project_id, current_package, provenance="ers_composite_persist")

    return {
        "sheet_id": sheet_id,
        "asset_id": asset_id,
        "ers_composite_asset_id": asset_id,
        "package_id": getattr(current_package, "id", None),
        "has_reference": True,
    }
