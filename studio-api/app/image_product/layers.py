"""EditLayer stack helpers (M42 W4)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4

from .edit_intent import default_edit_layers


def default_stack() -> list[dict[str, Any]]:
    return default_edit_layers()


def create_layer(
    *,
    name: str = "Layer",
    kind: str = "custom",
    visible: bool = True,
    locked: bool = False,
    opacity: float = 1.0,
    blend_mode: str = "normal",
    derived_asset_ids: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "layerId": f"layer-{uuid4().hex[:10]}",
        "name": name,
        "visible": visible,
        "locked": locked,
        "opacity": opacity,
        "blendMode": blend_mode,
        "derivedAssetIds": list(derived_asset_ids or []),
        "kind": kind,
    }


def update_layer(layer: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = dict(layer)
    for k, v in patch.items():
        if k == "layerId":
            continue
        if k == "derivedAssetIds" and v is not None:
            out["derivedAssetIds"] = list(v)
        elif v is not None:
            out[k] = v
    return out


def list_layers_for_intent(intent: dict[str, Any]) -> list[dict[str, Any]]:
    layers = intent.get("layers")
    if layers:
        return deepcopy(list(layers))
    return default_stack()


def ensure_layers_on_intent(intent: dict[str, Any]) -> dict[str, Any]:
    """Ensure intent dict has a layer stack."""
    out = dict(intent)
    if not out.get("layers"):
        out["layers"] = default_stack()
    return out
