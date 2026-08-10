"""Scene reads/writes shared by the HTTP router and Co-Director tool handlers.

Extracted from `routers/api.py` so Co-Director's mutating tools can act on scenes by calling
a service directly instead of round-tripping through the API over HTTP. The router keeps
owning HTTP concerns (404s, response models); this module owns the persistence semantics, so
"create a scene" means exactly the same thing whichever caller asks for it.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from .db import Project, Scene

# Fields that make up a scene's staleness fingerprint — the ones a Co-Director tool proposal
# can target or reason about. Rendering artifacts (`output_path`) are deliberately excluded so
# a finished render doesn't invalidate a pending title/prompt proposal.
_FINGERPRINT_FIELDS = (
    "index",
    "name",
    "engine",
    "prompt",
    "duration_sec",
    "camera_note",
    "continuity_json",
    "seed",
)


def list_scenes(db: Session, project_id: str) -> list[Scene]:
    return db.query(Scene).filter(Scene.project_id == project_id).order_by(Scene.index).all()


def scene_count(db: Session, project_id: str) -> int:
    return db.query(Scene).filter(Scene.project_id == project_id).count()


def get_scene(db: Session, project_id: str, scene_id: str) -> Optional[Scene]:
    """Project-scoped lookup — a scene id from another project is treated as missing."""

    scene = db.get(Scene, scene_id)
    if not scene or scene.project_id != project_id:
        return None
    return scene


def create_scene(
    db: Session,
    project: Project,
    *,
    name: str = "",
    engine: str = "minimax-h3",
    prompt: str = "",
    duration_sec: float = 5.0,
    start_asset_id: Optional[str] = None,
    middle_asset_id: Optional[str] = None,
    end_asset_id: Optional[str] = None,
    audio_asset_id: Optional[str] = None,
    lipsync_enabled: bool = False,
    lipsync_audio_asset_id: Optional[str] = None,
    continuity_json: str = "",
    camera_note: str = "",
    seed: int = -1,
) -> Scene:
    """Append a scene to the end of the project's timeline and touch the project's mtime."""

    count = scene_count(db, project.id)
    scene = Scene(
        id=str(uuid.uuid4()),
        project_id=project.id,
        index=count,
        name=name or f"Scene {count + 1}",
        engine=engine,
        prompt=prompt,
        duration_sec=duration_sec,
        start_asset_id=start_asset_id,
        middle_asset_id=middle_asset_id,
        end_asset_id=end_asset_id,
        audio_asset_id=audio_asset_id,
        lipsync_enabled=1 if lipsync_enabled else 0,
        lipsync_audio_asset_id=lipsync_audio_asset_id,
        continuity_json=continuity_json or "",
        camera_note=camera_note,
        seed=seed,
    )
    db.add(scene)
    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(scene)
    return scene


def update_scene_fields(db: Session, scene: Scene, **fields: Any) -> Scene:
    """Apply a partial update to known columns only, then touch the owning project."""

    for key, value in fields.items():
        if value is None or not hasattr(scene, key):
            continue
        setattr(scene, key, value)
    project = db.get(Project, scene.project_id)
    if project:
        project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(scene)
    return scene


def scene_summary(scene: Scene) -> dict[str, Any]:
    """Compact, model-facing view of a scene (no filesystem paths)."""

    return {
        "sceneId": scene.id,
        "index": scene.index,
        "name": scene.name,
        "engine": scene.engine,
        "durationSec": scene.duration_sec,
        "prompt": scene.prompt or "",
        "cameraNote": scene.camera_note or "",
        "aspectRatio": scene.aspect_ratio,
        "hasOutput": bool(scene.output_path),
        "lipsyncEnabled": bool(scene.lipsync_enabled),
        "seed": scene.seed,
    }


def scene_fingerprint(scene: Scene) -> str:
    """Stable hash of the scene fields a tool proposal can target.

    Used as the scene's entry in a proposal's `baseResourceVersions`: if the fingerprint moves
    between proposing and approving, the scene changed underneath the proposal and it must be
    re-previewed rather than applied blindly.
    """

    canonical = json.dumps(
        {field: getattr(scene, field, None) for field in _FINGERPRINT_FIELDS},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]
