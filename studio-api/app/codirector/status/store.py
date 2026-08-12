from __future__ import annotations

import json
from pathlib import Path
from threading import RLock
from typing import Optional

from ...config import settings
from .types import HealthRun

_LOCK = RLock()
_LIMIT = 20


def _store_path() -> Path:
    path = settings.data_dir / "codirector" / "status"
    path.mkdir(parents=True, exist_ok=True)
    return path / "history.json"


def _load_rows() -> list[dict]:
    path = _store_path()
    if not path.is_file():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_rows(rows: list[dict]) -> None:
    _store_path().write_text(json.dumps(rows[:_LIMIT], indent=2), encoding="utf-8")


def persist_run(run: HealthRun) -> None:
    with _LOCK:
        rows = _load_rows()
        rows.insert(0, run.model_dump(mode="json"))
        _save_rows(rows)


def list_runs(*, project_id: Optional[str] = None, scene_id: Optional[str] = None, limit: int = 20) -> list[HealthRun]:
    with _LOCK:
        rows = _load_rows()
    runs: list[HealthRun] = []
    for row in rows:
        if project_id and row.get("projectId") != project_id:
            continue
        if scene_id and row.get("sceneId") != scene_id:
            continue
        runs.append(HealthRun.model_validate(row))
        if len(runs) >= max(1, min(limit, _LIMIT)):
            break
    return runs


def latest_run(*, project_id: Optional[str] = None, scene_id: Optional[str] = None) -> Optional[HealthRun]:
    rows = list_runs(project_id=project_id, scene_id=scene_id, limit=1)
    return rows[0] if rows else None
