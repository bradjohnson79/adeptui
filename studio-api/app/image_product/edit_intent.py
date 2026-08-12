"""ImageEditIntent — product-level editing contract (M42 W4)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class ImageEditIntent:
    intentId: str = field(default_factory=lambda: str(uuid4()))
    projectId: str = ""
    sourceAssetIds: list[str] = field(default_factory=list)
    operation: str = "image.inpaint"
    prompt: str | None = None
    negativePrompt: str | None = None
    masks: list[dict[str, Any]] = field(default_factory=list)
    referenceAssetIds: list[str] = field(default_factory=list)
    controls: dict[str, Any] = field(default_factory=dict)
    preferences: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] = field(default_factory=dict)
    continuity: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    layers: list[dict[str, Any]] = field(default_factory=list)
    recipeId: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if not d.get("metadata", {}).get("createdAt"):
            d.setdefault("metadata", {})["createdAt"] = _now()
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImageEditIntent:
        data = dict(data or {})
        return cls(
            intentId=str(data.get("intentId") or uuid4()),
            projectId=str(data.get("projectId") or ""),
            sourceAssetIds=list(data.get("sourceAssetIds") or []),
            operation=str(data.get("operation") or "image.inpaint"),
            prompt=data.get("prompt"),
            negativePrompt=data.get("negativePrompt"),
            masks=list(data.get("masks") or []),
            referenceAssetIds=list(data.get("referenceAssetIds") or []),
            controls=dict(data.get("controls") or {}),
            preferences=dict(data.get("preferences") or {}),
            output=dict(data.get("output") or {}),
            continuity=dict(data.get("continuity") or {}),
            metadata=dict(data.get("metadata") or {}),
            layers=list(data.get("layers") or []),
            recipeId=data.get("recipeId"),
        )


def default_edit_layers() -> list[dict[str, Any]]:
    """Default layer stack: background · foreground · masks · references."""
    return [
        {
            "layerId": f"layer-bg-{uuid4().hex[:8]}",
            "name": "Background",
            "visible": True,
            "locked": False,
            "opacity": 1.0,
            "blendMode": "normal",
            "derivedAssetIds": [],
            "kind": "background",
        },
        {
            "layerId": f"layer-fg-{uuid4().hex[:8]}",
            "name": "Foreground",
            "visible": True,
            "locked": False,
            "opacity": 1.0,
            "blendMode": "normal",
            "derivedAssetIds": [],
            "kind": "foreground",
        },
        {
            "layerId": f"layer-mask-{uuid4().hex[:8]}",
            "name": "Masks",
            "visible": True,
            "locked": False,
            "opacity": 0.5,
            "blendMode": "normal",
            "derivedAssetIds": [],
            "kind": "mask",
        },
        {
            "layerId": f"layer-ref-{uuid4().hex[:8]}",
            "name": "References",
            "visible": True,
            "locked": False,
            "opacity": 1.0,
            "blendMode": "normal",
            "derivedAssetIds": [],
            "kind": "reference",
        },
    ]


def validate_basic(intent: ImageEditIntent | dict[str, Any]) -> list[str]:
    """Return list of validation errors; empty means OK."""
    if isinstance(intent, dict):
        intent = ImageEditIntent.from_dict(intent)
    errors: list[str] = []
    if not intent.projectId:
        errors.append("projectId required")
    if not intent.operation:
        errors.append("operation required")
    if not intent.sourceAssetIds:
        errors.append("sourceAssetIds required — at least one source asset")
    from .edit_ops import EDIT_OPERATIONS

    spec = EDIT_OPERATIONS.get(intent.operation)
    if spec is None:
        errors.append(f"unknown operation: {intent.operation}")
    elif spec.get("requiredMasks") and not intent.masks:
        errors.append(f"operation {intent.operation} requires at least one mask")
    return errors
