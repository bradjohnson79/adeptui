"""ProductionBibleService: project-facing Bible read/create/version API.

This is the only module callers outside `codirector/bible/` should import from for Bible
reads and direct (non-proposal) version creation. Proposal-driven writes go through
`proposals.ProposalService`, which calls `operations.apply_mutation_set` the same way this
module's `create_new_version` does.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from ...db import Asset, Project, ProductionBible, Scene
from ..errors import BIBLE_NOT_FOUND, BIBLE_VERSION_NOT_FOUND, CoDirectorError
from . import operations as ops
from .schemas import (
    BibleEntity,
    BibleFact,
    BibleMutationSet,
    BibleVersionDetail,
    ImportDiscoveryAsset,
    ImportDiscoveryGroup,
    ImportDiscoveryItem,
    ImportPreviewResponse,
    ProductionBibleOut,
)


def _slugify(text: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").strip().lower()).strip("-")
    return slug or fallback


def _pretty_label(text: str) -> str:
    cleaned = re.sub(r"[_-]+", " ", (text or "").strip())
    return re.sub(r"\s+", " ", cleaned).strip().title()


def _display_name_from_tag(tag: str, entity_type: str) -> str:
    display = (tag or "").strip()
    if not display:
        return "Untitled"
    patterns = {
        "character": r"\b(character|char|hero|lead|actor|cast)\b",
        "location": r"\b(location|set|room|place|environment|interior|exterior)\b",
        "prop": r"\b(prop|object|weapon|vehicle|artifact|item)\b",
    }
    pattern = patterns.get(entity_type)
    if pattern:
        display = re.sub(pattern, "", display, flags=re.IGNORECASE)
        display = re.sub(r"\s+", " ", display).strip(" -_/")
    return display or _pretty_label(tag)


def _tokenize(*parts: str) -> set[str]:
    return {
        token
        for token in re.split(r"[^a-z0-9]+", " ".join((part or "").lower() for part in parts))
        if token
    }


_CHARACTER_HINTS = {"character", "char", "hero", "lead", "actor", "cast", "protagonist", "antagonist"}
_LOCATION_HINTS = {
    "location",
    "set",
    "room",
    "place",
    "environment",
    "city",
    "forest",
    "street",
    "house",
    "interior",
    "exterior",
    "rooftop",
}
_PROP_HINTS = {"prop", "object", "weapon", "vehicle", "artifact", "item", "tool", "device"}
_STYLE_HINTS = {"style", "look", "palette", "moodboard", "mood", "lighting", "grade", "reference"}


def _infer_asset_entity_type(tag: str, assets: list[Asset]) -> tuple[str, str, bool, list[str]]:
    tokens = _tokenize(tag, *(asset.filename for asset in assets))
    matches: list[tuple[str, str]] = []
    if tokens & _CHARACTER_HINTS:
        matches.append(("character", "This tag looks like a character reference."))
    if tokens & _LOCATION_HINTS:
        matches.append(("location", "This tag looks like a location or set reference."))
    if tokens & _STYLE_HINTS:
        matches.append(("visual_style", "This tag looks like a visual style or mood reference."))
    if tokens & _PROP_HINTS or assets[0].kind != "image":
        matches.append(("prop", "This tag looks like a prop or production object."))

    if not matches:
        if assets[0].kind == "image":
            return (
                "prop",
                "needs-review",
                True,
                ["This image could not be confidently classified yet. Choose whether it belongs with a character, place, or object."],
            )
        return ("prop", "props", False, ["Imported as a project object."])

    chosen_type, first_reason = matches[0]
    group_id = {
        "character": "characters",
        "location": "locations",
        "visual_style": "visual-style",
        "prop": "props",
    }[chosen_type]
    needs_review = len({item[0] for item in matches}) > 1
    reasons = [reason for _, reason in matches]
    if needs_review:
        reasons.append("This discovery overlaps more than one creative category, so it should be confirmed before version 1.")
    else:
        reasons = [first_reason]
    return chosen_type, group_id, needs_review, reasons


def _reference_asset(asset: Asset) -> ImportDiscoveryAsset:
    return ImportDiscoveryAsset(
        assetId=asset.id,
        tag=asset.tag or "",
        kind=asset.kind or "image",
        filename=asset.filename or "",
    )


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
    discoveries: dict[str, dict[str, Any]] = {
        "project-foundation": {
            "title": "Project Foundation",
            "description": "The core identity of the project, including the title, premise, and format.",
            "items": [],
        },
        "characters": {
            "title": "Characters",
            "description": "People who belong in the trusted memory of the project.",
            "items": [],
        },
        "locations": {
            "title": "Locations",
            "description": "Places, sets, and environments the story returns to.",
            "items": [],
        },
        "props": {
            "title": "Props & Objects",
            "description": "Important objects, wardrobe, and recurring physical details.",
            "items": [],
        },
        "visual-style": {
            "title": "Visual Style",
            "description": "The look, mood, and image language that guide future generations.",
            "items": [],
        },
        "story": {
            "title": "Story Facts",
            "description": "Story beats and notes discovered from the current project.",
            "items": [],
        },
        "needs-review": {
            "title": "Needs Review",
            "description": "Discoveries that need a quick creative decision before they become canon.",
            "items": [],
        },
    }

    project_profile = BibleEntity(
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
    entities.append(project_profile)
    discoveries["project-foundation"]["items"].append(
        ImportDiscoveryItem(
            id="entity:project-profile",
            kind="entity",
            title=project_profile.displayName,
            subtitle=(project.description or "Project title, format, and foundational settings.")[:180],
            entityKey=project_profile.entityKey,
            entityType=project_profile.entityType,
        )
    )

    if (project.description or "").strip():
        premise_fact = BibleFact(
            entityKey="project-profile",
            factType="story_fact",
            statement=project.description.strip(),
            data={"source": "project_description"},
        )
        facts.append(premise_fact)
        discoveries["story"]["items"].append(
            ImportDiscoveryItem(
                id="fact:project-premise",
                kind="fact",
                title="Story premise",
                subtitle=project.description.strip()[:180],
                factIndex=len(facts) - 1,
            )
        )

    if (project.global_prompt or "").strip():
        visual_style = BibleEntity(
            entityType="visual_style",
            entityKey="global-visual-style",
            displayName="Project look & feel",
            data={"description": project.global_prompt.strip(), "discoveryGroup": "visual-style"},
        )
        entities.append(visual_style)
        discoveries["visual-style"]["items"].append(
            ImportDiscoveryItem(
                id="entity:global-visual-style",
                kind="entity",
                title=visual_style.displayName,
                subtitle=project.global_prompt.strip()[:180],
                entityKey=visual_style.entityKey,
                entityType=visual_style.entityType,
            )
        )

    if include_assets_as_props:
        assets = db.query(Asset).filter(Asset.project_id == project_id).all()
        assets_by_tag: dict[str, list[Asset]] = {}
        for asset in assets:
            tag = (asset.tag or "").strip()
            if not tag:
                continue
            assets_by_tag.setdefault(tag, []).append(asset)
        for tag, tagged_assets in sorted(assets_by_tag.items(), key=lambda item: item[0].lower()):
            entity_type, group_id, needs_review, reasons = _infer_asset_entity_type(tag, tagged_assets)
            entity_key = _slugify(tag, f"asset-{tagged_assets[0].id[:8]}")
            reference_assets = [_reference_asset(asset) for asset in tagged_assets]
            display_name = _display_name_from_tag(tag, entity_type)
            entity = BibleEntity(
                entityType=entity_type,  # type: ignore[arg-type]
                entityKey=entity_key,
                displayName=display_name,
                data={
                    "sourceAssetIds": [asset.id for asset in tagged_assets],
                    "referenceAssets": [asset.model_dump(mode="json") for asset in reference_assets],
                    "sourceTag": tag,
                    "discoveryGroup": group_id,
                    "needsReview": needs_review,
                    "classificationReasons": reasons,
                    "description": f"Imported from {len(tagged_assets)} tagged project asset(s).",
                },
            )
            entities.append(entity)
            discoveries[group_id]["items"].append(
                ImportDiscoveryItem(
                    id=f"entity:{entity_key}",
                    kind="entity",
                    title=display_name,
                    subtitle=f"{len(reference_assets)} reference asset{'s' if len(reference_assets) != 1 else ''} from tag '{tag}'",
                    entityKey=entity.entityKey,
                    entityType=entity.entityType,
                    needsReview=needs_review,
                    reasons=reasons,
                    referenceAssets=reference_assets,
                )
            )
        if not assets_by_tag:
            warnings.append("No tagged project assets were found to turn into characters, locations, or reference objects.")

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
                discoveries["story"]["items"].append(
                    ImportDiscoveryItem(
                        id=f"fact:scene:{scene.id}",
                        kind="fact",
                        title=scene.name or f"Scene {scene.index}",
                        subtitle=scene.prompt.strip()[:180],
                        factIndex=len(facts) - 1,
                    )
                )
        if not scenes:
            warnings.append("No scenes found to import as scene facts.")

    grouped_discoveries = [
        ImportDiscoveryGroup(
            id=group_id,
            title=str(group["title"]),
            description=str(group["description"]),
            items=list(group["items"]),
        )
        for group_id, group in discoveries.items()
        if group["items"]
    ]
    character_count = sum(1 for entity in entities if entity.entityType == "character")
    location_count = sum(1 for entity in entities if entity.entityType == "location")
    reference_count = sum(
        len(entity.data.get("referenceAssets", [])) for entity in entities if isinstance(entity.data, dict)
    )
    summary = (
        f"Found {character_count} character idea(s), {location_count} location idea(s), "
        f"{reference_count} reference asset(s), and {len(facts)} story fact(s) ready to shape into Version 1."
    )
    return ImportPreviewResponse(
        projectId=project_id,
        entities=entities,
        facts=facts,
        summary=summary,
        warnings=warnings,
        discoveries=grouped_discoveries,
    )


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
