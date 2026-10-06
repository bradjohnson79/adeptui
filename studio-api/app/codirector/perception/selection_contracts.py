"""Revision D selection contract. Single mask representation for all tools."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from .contracts import PROVIDER_LEAK_KEYS, NormalizedBox

SELECTION_SCHEMA = "selection-v1"

SelectionRole = Literal["include", "exclude", "replace", "subject", "background"]
SelectionSource = Literal["click", "box", "text", "subject", "background", "track", "refine"]
SelectionKind = Literal["subject", "background", "object", "person", "prop", "region"]


def _sid(prefix: str = "sel_") -> str:
    return f"{prefix}{uuid4().hex[:12]}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PerceptionSelectionPacket(BaseModel):
    """Canonical selection. Persist mask bytes via image_product.masks, not here."""

    schemaVersion: str = SELECTION_SCHEMA
    selectionId: str = Field(default_factory=_sid)
    projectId: str = ""
    assetId: str = ""
    frameTimeMs: Optional[int] = None
    entityId: str = ""
    semanticLabel: str = ""
    kind: SelectionKind = "object"
    maskAssetId: str = ""
    bounds: Optional[NormalizedBox] = None
    confidence: Optional[float] = None
    role: SelectionRole = "include"
    source: SelectionSource = "click"
    modelId: str = "sam21-hiera-tiny"
    modelVersion: str = ""
    promptModelId: str = ""
    trackingId: str = ""
    worldStateRef: str = ""
    createdAt: str = Field(default_factory=_now)
    provenance: dict[str, Any] = Field(default_factory=dict)

    @field_validator("provenance")
    @classmethod
    def _no_logits(cls, value: dict[str, Any]) -> dict[str, Any]:
        leaked = PROVIDER_LEAK_KEYS.intersection(value.keys())
        if leaked:
            raise ValueError(f"provider payload leaked into selection provenance: {sorted(leaked)}")
        return value


class SelectRequest(BaseModel):
    assetId: str
    point: Optional[dict[str, float]] = None
    box: Optional[dict[str, float]] = None
    label: str = ""
    kind: SelectionKind = "object"
    role: SelectionRole = "include"
    frameTimeMs: Optional[int] = None
    mapId: str = ""


class RefineRequest(BaseModel):
    addPoints: list[dict[str, float]] = Field(default_factory=list)
    removePoints: list[dict[str, float]] = Field(default_factory=list)
    brushPngBase64: str = ""
    role: Optional[SelectionRole] = None


class TrackRequest(BaseModel):
    assetId: str
    seedSelectionId: str = ""
    point: Optional[dict[str, float]] = None
    box: Optional[dict[str, float]] = None
    label: str = ""
    frameTimesMs: list[int] = Field(default_factory=list)
    role: SelectionRole = "include"


class RemoveBackgroundRequest(BaseModel):
    assetId: str
    fillColor: Optional[str] = None
    saveToLibrary: bool = True
    tag: str = ""


class ExtractSubjectRequest(BaseModel):
    assetId: str
    tag: str = "posecraft-subject"
