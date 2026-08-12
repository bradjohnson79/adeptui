"""Persist Model Storage roots and registered external folders (paths only — no silent copy)."""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import settings

_LOCK = threading.RLock()

DEFAULT_PREFERRED_ROOT = r"D:\01_Models"

ROOT_CATEGORIES = (
    "default",
    "llm",
    "ollama",
    "image",
    "video",
    "audio",
    "voice",
    "3d",
    "temp_cache",
)

#: Krea 2 weights live in this subtree under the existing "image" category root —
#: no separate storage root is created or required.
KREA2_SUBTREE_NAME = "krea2"


def storage_path() -> Path:
    return settings.data_dir / "model_storage.json"


def _defaults() -> dict[str, Any]:
    preferred = str(getattr(settings, "minimax_h3_model_root", None) or DEFAULT_PREFERRED_ROOT)
    roots = {cat: preferred for cat in ROOT_CATEGORIES}
    roots["temp_cache"] = str(Path(settings.data_dir) / "model_cache")
    return {
        "schemaVersion": 1,
        "preferredRoot": preferred,
        "roots": roots,
        "registeredFolders": [],
    }


def _normalize(raw: Any) -> dict[str, Any]:
    base = _defaults()
    if not isinstance(raw, dict):
        return base
    preferred = str(raw.get("preferredRoot") or base["preferredRoot"]).strip() or base["preferredRoot"]
    roots_in = raw.get("roots") if isinstance(raw.get("roots"), dict) else {}
    roots = dict(base["roots"])
    for cat in ROOT_CATEGORIES:
        if cat in roots_in and roots_in[cat]:
            roots[cat] = str(roots_in[cat]).strip()
    folders = raw.get("registeredFolders")
    if not isinstance(folders, list):
        folders = []
    clean_folders = [f for f in folders if isinstance(f, dict) and f.get("path")]
    return {
        "schemaVersion": 1,
        "preferredRoot": preferred,
        "roots": roots,
        "registeredFolders": clean_folders,
    }


