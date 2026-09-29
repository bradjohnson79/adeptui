"""Co-Director → Film Timeline bridge.

Authoring writes a shot and does not render.
Generation is a separate call to the orchestrator.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from .orchestrator import attach_reference, create_shot, update_timed_prompt

log = logging.getLogger("adept.film_timeline")

_TYPE = {
    "character": "character",
    "prop": "prop",
    "environment": "environment",
    "place": "environment",
    "image": "image",
    "video": "video",
}


def author_shot_from_spec(db: Session, spec: Any, references: list[Any], compiled_prompt: str) -> tuple[str, str, int, str]:
    from ..db import Project
    from ..scene_service import create_scene, get_scene, update_scene_fields
    from .store import require_film

    project = db.get(Project, spec.project_id)
    if project is None:
        raise ValueError("Project not found.")
    scene = get_scene(db, spec.project_id, spec.scene_id) if getattr(spec, "scene_id", "") else None
    title = (getattr(spec, "scene_intent", "") or "Scene").strip()[:80] or "Scene"
    if scene is None:
        scene = create_scene(
            db,
            project,
            name=title,
            engine=getattr(spec, "generator_id", None) or "minimax-h3",
            prompt=getattr(spec, "source_user_prompt", "") or compiled_prompt,
            duration_sec=float(getattr(spec, "duration_seconds", 10) or 10),
        )
    update_scene_fields(
        db,
        scene,
        engine=getattr(spec, "generator_id", None) or scene.engine,
        duration_sec=float(getattr(spec, "duration_seconds", scene.duration_sec) or 10),
    )
    human = (getattr(spec, "source_user_prompt", "") or compiled_prompt or "").strip()
    film = require_film(db, spec.project_id, scene.id)
    existing = next((shot for shot in film.shots if shot.id == getattr(spec, "shot_id", "")), None)
    if existing is None:
        created = create_shot(
            db,
            spec.project_id,
            scene.id,
            name=f"Shot {len(film.shots) + 1:02d}",
            duration_sec=float(getattr(spec, "duration_seconds", 10) or 10),
            timed_prompt=human,
            generator_id=getattr(spec, "generator_id", None),
        )
        shot_id = created["shot"]["id"]
    else:
        shot_id = existing.id
        update_timed_prompt(
            db,
            spec.project_id,
            scene.id,
            shot_id,
            human,
            model_prompt=compiled_prompt or "",
        )
    if existing is None and compiled_prompt:
        update_timed_prompt(db, spec.project_id, scene.id, shot_id, human, model_prompt=compiled_prompt)
    for ref in references:
        if getattr(ref, "status", "") != "found":
            continue
        asset_id = getattr(ref, "bindable_asset_id", "") or getattr(ref, "asset_id", "")
        if not asset_id:
            continue
        kind = _TYPE.get(str(getattr(ref, "asset_type", "") or ""), "image")
        attach_reference(
            db,
            spec.project_id,
            scene.id,
            shot_id,
            asset_id=asset_id,
            ref_type=kind,
            label=getattr(ref, "display_name", "") or "",
            scene_level=True,
        )
    film = require_film(db, spec.project_id, scene.id)
    shot = next(item for item in film.shots if item.id == shot_id)
    log.info(
        "codirector timeline author project=%s scene=%s shot=%s rendered=false",
        spec.project_id,
        scene.id,
        shot_id,
    )
    return scene.id, shot_id, int(scene.index or 0), shot.name
