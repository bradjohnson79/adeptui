"""Thin wrapper — project image model preferences."""

from __future__ import annotations

from ..production_control.store import (
    get_project_preferences,
    get_user_preferences,
    save_project_preferences,
    save_user_preferences,
)


def get_image_preferences(project_id: str) -> dict:
    user = get_user_preferences()
    project = get_project_preferences(project_id)
    return {
        "projectId": project_id,
        "activeModelId": project.activeImageModelId or user.image.activeModelId,
        "routing": user.image.model_dump(),
        "quality": project.imageQuality or user.defaultImageQuality,
    }


def save_image_preferences(project_id: str, patch: dict) -> dict:
    if "routing" in patch:
        user = get_user_preferences()
        routing = {**user.image.model_dump(), **patch["routing"]}
        save_user_preferences({**user.model_dump(), "image": routing})
    project_patch = {
        k: v
        for k, v in patch.items()
        if k in ("activeImageModelId", "imageQuality", "activeModelId")
    }
    if "activeModelId" in project_patch:
        project_patch["activeImageModelId"] = project_patch.pop("activeModelId")
    if project_patch:
        save_project_preferences(project_id, project_patch)
    return get_image_preferences(project_id)
