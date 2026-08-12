"""Project Type / Project Profile application and non-destructive change preview."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..db import Project, Scene
from .catalog.project_types import get_builtin_project_type, list_builtin_project_types
from .resolve import merge_profile, profile_to_dimensions
from .schema import ProjectProfile
from . import store


def _parse_json(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def list_project_types(db: Session, *, primary_only: bool = False) -> list[dict[str, Any]]:
    builtins = [t.to_dict() for t in list_builtin_project_types(primary_only=primary_only)]
    customs = store.list_custom_project_types(db)
    if primary_only:
        return builtins
    # Avoid slug collisions: custom overrides builtin listing for same slug.
    by_slug = {b["slug"]: b for b in builtins}
    for c in customs:
        by_slug[c["slug"]] = {**c, "subtypes": [], "traitOptions": []}
    return list(by_slug.values())


def resolve_project_profile(
    db: Session,
    *,
    primary_type: str,
    traits: list[str] | None = None,
    overrides: dict[str, Any] | None = None,
) -> ProjectProfile:
    custom = store.get_custom_project_type(db, primary_type)
    if custom:
        return merge_profile(
            primary_type,
            traits=traits,
            overrides=overrides,
            custom_definition_profile=custom.get("profile"),
        )
    return merge_profile(primary_type, traits=traits, overrides=overrides)


def seed_production_units(db: Session, project_id: str, profile: ProjectProfile) -> list[dict[str, Any]]:
    existing = store.list_production_units(db, project_id)
    if existing:
        # Non-destructive: do not recreate if units already exist.
        return existing

    created: list[dict[str, Any]] = []
    structure = profile.structure
    leaf_id: str | None = None

    if structure.season_enabled:
        season = store.insert_production_unit(
            db, project_id=project_id, kind="season", name="Season 1", unit_index=0
        )
        created.append(season)
        parent = season["id"]
        if structure.episode_enabled:
            episode = store.insert_production_unit(
                db,
                project_id=project_id,
                kind="episode",
                name="Episode 1",
                parent_id=parent,
                unit_index=0,
            )
            created.append(episode)
            leaf_id = episode["id"]
        else:
            leaf_id = parent
    elif structure.trailer_enabled:
        trailer = store.insert_production_unit(
            db,
            project_id=project_id,
            kind="trailer",
            name="Trailer",
            unit_index=0,
            meta={"deliveryTargets": list(profile.delivery)},
        )
        created.append(trailer)
        parent = trailer["id"]
        if structure.sequence_enabled:
            sequence = store.insert_production_unit(
                db,
                project_id=project_id,
                kind="sequence",
                name="Sequence 1",
                parent_id=parent,
                unit_index=0,
            )
            created.append(sequence)
            parent = sequence["id"]
        if structure.beat_enabled:
            beats = profile.beat_skeleton or ["Hook", "Climax", "Title reveal"]
            for idx, beat_name in enumerate(beats):
                beat = store.insert_production_unit(
                    db,
                    project_id=project_id,
                    kind="beat",
                    name=beat_name,
                    parent_id=parent,
                    unit_index=idx,
                    meta={"editable": True, "mandatory": False},
                )
                created.append(beat)
                if leaf_id is None:
                    leaf_id = beat["id"]
        else:
            leaf_id = parent
    elif structure.episode_enabled:
        episode = store.insert_production_unit(
            db, project_id=project_id, kind="episode", name="Episode 1", unit_index=0
        )
        created.append(episode)
        leaf_id = episode["id"]

    db.commit()

    if leaf_id:
        scene = (
            db.query(Scene)
            .filter(Scene.project_id == project_id)
            .order_by(Scene.index)
            .first()
        )
        if scene and not getattr(scene, "production_unit_id", None):
            scene.production_unit_id = leaf_id
            db.commit()

    return created


def apply_profile_to_project(
    db: Session,
    project: Project,
    profile: ProjectProfile,
    *,
    traits: list[str] | None = None,
    seed_units: bool = True,
    update_dims: bool = True,
) -> dict[str, Any]:
    width, height, fps = profile_to_dimensions(profile)
    if update_dims:
        project.width = width
        project.height = height
        project.fps = fps

    aspect = str(profile.defaults.get("aspectRatio") or "16:9")
    scene = (
        db.query(Scene)
        .filter(Scene.project_id == project.id)
        .order_by(Scene.index)
        .first()
    )
    if scene:
        scene.aspect_ratio = aspect

    project.primary_project_type = profile.project_type
    project.project_traits_json = json.dumps(list(traits or profile.traits or []))
    project.resolved_profile_json = json.dumps(profile.to_dict())
    project.project_type_version = int(profile.version or 1)

    # Soft-compat: keep deprecated defaults_json.production_type in sync for dual-read.
    defaults = _parse_json(getattr(project, "defaults_json", "") or "", {})
    if not isinstance(defaults, dict):
        defaults = {}
    defaults["production_type"] = profile.display_name  # deprecated soft metadata
    defaults["aspect"] = aspect
    defaults["fps"] = fps
    defaults["resolution"] = profile.defaults.get("resolution", "1080p")
    project.defaults_json = json.dumps(defaults)

    settings = _parse_json(getattr(project, "settings_json", "") or "", {})
    if not isinstance(settings, dict):
        settings = {}
    settings["projectType"] = {
        "primary": profile.project_type,
        "traits": list(traits or profile.traits or []),
        "libraryEmphasis": list(profile.library_emphasis),
    }
    project.settings_json = json.dumps(settings)

    db.commit()
    db.refresh(project)

    units: list[dict[str, Any]] = []
    if seed_units:
        units = seed_production_units(db, project.id, profile)

    return {
        "projectId": project.id,
        "profile": profile.to_dict(),
        "productionUnits": units,
        "width": project.width,
        "height": project.height,
        "fps": project.fps,
    }


def preview_project_type_change(
    db: Session,
    project: Project,
    *,
    primary_type: str,
    traits: list[str] | None = None,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    current_profile = ProjectProfile.from_dict(
        _parse_json(getattr(project, "resolved_profile_json", "") or "", {})
    )
    next_profile = resolve_project_profile(
        db, primary_type=primary_type, traits=traits, overrides=overrides
    )
    width, height, fps = profile_to_dimensions(next_profile)
    existing_units = store.list_production_units(db, project.id)
    scene_count = db.query(Scene).filter(Scene.project_id == project.id).count()

    deltas: list[dict[str, Any]] = []
    if project.primary_project_type != next_profile.project_type:
        deltas.append(
            {
                "field": "primaryProjectType",
                "from": project.primary_project_type,
                "to": next_profile.project_type,
                "destructive": False,
            }
        )
    if (project.width, project.height, project.fps) != (width, height, fps):
        deltas.append(
            {
                "field": "dimensions",
                "from": {"width": project.width, "height": project.height, "fps": project.fps},
                "to": {"width": width, "height": height, "fps": fps},
                "destructive": False,
                "note": "Does not relocate or delete assets",
            }
        )
    deltas.append(
        {
            "field": "resolvedProfile",
            "from": current_profile.project_type if current_profile.project_type else None,
            "to": next_profile.project_type,
            "destructive": False,
        }
    )
    deltas.append(
        {
            "field": "libraryEmphasis",
            "from": current_profile.library_emphasis,
            "to": next_profile.library_emphasis,
            "destructive": False,
        }
    )
    if not existing_units and (
        next_profile.structure.season_enabled
        or next_profile.structure.trailer_enabled
        or next_profile.structure.episode_enabled
    ):
        deltas.append(
            {
                "field": "productionUnits",
                "from": [],
                "to": "seed_missing_units_only",
                "destructive": False,
            }
        )
    else:
        deltas.append(
            {
                "field": "productionUnits",
                "from": [u["id"] for u in existing_units],
                "to": "unchanged_existing",
                "destructive": False,
                "note": "Existing units are never deleted on type change",
            }
        )

    return {
        "projectId": project.id,
        "sceneCount": scene_count,
        "assetRelocate": False,
        "assetDelete": False,
        "bibleOverwrite": False,
        "allowed": True,
        "deltas": deltas,
        "nextProfile": next_profile.to_dict(),
        "currentPrimaryType": project.primary_project_type,
        "nextPrimaryType": next_profile.project_type,
        "traits": list(traits or []),
    }


def apply_project_type_change(
    db: Session,
    project: Project,
    *,
    primary_type: str,
    traits: list[str] | None = None,
    overrides: dict[str, Any] | None = None,
    apply_dimension_defaults: bool = True,
) -> dict[str, Any]:
    preview = preview_project_type_change(
        db, project, primary_type=primary_type, traits=traits, overrides=overrides
    )
    if not preview["allowed"]:
        raise ValueError("project_type_change_not_allowed")
    profile = ProjectProfile.from_dict(preview["nextProfile"])
    result = apply_profile_to_project(
        db,
        project,
        profile,
        traits=traits,
        seed_units=True,  # only seeds when empty
        update_dims=apply_dimension_defaults,
    )
    result["preview"] = preview
    return result


def save_custom_type_from_project(
    db: Session,
    project: Project,
    *,
    slug: str,
    display_name: str | None = None,
) -> dict[str, Any]:
    profile_data = _parse_json(getattr(project, "resolved_profile_json", "") or "", {})
    if not profile_data:
        profile = resolve_project_profile(
            db,
            primary_type=project.primary_project_type or "custom",
            traits=_parse_json(getattr(project, "project_traits_json", "") or "", []),
        )
        profile_data = profile.to_dict()
    else:
        profile_data = deepcopy(profile_data)
    profile_data["projectType"] = slug
    profile_data["displayName"] = display_name or slug.replace("_", " ").title()
    return store.save_custom_project_type(
        db,
        slug=slug,
        display_name=profile_data["displayName"],
        profile=profile_data,
        parent_selector=project.primary_project_type,
        group="custom",
    )


def get_project_profile_payload(project: Project) -> dict[str, Any]:
    traits = _parse_json(getattr(project, "project_traits_json", "") or "", [])
    profile = _parse_json(getattr(project, "resolved_profile_json", "") or "", {})
    return {
        "projectId": project.id,
        "primaryProjectType": getattr(project, "primary_project_type", None) or "custom",
        "projectTraits": traits if isinstance(traits, list) else [],
        "projectTypeVersion": int(getattr(project, "project_type_version", 1) or 1),
        "resolvedProfile": profile if isinstance(profile, dict) else {},
    }
