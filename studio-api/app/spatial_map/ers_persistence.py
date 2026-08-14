"""Persistence helpers for ERS packages, scene batches, and prop entities.

Stores structured JSON values in ``ProjectTraitRow`` so no DB migration is
required (idempotent with existing tables). All accessors are project-scoped:
queries always filter by ``project_id`` to preserve project isolation
(Build Law #14).

Three trait categories are used:
- ``spatial_ers``   : ``EnvironmentReferencePackage`` keyed by package id
- ``scene_batch``   : ``SceneGenerationBatch`` keyed by batch id
- ``prop_entity``   : ``PropEntity`` keyed by normalized prop tag

Amendment #3 (SPATIAL AUTHORITY): the ERS package snapshots spatial map
placements at generation time and never writes back to the spatial map.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING
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
    _upsert_trait(
        db,
        project_id=project_id,
        category=PROP_CATEGORY,
        key=prop.tag,
        value=_model_dump_json(prop),
        provenance="prop_entity",
    )


def load_prop_entity(db: Session, project_id: str, tag: str) -> PropEntity | None:
    raw = _load_trait_value(db, project_id=project_id, category=PROP_CATEGORY, key=tag)
    if not raw:
        return None
    try:
        return PropEntity.model_validate_json(raw)
    except Exception as exc:
        logger.error("Failed to load prop entity %s: %s", tag, exc)
        return None


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
