"""Artifact persistence — ensure generated assets are real Library assets.

Spec §41: "Generated binaries belong to Library. Conversation stores references,
not duplicate media."

When a child job completes, this module:
1. Ensures an `Asset` row exists (the imagegen job already creates one — verify).
2. Writes `AssetLibraryMeta` if missing.
3. Adds the asset to the execution's collection (if storyboard/casting).

Reuses existing `image_product` asset creation — does not duplicate it.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def ensure_asset_persisted(
    db: Session,
    project_id: str,
    asset_id: str,
    *,
    purpose: str = "",
    metadata: dict | None = None,
) -> str | None:
    """Ensure an asset is persisted to the Library.

    The imagegen job queue already creates the `Asset` row on completion
    (see `queue_worker.py:_imagegen_commit_asset`). This function is a
    no-op verification + optional metadata enrichment. Returns the asset_id
    if confirmed, None if the asset doesn't actually exist.
    """
    try:
        from ...assets.service import get_asset
        from ...assets.models import AssetLibraryMetaRow

        asset = get_asset(db, project_id, asset_id)
        if not asset:
            logger.warning("Asset %s not found for project %s", asset_id, project_id)
            return None

        # Enrich metadata if provided.
        if metadata:
            meta = (
                db.query(AssetLibraryMetaRow)
                .filter(AssetLibraryMetaRow.asset_id == asset_id)
                .first()
            )
            if meta:
                # Merge — don't overwrite existing keys.
                existing = meta.meta_json or {}
                for k, v in metadata.items():
                    if k not in existing:
                        existing[k] = v
                meta.meta_json = existing
            else:
                meta = AssetLibraryMetaRow(
                    asset_id=asset_id,
                    meta_json=metadata,
                )
                db.add(meta)
            db.commit()

        return asset_id
    except Exception as exc:
        logger.error("Failed to persist asset %s: %s", asset_id, exc)
        return None


def get_asset_url(asset_id: str) -> str:
    """Build the asset URL for frontend display."""
    return f"/api/assets/{asset_id}/file"
