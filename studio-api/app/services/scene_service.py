"""Scene CRUD as an application service.

Scene logic used to live inline in `routers/api.py`, which meant the only way to create or
edit a scene was an HTTP round trip. Pulling it out gives three things the capability
registry depends on:

* a callable entry point (`SceneService.*`) that the registry can name in `service_ref`,
* one place where scene invariants live — contiguous indices, project ownership, partial
  updates — instead of three copies across routes,
* structured, code-carrying failures (`PROJECT_NOT_FOUND`, `SCENE_NOT_FOUND`) so a caller can
  branch on the reason rather than parsing prose.

The service takes an explicit `Session` and never commits on behalf of a caller that passes
`commit=False`, so a router can compose several operations in one transaction.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Iterable, Mapping, Optional

from sqlalchemy.orm import Session

from ..capabilities.errors import (
    PROJECT_NOT_FOUND,
    SCENE_NOT_FOUND,
    VALIDATION_ERROR,
    CapabilityError,
)
from ..db import Project, Scene

#: Fields a caller may set on a scene. `id`, `project_id`, `index`, and the output paths are
#: owned by the service (or by the render pipeline) and are deliberately not writable here.
WRITABLE_FIELDS: frozenset[str] = frozenset(
    {
        "name",
        "summary",
        "engine",
        "prompt",
        "duration_sec",
        "start_asset_id",
        "middle_asset_id",
        "end_asset_id",
        "audio_asset_id",
        "lipsync_enabled",
        "lipsync_audio_asset_id",
        "lipsync_tracks_json",
        "director_json",
        "continuity_json",
        "camera_note",
        "seed",
        "aspect_ratio",
        "width",
        "height",
        "fps_mode",
        "fps",
    }
)

_INT_FLAG_FIELDS = frozenset({"lipsync_enabled"})


def _project_not_found(project_id: str) -> CapabilityError:
    return CapabilityError(
        code=PROJECT_NOT_FOUND,
        message="Project not found",
        details={"projectId": project_id},
        recoverable=False,
        recommended_action="open_project",
    )


def _scene_not_found(project_id: str, scene_id: str) -> CapabilityError:
    return CapabilityError(
        code=SCENE_NOT_FOUND,
        message="Scene not found",
        details={"projectId": project_id, "sceneId": scene_id},
        recoverable=False,
        recommended_action="reload_project",
    )


def _coerce(field: str, value: Any) -> Any:
    if field in _INT_FLAG_FIELDS:
        return 1 if value else 0
    if field in ("lipsync_tracks_json", "director_json", "continuity_json") and value is None:
        # These are non-nullable Text columns; None means "leave as empty", not NULL.
        return ""
    return value


class SceneService:
    """Scene operations for one project. Stateless; every method takes the session."""

    @staticmethod
    def require_project(db: Session, project_id: str) -> Project:
        project = db.get(Project, project_id)
        if project is None:
            raise _project_not_found(project_id)
        return project

    @staticmethod
    def list_for_project(db: Session, project_id: str) -> list[Scene]:
        """Scenes in timeline order. Does not require the project to exist."""
        return (
            db.query(Scene)
            .filter(Scene.project_id == project_id)
            .order_by(Scene.index)
            .all()
        )

    @staticmethod
    def count_for_project(db: Session, project_id: str) -> int:
        return db.query(Scene).filter(Scene.project_id == project_id).count()

    @staticmethod
    def get(db: Session, project_id: str, scene_id: str) -> Scene:
        """One scene, enforcing project ownership so ids cannot be probed across projects."""
        scene = db.get(Scene, scene_id)
        if scene is None or scene.project_id != project_id:
            raise _scene_not_found(project_id, scene_id)
        return scene

    @classmethod
    def create(
        cls,
        db: Session,
        project_id: str,
        values: Mapping[str, Any] | None = None,
        *,
        commit: bool = True,
    ) -> Scene:
        """Append a scene at the end of the timeline."""
        project = cls.require_project(db, project_id)
        data = {
            key: _coerce(key, value)
            for key, value in (values or {}).items()
            if key in WRITABLE_FIELDS
        }
        index = cls.count_for_project(db, project_id)
        scene = Scene(
            id=str(uuid.uuid4()),
            project_id=project_id,
            index=index,
            name=data.pop("name", None) or f"Scene {index + 1}",
        )
        for field, value in data.items():
            if value is not None:
                setattr(scene, field, value)
        db.add(scene)
        project.updated_at = datetime.utcnow()
        if commit:
            db.commit()
            db.refresh(scene)
        else:
            db.flush()
        return scene

    @classmethod
    def create_many(
        cls,
        db: Session,
        project_id: str,
        rows: Iterable[Mapping[str, Any]],
        *,
        replace_existing: bool = False,
        commit: bool = True,
    ) -> list[Scene]:
        """Append (or replace) a batch of scenes, keeping indices contiguous.

        Used by the timeline apply path, which is destructive when `replace_existing` is set
        and therefore always gated behind an explicit user action upstream.
        """
        project = cls.require_project(db, project_id)
        existing = cls.list_for_project(db, project_id)
        if replace_existing:
            for scene in existing:
                db.delete(scene)
            db.flush()
            start_index = 0
        else:
            start_index = len(existing)

        created: list[Scene] = []
        for offset, values in enumerate(rows):
            index = start_index + offset
            data = {
                key: _coerce(key, value)
                for key, value in values.items()
                if key in WRITABLE_FIELDS
            }
            scene = Scene(
                id=str(uuid.uuid4()),
                project_id=project_id,
                index=index,
                name=data.pop("name", None) or f"Scene {index + 1}",
            )
            for field, value in data.items():
                if value is not None:
                    setattr(scene, field, value)
            db.add(scene)
            created.append(scene)

        project.updated_at = datetime.utcnow()
        if commit:
            db.commit()
            for scene in created:
                db.refresh(scene)
        else:
            db.flush()
        return created

    @classmethod
    def update(
        cls,
        db: Session,
        project_id: str,
        scene_id: str,
        values: Mapping[str, Any],
        *,
        commit: bool = True,
    ) -> Scene:
        """Apply a partial update.

        Only keys present in `values` are written. This is what PATCH always claimed to do —
        the previous router code dumped the whole request model, so any field the client left
        out was silently reset to the schema default (a prompt could be blanked by a request
        that only meant to rename a scene).
        """
        scene = cls.get(db, project_id, scene_id)
        unknown = sorted(set(values) - WRITABLE_FIELDS)
        if unknown:
            raise CapabilityError(
                code=VALIDATION_ERROR,
                message="Unknown or read-only scene field(s): " + ", ".join(unknown),
                details={"fields": unknown},
                recommended_action="review_request",
            )
        for field, value in values.items():
            setattr(scene, field, _coerce(field, value))
        project = db.get(Project, project_id)
        if project is not None:
            project.updated_at = datetime.utcnow()
        if commit:
            db.commit()
            db.refresh(scene)
        else:
            db.flush()
        return scene

    @classmethod
    def delete(
        cls,
        db: Session,
        project_id: str,
        scene_id: str,
        *,
        commit: bool = True,
    ) -> None:
        """Delete a scene and re-pack the remaining indices so the timeline has no gaps."""
        scene = cls.get(db, project_id, scene_id)
        db.delete(scene)
        db.flush()
        cls.repack_indices(db, project_id)
        project = db.get(Project, project_id)
        if project is not None:
            project.updated_at = datetime.utcnow()
        if commit:
            db.commit()

    @classmethod
    def repack_indices(cls, db: Session, project_id: str) -> None:
        for position, scene in enumerate(cls.list_for_project(db, project_id)):
            if scene.index != position:
                scene.index = position

    @staticmethod
    def describe(scene: Scene) -> dict[str, Any]:
        """Compact, agent-readable view of a scene (no generation internals)."""
        return {
            "id": scene.id,
            "index": scene.index,
            "name": scene.name,
            "summary": getattr(scene, "summary", "") or "",
            "durationSec": scene.duration_sec,
            "engine": scene.engine,
            "hasPrompt": bool((scene.prompt or "").strip()),
            "rendered": bool(scene.output_path),
        }


def scene_summary_or_prompt(scene: Scene, *, limit: int = 160) -> Optional[str]:
    """Best available short description: the summary if set, else a clipped prompt."""
    summary = (getattr(scene, "summary", "") or "").strip()
    if summary:
        return summary
    prompt = (scene.prompt or "").strip()
    if not prompt:
        return None
    return prompt if len(prompt) <= limit else prompt[: limit - 1].rstrip() + "…"
