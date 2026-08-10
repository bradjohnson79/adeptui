"""Project-level reads shared by the HTTP router and Co-Director tool handlers.

Extracted from `routers/api.py` so the status label a project shows in the library and the
status a Co-Director read tool reports can never drift apart.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from .db import Asset, Job, Project, Scene

ACTIVE_JOB_STATUSES = ("queued", "running", "pending")

_IMAGE_KINDS = frozenset({"image", "imagegen_edit"})
_VIDEO_KINDS = frozenset({"video", "video_upscale"})
_IMAGE_EXTS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"})
_VIDEO_EXTS = frozenset({".mp4", ".webm", ".mov", ".mkv", ".m4v"})


def _asset_created(asset: Asset) -> datetime:
    return getattr(asset, "created_at", None) or datetime.min


def _ext_of(asset: Asset) -> str:
    raw = (getattr(asset, "filename", None) or getattr(asset, "path", None) or "").strip()
    return Path(raw).suffix.lower()


def cover_media_kind(asset: Asset | None) -> str | None:
    """Normalize an asset to `image` / `video` for library card rendering."""
    if asset is None:
        return None
    kind = (asset.kind or "").strip().lower()
    if kind in _IMAGE_KINDS or _ext_of(asset) in _IMAGE_EXTS:
        return "image"
    if kind in _VIDEO_KINDS or _ext_of(asset) in _VIDEO_EXTS:
        return "video"
    return None


def pick_cover_asset(assets: list[Asset]) -> Asset | None:
    """Prefer the newest image still; otherwise the newest video clip."""
    if not assets:
        return None
    images = [a for a in assets if cover_media_kind(a) == "image"]
    if images:
        return max(images, key=_asset_created)
    videos = [a for a in assets if cover_media_kind(a) == "video"]
    if videos:
        return max(videos, key=_asset_created)
    return None


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

    traits: list[str] = []
    try:
        raw_traits = json.loads(getattr(project, "project_traits_json", None) or "[]")
        if isinstance(raw_traits, list):
            traits = [str(t) for t in raw_traits]
    except Exception:
        traits = []
    resolved: dict[str, Any] = {}
    try:
        raw_profile = json.loads(getattr(project, "resolved_profile_json", None) or "{}")
        if isinstance(raw_profile, dict):
            resolved = raw_profile
    except Exception:
        resolved = {}

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
        # M3.1a Project Types / Project Profile (Co-Director awareness)
        "primaryProjectType": getattr(project, "primary_project_type", None) or "custom",
        "projectTraits": traits,
        "projectTypeVersion": int(getattr(project, "project_type_version", 1) or 1),
        "resolvedProfile": {
            "projectType": resolved.get("projectType"),
            "displayName": resolved.get("displayName"),
            "libraryEmphasis": resolved.get("libraryEmphasis") or [],
            "recommendedTemplates": resolved.get("recommendedTemplates") or [],
            "recommendedCameraPresets": resolved.get("recommendedCameraPresets") or [],
            "recommendedLightingPresets": resolved.get("recommendedLightingPresets") or [],
            "recommendedColorPresets": resolved.get("recommendedColorPresets") or [],
            "coDirectorContext": resolved.get("coDirectorContext") or {},
            "structure": resolved.get("structure") or {},
            "delivery": resolved.get("delivery") or [],
            "defaults": resolved.get("defaults") or {},
        },
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
