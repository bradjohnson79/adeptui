"""Thin wrapper — project video model preferences."""

from __future__ import annotations

from ..production_control.store import (
    get_project_preferences,
    get_user_preferences,
    save_project_preferences,
    save_user_preferences,
)


def get_video_preferences(project_id: str) -> dict:
    user = get_user_preferences()
    project = get_project_preferences(project_id)
    return {
        "projectId": project_id,
        "activeModelId": project.activeVideoModelId or user.video.activeModelId,
        "routing": user.video.model_dump(),
        "quality": project.videoQuality or user.defaultVideoQuality,
    }


def save_video_preferences(project_id: str, patch: dict) -> dict:
    if "routing" in patch:
        user = get_user_preferences()
        routing = {**user.video.model_dump(), **patch["routing"]}
        save_user_preferences({**user.model_dump(), "video": routing})
    project_patch = {
        k: v
        for k, v in patch.items()
        if k in ("activeVideoModelId", "videoQuality", "activeModelId")
    }
    if "activeModelId" in project_patch:
        project_patch["activeVideoModelId"] = project_patch.pop("activeModelId")
    if project_patch:
        save_project_preferences(project_id, project_patch)
    return get_video_preferences(project_id)
