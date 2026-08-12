"""JSON file store under data/image_product/{project_id}/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _root() -> Path:
    try:
        from ..config import settings

        base = Path(settings.data_dir)
    except Exception:
        base = Path(__file__).resolve().parents[3] / "data"
    return base / "image_product"


def project_dir(project_id: str) -> Path:
    d = _root() / project_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def read_json(project_id: str, name: str, default: Any) -> Any:
    path = project_dir(project_id) / name
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(project_id: str, name: str, data: Any) -> Path:
    path = project_dir(project_id) / name
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return path