def load_model_storage() -> dict[str, Any]:
    with _LOCK:
        path = storage_path()
        if not path.exists():
            return _defaults()
        try:
            return _normalize(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            return _defaults()


def save_model_storage(state: dict[str, Any]) -> dict[str, Any]:
    with _LOCK:
        clean = _normalize(state)
        path = storage_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        try:
            with tmp.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(clean, handle, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, path)
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
        return clean


def get_roots() -> dict[str, str]:
    return dict(load_model_storage()["roots"])


def krea2_image_root() -> Path:
    """Krea 2 subtree under the Model Storage "image" category root."""
    roots = get_roots()
    base = roots.get("image") or roots.get("default") or DEFAULT_PREFERRED_ROOT
    return Path(base) / KREA2_SUBTREE_NAME


def krea2_registration_status() -> dict[str, Any]:
    """Discoverability check for the Krea 2 subtree under the image model root.

    Reports whether the subtree exists on disk and whether a Source Manager
    registration already covers it (exact folder or an ancestor image root).
    """
    path = krea2_image_root()
    roots = get_roots()
    image_root = roots.get("image") or ""
    exists = path.is_dir()
    registered = False
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    for folder in get_registered_folders():
        raw = str(folder.get("path") or "")
        if not raw:
            continue
        try:
            candidate = Path(raw).expanduser().resolve()
        except OSError:
            candidate = Path(raw).expanduser()
        if candidate == resolved:
            registered = True
            break
        try:
            if resolved.is_relative_to(candidate):
                registered = True
                break
        except ValueError:
            continue
    return {
        "path": str(path),
        "category": "image",
        "imageCategoryRoot": image_root,
        "exists": exists,
        "registered": registered,
        "discoverable": exists or registered,
    }


def set_root(category: str, path: str) -> dict[str, Any]:
    cat = (category or "").strip().lower()
    if cat not in ROOT_CATEGORIES:
        raise ValueError(f"Unknown root category: {category}")
    value = str(path or "").strip()
    if not value:
        raise ValueError("path is required")
    state = load_model_storage()
    state["roots"][cat] = value
    if cat == "default":
        state["preferredRoot"] = value
    return save_model_storage(state)


def get_registered_folders() -> list[dict[str, Any]]:
    return list(load_model_storage().get("registeredFolders") or [])


def register_folder(
    *,
    path: str,
    runtime_type: str | None = None,
    label: str | None = None,
    category: str = "llm",
    metadata: dict[str, Any] | None = None,
    import_into_library: bool = False,
) -> dict[str, Any]:
    """Register an existing folder by path. Never copies unless import_into_library is True."""
    from .classify import classify_folder
    from .validate import validate_registration

    folder = Path(path).expanduser()
    abs_path = str(folder.resolve()) if folder.exists() else str(folder)
    classification = classify_folder(abs_path)
    runtime = (runtime_type or classification.get("runtimeType") or "unknown").strip()
    validation = validate_registration(abs_path, runtime_type=runtime)
    now = datetime.now(timezone.utc).isoformat()
    entry = {
        "id": str(uuid.uuid4()),
        "path": abs_path,
        "label": (label or classification.get("label") or folder.name or abs_path).strip(),
        "category": (category or "llm").strip().lower(),
        "runtimeType": runtime,
        "classification": classification,
        "validationStatus": validation.get("status"),
        "validation": validation,
        "metadata": dict(metadata or {}),
        "imported": False,
        "importDestination": None,
        "discoveredAt": now,
        "updatedAt": now,
    }
    if import_into_library:
        dest = _import_copy(abs_path, category=entry["category"])
        entry["imported"] = True
        entry["importDestination"] = dest
        entry["metadata"]["importDisclosed"] = True
    state = load_model_storage()
    # Replace existing registration for same path
    folders = [
        f
        for f in state.get("registeredFolders") or []
        if str(f.get("path") or "").lower() != abs_path.lower()
    ]
    folders.append(entry)
    state["registeredFolders"] = folders
    save_model_storage(state)
    return entry


def unregister_folder(folder_id: str) -> bool:
    state = load_model_storage()
    before = len(state.get("registeredFolders") or [])
    state["registeredFolders"] = [
        f for f in state.get("registeredFolders") or [] if f.get("id") != folder_id
    ]
    save_model_storage(state)
    return len(state["registeredFolders"]) < before


def refresh_registration(folder_id: str) -> dict[str, Any] | None:
    state = load_model_storage()
    for i, f in enumerate(state.get("registeredFolders") or []):
        if f.get("id") != folder_id:
            continue
        from .classify import classify_folder
        from .validate import validate_registration

        path = str(f.get("path") or "")
        classification = classify_folder(path)
        runtime = str(f.get("runtimeType") or classification.get("runtimeType") or "unknown")
        validation = validate_registration(path, runtime_type=runtime)
        f = {
            **f,
            "classification": classification,
            "runtimeType": runtime,
            "validationStatus": validation.get("status"),
            "validation": validation,
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }
        state["registeredFolders"][i] = f
        save_model_storage(state)
        return f
    return None


def _import_copy(source: str, *, category: str) -> str:
    """Explicit import: copy into Adept-managed library under preferred/default root."""
    import shutil

    src = Path(source)
    if not src.exists():
        raise FileNotFoundError(f"Source path not found: {source}")
    roots = get_roots()
    dest_root = Path(roots.get(category) or roots.get("default") or DEFAULT_PREFERRED_ROOT) / "adept_library" / category
    dest_root.mkdir(parents=True, exist_ok=True)
    dest = dest_root / src.name
    if src.is_dir():
        if dest.exists():
            dest = dest_root / f"{src.name}_{uuid.uuid4().hex[:8]}"
        shutil.copytree(src, dest)
    else:
        if dest.exists():
            dest = dest_root / f"{src.stem}_{uuid.uuid4().hex[:8]}{src.suffix}"
        shutil.copy2(src, dest)
    return str(dest)
