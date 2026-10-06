"""Generate-with-reference pixel binding (identity vs edit canvas).

Binding law:
- referenceImage / referenceIds = identity (CRS). NEVER copy into sourceAssetId.
- sourceAssetId = real edit canvas only (strategy A / edit), never an identity id.
- Certified *.ref generate (qwen2512.ref) loads identity pixels from
  referenceImage or the first referenceIds asset when source is null.
- zimage.ref_edit is an edit canvas and must not steal CRS as source.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


def is_certified_ref_generate(workflow_key: str | None) -> bool:
    """True for certified generate-with-reference keys (*.ref), not ref_edit."""
    key = str(workflow_key or "").strip()
    if not key:
        return False
    # Edit canvas. Do not treat as generate-with-reference identity load.
    if key.endswith("ref_edit") or key.endswith(".edit") or ".edit" in key.split(".", 1)[-1]:
        return False
    return key.endswith(".ref") or key in {"qwen2512.atlas", "qwen2512.atlas_direct"}


def first_identity_asset_id(
    *,
    reference_ids: Sequence[Any] | None = None,
    reference_image: str | None = None,
) -> str | None:
    """Identity/reference asset id. Not an edit canvas."""
    img = str(reference_image or "").strip()
    if img:
        return img
    for raw in reference_ids or ():
        rid = str(raw or "").strip()
        if rid:
            return rid
    return None


def identity_refs_from_intent(
    intent: Any = None,
    params: Mapping[str, Any] | None = None,
) -> tuple[list[str], str | None]:
    """Collect referenceIds + referenceImage without reading or writing sourceAssetId."""
    params = params or {}
    ids: list[str] = []
    if intent is not None:
        for raw in getattr(intent, "referenceIds", None) or []:
            rid = str(raw or "").strip()
            if rid and rid not in ids:
                ids.append(rid)
    for raw in params.get("referenceIds") or params.get("reference_ids") or []:
        rid = str(raw or "").strip()
        if rid and rid not in ids:
            ids.append(rid)
    raw_img = params.get("referenceImage") or params.get("reference_image")
    ref_img = str(raw_img).strip() if raw_img else ""
    return ids, (ref_img or None)


@dataclass(frozen=True)
class ImagegenPixelChoice:
    """Worker pixel-load decision. source_asset_id is never rewritten to identity."""

    load_asset_id: str | None
    source_asset_id: str | None
    is_ref_generate: bool
    missing_required_pixels: bool


def choose_imagegen_pixel_asset(
    *,
    workflow_key: str | None,
    source_asset_id: str | None,
    reference_ids: Sequence[Any] | None = None,
    reference_image: str | None = None,
) -> ImagegenPixelChoice:
    """Decide which asset pixels a generate-with-reference worker should load.

    Returns source_asset_id unchanged. Identity ids are load_asset_id only.
    """
    src = str(source_asset_id or "").strip() or None
    is_ref = is_certified_ref_generate(workflow_key)
    identity = first_identity_asset_id(
        reference_ids=reference_ids,
        reference_image=reference_image,
    )
    if not is_ref:
        return ImagegenPixelChoice(
            load_asset_id=src,
            source_asset_id=src,
            is_ref_generate=False,
            missing_required_pixels=False,
        )
    load = src or identity
    return ImagegenPixelChoice(
        load_asset_id=load,
        source_asset_id=src,
        is_ref_generate=True,
        missing_required_pixels=load is None,
    )


def scene_asset_id_from_intent(
    intent: Any = None,
    params: Mapping[str, Any] | None = None,
) -> str | None:
    """Second plate for CIS multi-ref (environment / SCENE_REFERENCE)."""
    params = params or {}
    for key in ("sceneReferenceAssetId", "scene_reference_asset_id", "sceneAssetId"):
        raw = params.get(key)
        if raw and str(raw).strip():
            return str(raw).strip()
    meta = {}
    if intent is not None and isinstance(getattr(intent, "metadata", None), dict):
        meta = dict(intent.metadata or {})
    if isinstance(params.get("imageIntent"), dict):
        meta = {**meta, **dict((params.get("imageIntent") or {}).get("metadata") or {})}
    for key in ("sceneReferenceAssetId", "scene_reference_asset_id", "sceneAssetId"):
        raw = meta.get(key)
        if raw and str(raw).strip():
            return str(raw).strip()
    bind = meta.get("referenceBinding") if isinstance(meta.get("referenceBinding"), dict) else {}
    raw = bind.get("sceneAssetId")
    if raw and str(raw).strip():
        return str(raw).strip()
    creative = params.get("creativeContext") if isinstance(params.get("creativeContext"), dict) else {}
    raw = creative.get("sceneReferenceAssetId")
    if raw and str(raw).strip():
        return str(raw).strip()
    bind = creative.get("referenceBinding") if isinstance(creative.get("referenceBinding"), dict) else {}
    raw = bind.get("sceneAssetId")
    if raw and str(raw).strip():
        return str(raw).strip()
    # Typed authority rows
    rows = (
        meta.get("authorityReferences")
        or creative.get("authorityReferences")
        or params.get("authorityReferences")
        or []
    )
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        kind = str(row.get("kind") or row.get("role") or "").strip().lower()
        if kind in {"environment", "location", "scene"} or str(row.get("slot") or "") == "SCENE_REFERENCE":
            aid = str(row.get("assetId") or row.get("asset_id") or "").strip()
            if aid:
                return aid
    return None

