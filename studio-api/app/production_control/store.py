"""JSON persistence for Production Control Dock preferences."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from ..config import settings
from .contracts import (
    Modality,
    ModelRoutingPreference,
    PreferenceScope,
    ProjectPreferences,
    ResolvedSelection,
    UserGlobalPreferences,
)
from .model_registry import get_model, list_models

_LOCK = threading.RLock()

_USER_PATH = settings.data_dir / "production_control" / "user_preferences.json"
_PROJECTS_DIR = settings.data_dir / "production_control" / "projects"


def _read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        with tmp.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def default_user_preferences() -> UserGlobalPreferences:
    return UserGlobalPreferences()


def get_user_preferences() -> UserGlobalPreferences:
    with _LOCK:
        raw = _read_json(_USER_PATH, {})
        if not isinstance(raw, dict):
            return default_user_preferences()
        return UserGlobalPreferences.model_validate(raw)


def save_user_preferences(prefs: UserGlobalPreferences | dict[str, Any]) -> UserGlobalPreferences:
    with _LOCK:
        if isinstance(prefs, UserGlobalPreferences):
            model = prefs
        else:
            current = get_user_preferences()
            merged = current.model_dump()
            merged.update(prefs)
            model = UserGlobalPreferences.model_validate(merged)
        _write_json(_USER_PATH, model.model_dump())
        return model


def patch_user_preferences(patch: dict[str, Any]) -> UserGlobalPreferences:
    current = get_user_preferences()
    data = current.model_dump()
    # Accept frontend aliases (llmRouting → llm, etc.)
    alias = {
        "llmRouting": "llm",
        "videoRouting": "video",
        "imageRouting": "image",
        "audioRouting": "audio",
    }
    normalized: dict[str, Any] = {}
    for key, value in patch.items():
        normalized[alias.get(key, key)] = value
    # Derive runtimeSource from Local/API toggles when provided
    if "runtimeLocalEnabled" in normalized or "runtimeApiEnabled" in normalized:
        local_on = bool(normalized.pop("runtimeLocalEnabled", data.get("runtimeSource") in ("local", "hybrid")))
        api_on = bool(normalized.pop("runtimeApiEnabled", data.get("runtimeSource") in ("api", "hybrid")))
        if local_on and api_on:
            normalized["runtimeSource"] = "hybrid"
        elif local_on:
            normalized["runtimeSource"] = "local"
        elif api_on:
            normalized["runtimeSource"] = "api"
        else:
            normalized["runtimeSource"] = "hybrid"
    for key, value in normalized.items():
        if key in ("llm", "video", "image", "audio") and isinstance(value, dict):
            existing = data.get(key) or {}
            if isinstance(existing, dict):
                existing.update(value)
                if "modality" not in existing:
                    existing["modality"] = key
                data[key] = existing
            else:
                data[key] = value
        elif value is not None and key in UserGlobalPreferences.model_fields:
            data[key] = value
    return save_user_preferences(data)


def _project_path(project_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in project_id)
    return _PROJECTS_DIR / f"{safe}.json"


def default_project_preferences(project_id: str) -> ProjectPreferences:
    return ProjectPreferences(projectId=project_id)


def get_project_preferences(project_id: str) -> ProjectPreferences:
    with _LOCK:
        raw = _read_json(_project_path(project_id), {"projectId": project_id})
        if not isinstance(raw, dict):
            return default_project_preferences(project_id)
        raw.setdefault("projectId", project_id)
        return ProjectPreferences.model_validate(raw)


def save_project_preferences(
    project_id: str, prefs: ProjectPreferences | dict[str, Any]
) -> ProjectPreferences:
    with _LOCK:
        if isinstance(prefs, ProjectPreferences):
            model = prefs
        else:
            current = get_project_preferences(project_id)
            merged = current.model_dump()
            merged.update(prefs)
            merged["projectId"] = project_id
            model = ProjectPreferences.model_validate(merged)
        _write_json(_project_path(project_id), model.model_dump())
        return model


def _modality_routing(user: UserGlobalPreferences, modality: Modality) -> ModelRoutingPreference:
    return getattr(user, modality)


def _project_active_model_id(project: ProjectPreferences, modality: Modality) -> str | None:
    if modality == "video":
        return project.activeVideoModelId
    if modality == "image":
        return project.activeImageModelId
    if modality == "audio":
        return project.activeAudioModelId
    if modality == "llm":
        return project.codirectorModelId
    return None


def resolve_with_precedence(project_id: str, modality: Modality) -> ResolvedSelection:
    """Apply precedence: project → user → system."""
    user = get_user_preferences()
    project = get_project_preferences(project_id)
    routing = _modality_routing(user, modality)

    active_id: str | None = None
    source: PreferenceScope = "system"

    project_active = _project_active_model_id(project, modality)
    if project_active:
        active_id = project_active
        source = "project"
    elif routing.activeModelId:
        active_id = routing.activeModelId
        source = "user"

    descriptor = get_model(active_id) if active_id else None
    active_label = descriptor.label if descriptor else (active_id or "System default")

    return ResolvedSelection(
        modality=modality,
        activeModelId=active_id,
        activeLabel=active_label,
        source=source,
        fallbackPolicy=user.cpuFallbackPolicy,
        gpu="Unknown",
        executable=bool(descriptor.executable) if descriptor else False,
        blockedReason=None if (descriptor and descriptor.executable) else "No active model selected",
        runtime=descriptor.providerId if descriptor else None,
        providerId=descriptor.providerId if descriptor else None,
        cpuFallbackPolicy=user.cpuFallbackPolicy,
        availableModelIds=list(routing.availableModelIds)
        or [m.id for m in list_models(modality)],
        fallbackModelId=routing.fallbackModelId,
        allowFallback=routing.allowFallback,
        provenance={
            "activeModelId": active_id,
            "activeLabel": active_label,
            "source": source,
            "fallbackPolicy": user.cpuFallbackPolicy,
            "gpu": "Unknown",
            "executable": bool(descriptor.executable) if descriptor else False,
            "blockedReason": None,
            "runtime": descriptor.providerId if descriptor else None,
            "providerId": descriptor.providerId if descriptor else None,
            "cpuFallbackPolicy": user.cpuFallbackPolicy,
        },
    )
