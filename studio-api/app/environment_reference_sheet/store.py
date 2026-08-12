"""JSON storage for Environment Reference Sheets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import EnvironmentReferenceSheet


def _root() -> Path:
    try:
        from ..config import settings

        base = Path(settings.data_dir)
    except Exception:
        base = Path(__file__).resolve().parents[3] / "data"
    return base / "environment_reference_sheet"


def project_dir(project_id: str) -> Path:
    path = _root() / project_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def sheets_dir(project_id: str) -> Path:
    path = project_dir(project_id) / "sheets"
    path.mkdir(parents=True, exist_ok=True)
    return path


def exports_dir(project_id: str, sheet_id: str) -> Path:
    path = project_dir(project_id) / "exports" / sheet_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return path


def save_sheet(sheet: EnvironmentReferenceSheet) -> Path:
    return _write_json(sheets_dir(sheet.projectId) / f"{sheet.sheetId}.json", sheet.model_dump(mode="json"))


def load_sheet(project_id: str, sheet_id: str) -> EnvironmentReferenceSheet | None:
    payload = _read_json(sheets_dir(project_id) / f"{sheet_id}.json", None)
    if not isinstance(payload, dict):
        return None
    try:
        return EnvironmentReferenceSheet.model_validate(payload)
    except Exception:
        return None


def list_sheets(project_id: str) -> list[EnvironmentReferenceSheet]:
    sheets: list[EnvironmentReferenceSheet] = []
    for path in sorted(sheets_dir(project_id).glob("*.json"), reverse=True):
        payload = _read_json(path, None)
        if not isinstance(payload, dict):
            continue
        try:
            sheets.append(EnvironmentReferenceSheet.model_validate(payload))
        except Exception:
            continue
    return sheets
