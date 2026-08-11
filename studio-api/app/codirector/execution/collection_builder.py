"""Collection builder — create ordered Library collections for execution results.

Spec §38: "Storyboard results become Library assets. Collection: lightweight
ordered grouping."
Spec §39: "If Library lacks collections, introduce/reuse a lightweight generic
collection structure."

Reuses existing `image_product/collections.py` — does not create a parallel
collection system.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def create_storyboard_collection(
    project_id: str,
    title: str,
    ordered_asset_ids: list[str],
    *,
    scene_label: str = "",
    metadata: dict | None = None,
) -> str:
    """Create an ordered storyboard collection.

    Returns the collection_id. The collection's `assetIds` list is ordered
    by frame index (spec §38).
    """
    from ...image_product.collections import create_collection

    col = create_collection(
        project_id,
        name=title,
        asset_ids=ordered_asset_ids,
    )

    # Enrich with storyboard metadata.
    meta = {
        "collection_type": "storyboard",
        "scene_label": scene_label,
        "frame_count": len(ordered_asset_ids),
        **(metadata or {}),
    }
    _enrich_collection(project_id, col["collectionId"], meta)

    return col["collectionId"]


def add_to_collection(
    project_id: str,
    collection_id: str,
    asset_id: str,
    *,
    index: Optional[int] = None,
) -> None:
    """Add an asset to an existing collection at a specific index."""
    from ...image_product.collections import get_collection, update_collection

    col = get_collection(project_id, collection_id)
    if not col:
        logger.warning("Collection %s not found", collection_id)
        return

    asset_ids = list(col.get("assetIds") or [])
    if index is not None and 0 <= index < len(asset_ids):
        # Replace at index (for regeneration).
        asset_ids[index] = asset_id
    else:
        asset_ids.append(asset_id)

    update_collection(project_id, collection_id, {"assetIds": asset_ids})


def _enrich_collection(project_id: str, collection_id: str, metadata: dict) -> None:
    """Merge metadata into an existing collection."""
    from ...image_product.collections import get_collection, update_collection

    col = get_collection(project_id, collection_id)
    if not col:
        return
    existing_meta = col.get("metadata") or {}
    existing_meta.update(metadata)
    update_collection(project_id, collection_id, {"metadata": existing_meta})
