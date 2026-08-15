"""Image Core request / decision / result types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

IMAGE_CORE_PURPOSES = (
    "scene_shot_preview",
    "scene_shot_final",
    "region_edit",
    "final_region_edit",
)


@dataclass
class ImageCoreRequest:
    project_id: str
    purpose: str
    operation: str
    model_id: str = ""
    prompt: str = ""
    negative_prompt: str = ""
    provider: str = "local"
    hosted_model_id: str = ""
    source_asset_id: str = ""
    mask_asset_id: str = ""
    edit_operation: str = ""
    expand: str = ""
    feather: str = ""
    seed: int | None = None
    scene_id: str = ""
    shot_id: str = ""
    tag: str = ""
    lock_model_family: bool = True
    creative_context: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class CapabilityDecision:
    ok: bool
    code: str = ""
    message: str = ""
    family: str = ""
    workflow_key: str = ""
    runtime_operation: str = ""
    width: int = 0
    height: int = 0
    denoise: float | None = None
    grow_mask_by: int | None = None
    recommended_family: str = ""
    supported: bool = False
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedEnqueue:
    job_id: str
    status: str
    workflow_key: str = ""
    family: str = ""
    operation: str = ""
    width: int = 0
    height: int = 0
    fallback_applied: bool = False
    error: str = ""
    job: Any = None
    decision: CapabilityDecision | None = None
