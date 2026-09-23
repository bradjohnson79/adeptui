"""Format-aware production lifecycle — stage gates for Co-Director."""

from .contracts import ProjectProductionLifecycle, ReadinessDepartment, SceneProductionReadiness
from .live_scene_readiness import compute_live_scene_readiness
from .service import (
    advance_script_status,
    assess_scene_readiness_from_project,
    can_formal_cast,
    can_formal_production,
    get_lifecycle,
    mark_complete,
    reopen_complete,
    scene_production_package,
    set_character_cast_status,
    upsert_scene_readiness,
)

__all__ = [
    "ProjectProductionLifecycle",
    "ReadinessDepartment",
    "SceneProductionReadiness",
    "compute_live_scene_readiness",
    "advance_script_status",
    "assess_scene_readiness_from_project",
    "can_formal_cast",
    "can_formal_production",
    "get_lifecycle",
    "mark_complete",
    "reopen_complete",
    "scene_production_package",
    "set_character_cast_status",
    "upsert_scene_readiness",
]
