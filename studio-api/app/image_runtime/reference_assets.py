"""ReferenceAsset architecture (M42 W1) — backbone for IC-LoRA / multi-ref / Bible."""

from __future__ import annotations

from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

ReferenceType = Literal[
    "character",
    "environment",
    "prop",
    "vehicle",
    "wardrobe",
    "lighting",
    "pose",
    "composition",
    "style",
    "palette",
]


class ReferenceAsset(BaseModel):
    referenceId: str = Field(default_factory=lambda: str(uuid4()))
    type: ReferenceType
    displayName: str = ""
    projectId: str = ""
    approvedVersion: Optional[str] = None
    relationships: list[dict[str, Any]] = Field(default_factory=list)
    sourceImages: list[str] = Field(default_factory=list)
    continuityTags: list[str] = Field(default_factory=list)
    identityRegistryRef: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


REFERENCE_TYPES: tuple[str, ...] = (
    "character",
    "environment",
    "prop",
    "vehicle",
    "wardrobe",
    "lighting",
    "pose",
    "composition",
    "style",
    "palette",
)
