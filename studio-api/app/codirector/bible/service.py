"""ProductionBibleService: project-facing Bible read/create/version API.

This is the only module callers outside `codirector/bible/` should import from for Bible
reads and direct (non-proposal) version creation. Proposal-driven writes go through
`proposals.ProposalService`, which calls `operations.apply_mutation_set` the same way this
module's `create_new_version` does.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from ...db import Asset, Project, ProductionBible, Scene
from ..errors import BIBLE_NOT_FOUND, BIBLE_VERSION_NOT_FOUND, CoDirectorError
from . import operations as ops
from .schemas import (
    BibleEntity,
    BibleFact,
    BibleMutationSet,
    BibleVersionDetail,
    ImportPreviewResponse,
    ProductionBibleOut,
)


def _slugify(text: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").strip().lower()).strip("-")
    return slug or fallback


def _version_to_detail(db: Session, version) -> BibleVersionDetail:
    entities = [ops.entity_row_to_schema(row) for row in ops.entities_for_version(db, version.id)]
    facts = [ops.fact_row_to_schema(row) for row in ops.facts_for_version(db, version.id)]
    return BibleVersionDetail(
        id=version.id,
        bibleId=version.bible_id,
        versionNumber=version.version_number,
        parentVersionId=version.parent_version_id,
        summary=version.summary or "",
        changeReason=version.change_reason or "",
        createdBy=version.created_by or "user",
        createdAt=version.created_at.isoformat() if version.created_at else "",
        entities=entities,
        facts=facts,
    )


def get_bible_out(db: Session, project_id: str) -> Optional[ProductionBibleOut]:
    bible = ops.get_bible(db, project_id)
    if not bible:
        return None
    current = ops.get_current_version(db, bible)
    versions = ops.list_versions(db, bible.id)
    return ProductionBibleOut(
        projectId=project_id,
        currentVersion=_version_to_detail(db, current) if current else None,
        versionCount=len(versions),
    )


def require_bible(db: Session, project_id: str) -> ProductionBible:
    bible = ops.get_bible(db, project_id)
    if not bible:
        raise CoDirectorError(
            BIBLE_NOT_FOUND,
            "This project doesn't have a Production Bible yet. Create one first.",
            details={"projectId": project_id},
            recoverable=True,
            recommended_action="create_bible",
        )
    return bible


def list_versions_out(db: Session, project_id: str) -> list[BibleVersionDetail]:
    bible = require_bible(db, project_id)
    return [_version_to_detail(db, v) for v in ops.list_versions(db, bible.id)]


def get_version_out(db: Session, project_id: str, version_number: int) -> BibleVersionDetail:
    bible = require_bible(db, project_id)
    version = ops.get_version_by_number(db, bible.id, version_number)
    if not version:
        raise CoDirectorError(
            BIBLE_VERSION_NOT_FOUND,
            f"Bible version {version_number} was not found.",
            details={"projectId": project_id, "versionNumber": version_number},
            recoverable=False,
            recommended_action="none",
        )
    return _version_to_detail(db, version)


def build_import_preview(db: Session, project_id: str, *, include_scenes: bool, include_assets_as_props: bool) -> ImportPreviewResponse:
    """Derive a Bible seed from existing project data. Pure read — nothing is persisted."""

    project = db.get(Project, project_id)
    if not project:
        raise CoDirectorError(
            "PROJECT_NOT_FOUND",
            "Project not found.",
            details={"projectId": project_id},
            recoverable=False,
            recommended_action="none",
        )

    entities: list[BibleEntity] = []
    facts: list[BibleFact] = []
    warnings: list[str] = []

    entities.append(
        BibleEntity(
            entityType="project_profile",
            entityKey="project-profile",
            displayName=project.name or "Untitled Project",
            data={
                "name": project.name,
                "description": project.description or "",
                "engineDefault": project.engine_default,
                "aspect": f"{project.width}x{project.height}",
                "fps": project.fps,
            },
        )
    )

    if (project.global_prompt or "").strip():
        entities.append(
            BibleEntity(
                entityType="visual_style",
                entityKey="global-visual-style",
                displayName="Global look & feel",
                data={"description": project.global_prompt.strip()},
            )
        )

    if include_assets_as_props:
        assets = db.query(Asset).filter(Asset.project_id == project_id).all()
        seen_tags: set[str] = set()
        for asset in assets:
            tag = (asset.tag or "").strip()
            if not tag or tag in seen_tags:
                continue
            seen_tags.add(tag)
            entities.append(
                BibleEntity(
                    entityType="prop" if asset.kind != "image" or "char" not in tag.lower() else "character",
                    entityKey=_slugify(tag, f"asset-{asset.id[:8]}"),
                    displayName=tag,
                    data={"assetId": asset.id, "kind": asset.kind},
                )
            )
        if not assets:
            warnings.append("No tagged assets found to import as characters/props.")

    if include_scenes:
        scenes = db.query(Scene).filter(Scene.project_id == project_id).order_by(Scene.index).all()
        for scene in scenes:
            if (scene.prompt or "").strip():
                facts.append(
                    BibleFact(
                        entityKey=None,
                        factType="scene_fact",
                        statement=f"Scene '{scene.name}' (#{scene.index}): {scene.prompt.strip()[:400]}",
                        data={"sceneId": scene.id, "sceneIndex": scene.index},
                    )
                )
        if not scenes:
            warnings.append("No scenes found to import as scene facts.")

    summary = f"Imported from project '{project.name}': {len(entities)} entities, {len(facts)} facts."
    return ImportPreviewResponse(projectId=project_id, entities=entities, facts=facts, summary=summary, warnings=warnings)


def confirm_import(
    db: Session,
    project_id: str,
    *,
    entities: list[BibleEntity],
    facts: list[BibleFact],
    summary: str,
    change_reason: str,
) -> ProductionBibleOut:
    existing = ops.get_bible(db, project_id)
    if existing:
        raise CoDirectorError(
            "BIBLE_ALREADY_EXISTS",
            "This project already has a Production Bible. Create a new version instead of re-importing.",
            details={"projectId": project_id},
            recoverable=True,
            recommended_action="use_versions",
        )
    ops.create_bible_with_first_version(
        db,
        project_id=project_id,
        entities=entities,
        facts=facts,
        summary=summary,
        change_reason=change_reason,
        created_by="user",
    )
    out = get_bible_out(db, project_id)
    assert out is not None
    return out


def create_new_version(
    db: Session, project_id: str, mutations: BibleMutationSet, created_by: str = "user"
) -> BibleVersionDetail:
    bible = require_bible(db, project_id)
    base = ops.get_current_version(db, bible)
    version = ops.apply_mutation_set(db, bible=bible, base_version=base, mutations=mutations, created_by=created_by)
    return _version_to_detail(db, version)
