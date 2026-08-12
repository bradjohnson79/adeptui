"""JSON store under data/image_pipeline/{project_id}/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import ImageCandidateGroup, ImageGenerationPlan


def _root() -> Path:
    try:
        from ..config import settings

        base = Path(settings.data_dir)
    except Exception:
        base = Path(__file__).resolve().parents[3] / "data"
    return base / "image_pipeline"


def project_dir(project_id: str) -> Path:
    path = _root() / project_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _plans_dir(project_id: str) -> Path:
    path = project_dir(project_id) / "plans"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _groups_dir(project_id: str) -> Path:
    path = project_dir(project_id) / "candidate_groups"
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


def save_plan(plan: ImageGenerationPlan) -> Path:
    payload = plan.model_dump(mode="json")
    return write_json(_plans_dir(plan.projectId) / f"{plan.planId}.json", payload)


def load_plan(project_id: str, plan_id: str) -> ImageGenerationPlan | None:
    payload = read_json(_plans_dir(project_id) / f"{plan_id}.json", None)
    if not isinstance(payload, dict):
        return None
    try:
        return ImageGenerationPlan.model_validate(payload)
    except Exception:
        return None


def save_candidate_group(group: ImageCandidateGroup) -> Path:
    payload = group.model_dump(mode="json")
    return write_json(_groups_dir(group.projectId) / f"{group.groupId}.json", payload)


def load_candidate_group(project_id: str, group_id: str) -> ImageCandidateGroup | None:
    payload = read_json(_groups_dir(project_id) / f"{group_id}.json", None)
    if not isinstance(payload, dict):
        return None
    try:
        return ImageCandidateGroup.model_validate(payload)
    except Exception:
        return None

