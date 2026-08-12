"""ImageProvenance schema (M42 W1) — QueueWorker write deferred to Wave 2."""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class ImageProvenance(BaseModel):
    workflow: Optional[str] = None
    workflowVersion: Optional[str] = None
    runtime: str = "comfy"
    provider: str = "local"
    references: list[str] = Field(default_factory=list)
    prompt: str = ""
    seed: Optional[int] = None
    parentImages: list[str] = Field(default_factory=list)
    generationTime: Optional[str] = None
    validation: dict[str, Any] = Field(default_factory=dict)
    continuity: dict[str, Any] = Field(default_factory=dict)
    approval: dict[str, Any] = Field(default_factory=dict)
    projectLocation: Optional[str] = None
    intentId: Optional[str] = None
    toolId: Optional[str] = None
    settings: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class EditProvenance(ImageProvenance):
    """Extended provenance for Wave 4 edit operations — backward compatible with ImageProvenance."""

    operation: Optional[str] = None
    maskAssetIds: list[str] = Field(default_factory=list)
    controlAssetIds: list[str] = Field(default_factory=list)
    imageEditIntentId: Optional[str] = None
    sourceAssetId: Optional[str] = None
    controlType: Optional[str] = None
    compositeLayerAssetIds: list[str] = Field(default_factory=list)
    editParameters: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()
