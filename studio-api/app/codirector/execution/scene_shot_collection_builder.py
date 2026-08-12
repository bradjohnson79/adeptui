"""Scene Shots collection builder — group Scene Creator outputs into a Library collection.

Mirrors ``collection_builder.create_storyboard_collection`` but for Scene Creator
shot batches. A Scene Shots collection is a lightweight ordered Library grouping
(spec §39) whose ``metadata.collection_type == "scene_shots"`` and which carries
references to the originating ``SceneGenerationBatch`` and ``EnvironmentReferencePackage``.

Reuses existing ``image_product/collections.py`` — does not create a parallel
collection system (Build Law #5, #17).

Amendment #3 (SPATIAL AUTHORITY): the collection only references generated asset
IDs; it never writes back to spatial map placement state.

Amendment #49 (scene shots collection): scene shot assets are grouped into a
lightweight Library collection of type ``scene_shots`` storing ordered asset
references.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def create_scene_shots_collection(
    project_id: str,
    *,
    asset_ids: list[str],
    batch_id: str,
    ers_package_id: str = "",
    shot_requests: Optional[list[Any]] = None,
    name: str = "Scene Shots",
    metadata: Optional[dict[str, Any]] = None,
) -> str:
    """Create an ordered Scene Shots Library collection.

    Args:
        project_id: Owning project (project isolation — Build Law #14).
        asset_ids: Ordered result asset IDs from the Scene Creator batch.
        batch_id: The originating ``SceneGenerationBatch.id``.
        ers_package_id: The ERS package used for the batch (provenance).
        shot_requests: Optional ``ShotRequest`` list (or dicts) for rich
            provenance metadata (shot order, prompts, character/prop IDs).
        name: Collection display name.
        metadata: Extra metadata merged into the collection.

    Returns:
        The created ``collectionId``.
    """
    from ...image_product.collections import create_collection

    ordered = [aid for aid in asset_ids if aid]
    col = create_collection(project_id, name=name, asset_ids=ordered)

    shot_provenance: list[dict[str, Any]] = []
    if shot_requests:
        for shot in shot_requests:
            # ShotRequest is a pydantic model; dicts also supported.
            dump = getattr(shot, "model_dump", None)
            if callable(dump):
                shot_provenance.append(dump())
            elif isinstance(shot, dict):
                shot_provenance.append(shot)

    meta = {
        "collection_type": "scene_shots",
        "batch_id": batch_id,
        "ers_package_id": ers_package_id,
        "shot_count": len(ordered),
        "shots": shot_provenance,
        **(metadata or {}),
    }
    _enrich_collection(project_id, col["collectionId"], meta)
    return col["collectionId"]


def add_scene_shots_to_collection(
    project_id: str,
    collection_id: str,
    asset_ids: list[str],
    *,
    batch_id: str = "",
) -> Optional[dict[str, Any]]:
    """Append additional scene shot assets to an existing scene shots collection.

    Used for targeted regeneration: the regenerated asset replaces/augments the
    collection entry for its shot index. Preserves the ``scene_shots`` collection
    type metadata.
    """
    from ...image_product.collections import get_collection, update_collection

    col = get_collection(project_id, collection_id)
    if not col:
        logger.warning("Scene shots collection %s not found", collection_id)
        return None

    existing = col.get("metadata") or {}
    if existing.get("collection_type") != "scene_shots":
        logger.warning(
            "Collection %s is not a scene_shots collection (type=%s)",
            collection_id,
            existing.get("collection_type"),
        )
        # Still proceed — do not block, but record the mismatch.
        existing.setdefault("collection_type", "scene_shots")

    if batch_id and not existing.get("batch_id"):
        existing["batch_id"] = batch_id

    current_ids = list(col.get("assetIds") or [])
    for aid in asset_ids:
        if aid and aid not in current_ids:
            current_ids.append(aid)
    existing["shot_count"] = len(current_ids)
    update_collection(project_id, collection_id, {"assetIds": current_ids, "metadata": existing})
    return get_collection(project_id, collection_id)


def _enrich_collection(project_id: str, collection_id: str, metadata: dict[str, Any]) -> None:
    """Merge metadata into an existing collection."""
    from ...image_product.collections import get_collection, update_collection

    col = get_collection(project_id, collection_id)
    if not col:
        return
    existing_meta = col.get("metadata") or {}
    existing_meta.update(metadata)
    update_collection(project_id, collection_id, {"metadata": existing_meta})
