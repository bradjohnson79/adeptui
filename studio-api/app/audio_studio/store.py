"""Project-scoped Audio Studio persistence (JSON under data/audio_studio)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import settings


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _root(project_id: str) -> Path:
    base = Path(settings.data_dir) / "audio_studio" / project_id
    base.mkdir(parents=True, exist_ok=True)
    return base


def _read(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def list_batches(project_id: str) -> list[dict[str, Any]]:
    path = _root(project_id) / "batches.json"
    items = _read(path, [])
    return items if isinstance(items, list) else []


def save_batch(project_id: str, batch: dict[str, Any]) -> dict[str, Any]:
    items = list_batches(project_id)
    items = [b for b in items if b.get("id") != batch.get("id")]
    items.insert(0, batch)
    _write(_root(project_id) / "batches.json", items[:100])
    return batch


def get_batch(project_id: str, batch_id: str) -> dict[str, Any] | None:
    for b in list_batches(project_id):
        if b.get("id") == batch_id:
            return b
    return None


def get_mix(project_id: str) -> dict[str, Any]:
    return _read(
        _root(project_id) / "mix.json",
        {"clips": {}, "master": {"gain": 1.0, "peak": None, "lufs_integrated": None}},
    )


def save_mix(project_id: str, mix: dict[str, Any]) -> dict[str, Any]:
    mix["updatedAt"] = _now()
    _write(_root(project_id) / "mix.json", mix)
    return mix


def get_draft(project_id: str) -> dict[str, Any]:
    return _read(_root(project_id) / "draft.json", {})


def save_draft(project_id: str, draft: dict[str, Any]) -> dict[str, Any]:
    existing = get_draft(project_id)
    merged = {**existing, **draft, "updatedAt": _now()}
    _write(_root(project_id) / "draft.json", merged)
    return merged


def new_id() -> str:
    return str(uuid.uuid4())
