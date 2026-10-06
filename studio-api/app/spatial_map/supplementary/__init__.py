"""Qwen supplementary environment views — inferred reasoning support only."""

from .contracts import (
    CAMERA_ROLES,
    SUPPLEMENTARY_PURPOSE,
    SUPPLEMENTARY_TASK_CLASS,
    CameraRole,
    SpatialReferenceRecord,
    SupplementaryState,
    observed_asset_ids,
)
from .confidence import summarize_confidence
from .gate import evaluate_set_gate, evaluate_view_gate
from .select import select_camera_role
from .service import (
    accept_view,
    analyze_next_view,
    generate_view,
    get_state,
    regenerate_view,
    reject_view,
    write_contact_sheet,
    write_owner_review_strip,
)

__all__ = [
    "CAMERA_ROLES",
    "SUPPLEMENTARY_PURPOSE",
    "SUPPLEMENTARY_TASK_CLASS",
    "CameraRole",
    "SpatialReferenceRecord",
    "SupplementaryState",
    "accept_view",
    "analyze_next_view",
    "evaluate_set_gate",
    "evaluate_view_gate",
    "generate_view",
    "get_state",
    "observed_asset_ids",
    "regenerate_view",
    "reject_view",
    "select_camera_role",
    "summarize_confidence",
    "write_contact_sheet",
    "write_owner_review_strip",
]
