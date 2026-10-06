"""Project-isolated selection cache. Invalidate on asset / frame / model change."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Optional

from ...config import settings


CACHE_VERSION = "selection-cache-v1"


def _root() -> Path:
    return Path(settings.data_dir) / "cache" / "perception_selections"


def _key(
    project_id: str,
    asset_id: str,
    frame_time_ms: int | None,
    entity: str,
    model_id: str,
    model_version: str,
    source: str,
) -> str:
    raw = "|".join(
        [
            project_id,
            asset_id,
            str(frame_time_ms if frame_time_ms is not None else ""),
            entity.strip().lower(),
            model_id,
            model_version,
            source,
            CACHE_VERSION,
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _path(project_id: str, cache_key: str) -> Path:
    folder = _root() / project_id
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{cache_key}.json"


def get_cached_selection(
    *,
    project_id: str,
    asset_id: str,
    frame_time_ms: int | None,
    entity: str,
    model_id: str,
    model_version: str,
    source: str,
) -> Optional[dict[str, Any]]:
    if not project_id or not asset_id:
        return None
    key = _key(project_id, asset_id, frame_time_ms, entity, model_id, model_version, source)
    path = _path(project_id, key)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        path.unlink(missing_ok=True)
        return None
    if data.get("projectId") != project_id:
        path.unlink(missing_ok=True)
        return None
    return data


def set_cached_selection(
    packet: dict[str, Any],
    *,
    entity: str,
    source: str,
) -> str:
    project_id = str(packet.get("projectId") or "")
    asset_id = str(packet.get("assetId") or "")
    key = _key(
        project_id,
        asset_id,
        packet.get("frameTimeMs"),
        entity,
        str(packet.get("modelId") or ""),
        str(packet.get("modelVersion") or ""),
        source,
    )
    path = _path(project_id, key)
    payload = dict(packet)
    payload["cacheKey"] = key
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return key


def store_packet(packet: dict[str, Any]) -> Path:
    project_id = str(packet.get("projectId") or "")
    selection_id = str(packet.get("selectionId") or "")
    folder = Path(settings.data_dir) / "image_product" / project_id / "selections"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{selection_id}.json"
    path.write_text(json.dumps(packet, indent=2), encoding="utf-8")
    return path


def load_packet(project_id: str, selection_id: str) -> Optional[dict[str, Any]]:
    path = Path(settings.data_dir) / "image_product" / project_id / "selections" / f"{selection_id}.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if data.get("projectId") != project_id:
        return None
    return data


def store_track(project_id: str, tracking_id: str, payload: dict[str, Any]) -> Path:
    folder = Path(settings.data_dir) / "image_product" / project_id / "tracks"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{tracking_id}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def load_track(project_id: str, tracking_id: str) -> Optional[dict[str, Any]]:
    path = Path(settings.data_dir) / "image_product" / project_id / "tracks" / f"{tracking_id}.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if data.get("projectId") != project_id:
        return None
    return data
