"""Project-level reads shared by the HTTP router and Co-Director tool handlers.

Extracted from `routers/api.py` so the status label a project shows in the library and the
status a Co-Director read tool reports can never drift apart.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from .db import Asset, Job, Project, Scene

ACTIVE_JOB_STATUSES = ("queued", "running", "pending")


def status_label(*, archived: bool, active_jobs: int, scene_count: int, scenes_with_output: int) -> str:
    """The library's status heuristic, in one place."""

    if archived:
        return "Archived"
    if active_jobs:
        return "Rendering"
    if scene_count and scenes_with_output >= scene_count:
        return "Complete"
    return "Active"


def active_job_count(db: Session, project_id: str) -> int:
    return (
        db.query(Job)
        .filter(Job.project_id == project_id, Job.status.in_(list(ACTIVE_JOB_STATUSES)))
        .count()
    )


def _parse_tags(raw: str) -> list[str]:
    try:
        tags = json.loads(raw or "[]")
    except Exception:
        return []
    return [str(t) for t in tags] if isinstance(tags, list) else []


def project_profile(project: Project) -> dict[str, Any]:
    """Identity/format metadata for a project — the model-facing project profile."""

    return {
        "projectId": project.id,
        "name": project.name,
        "description": getattr(project, "description", "") or "",
        "company": getattr(project, "company", "") or "",
        "directorName": getattr(project, "director_name", "") or "",
        "version": getattr(project, "version", "1.0") or "1.0",
        "tags": _parse_tags(getattr(project, "tags_json", "[]") or "[]"),
        "engineDefault": project.engine_default,
        "width": project.width,
        "height": project.height,
        "fps": project.fps,
        "preset": project.preset,
        "vramGb": getattr(project, "vram_gb", None),
        "globalPrompt": project.global_prompt or "",
        "negativePrompt": project.negative_prompt or "",
        "archived": bool(getattr(project, "archived", 0)),
        "updatedAt": project.updated_at.isoformat() if project.updated_at else None,
    }


def project_status(db: Session, project: Project) -> dict[str, Any]:
    """Counts + derived status label for a project."""

    scenes = db.query(Scene).filter(Scene.project_id == project.id).all()
    scenes_with_output = sum(1 for s in scenes if getattr(s, "output_path", None))
    asset_count = db.query(Asset).filter(Asset.project_id == project.id).count()
    active_jobs = active_job_count(db, project.id)
    return {
        "projectId": project.id,
        "statusLabel": status_label(
            archived=bool(getattr(project, "archived", 0)),
            active_jobs=active_jobs,
            scene_count=len(scenes),
            scenes_with_output=scenes_with_output,
        ),
        "sceneCount": len(scenes),
        "scenesWithOutput": scenes_with_output,
        "assetCount": asset_count,
        "activeJobCount": active_jobs,
        "renderPct": int(100 * scenes_with_output / max(1, len(scenes))) if scenes else 0,
        "updatedAt": project.updated_at.isoformat() if project.updated_at else None,
    }


def project_version_token(project: Optional[Project]) -> Optional[str]:
    """Staleness token for a project: its last-modified timestamp."""

    if project is None or not project.updated_at:
        return None
    return project.updated_at.isoformat()
