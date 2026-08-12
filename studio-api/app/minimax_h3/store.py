"""JSON persistence for MiniMax H3 plans under data/minimax_h3/{project_id}/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import H3GenerationPlan


def _root() -> Path:
    try:
        from ..config import settings

        base = Path(settings.data_dir)
    except Exception:
        base = Path(__file__).resolve().parents[3] / "data"
    return base / "minimax_h3"


def project_dir(project_id: str) -> Path:
    path = _root() / project_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def plans_dir(project_id: str) -> Path:
    path = project_dir(project_id) / "plans"
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path


def save_plan(plan: H3GenerationPlan) -> Path:
    return write_json(plans_dir(plan.projectId) / f"{plan.planId}.json", plan.model_dump(mode="json"))


def load_plan(project_id: str, plan_id: str) -> H3GenerationPlan | None:
    payload = read_json(plans_dir(project_id) / f"{plan_id}.json", None)
    if not isinstance(payload, dict):
        return None
    try:
        return H3GenerationPlan.model_validate(payload)
    except Exception:
        return None
