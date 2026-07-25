"""Side-by-side reference vs generated metadata bundles (no required pixel diff)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from ...db import Asset
from .schemas import ValidationComparison


def _asset_meta(db: Session, asset_id: Optional[str]) -> dict[str, Any]:
    if not asset_id:
        return {}
    asset = db.get(Asset, asset_id)
    if not asset:
        return {"assetId": asset_id, "missing": True}
    return {
        "assetId": asset.id,
        "tag": asset.tag,
        "kind": asset.kind,
        "filename": asset.filename,
        "path": asset.path,
        "validationLifecycle": getattr(asset, "validation_lifecycle", "not_requested"),
        "validationResult": getattr(asset, "validation_result", "unreviewed"),
        "productionApproval": getattr(asset, "production_approval", "none"),
    }


def build_comparison(
    db: Session,
    *,
    session_id: str,
    project_id: str,
    reference_asset_id: Optional[str],
    generated_asset_id: Optional[str],
    context: dict[str, Any] | None = None,
) -> ValidationComparison:
    ref_meta = _asset_meta(db, reference_asset_id)
    gen_meta = _asset_meta(db, generated_asset_id)
    differences: list[dict[str, Any]] = []

    if ref_meta.get("kind") and gen_meta.get("kind") and ref_meta.get("kind") != gen_meta.get("kind"):
        differences.append(
            {
                "field": "kind",
                "reference": ref_meta.get("kind"),
                "generated": gen_meta.get("kind"),
            }
        )

    tech = (context or {}).get("technicalMetrics") or {}
    if tech:
        differences.append(
            {
                "field": "technicalMetrics",
                "generated": {
                    "width": tech.get("width"),
                    "height": tech.get("height"),
                    "meanLuma": tech.get("meanLuma"),
                },
            }
        )

    if not reference_asset_id:
        differences.append({"field": "referenceAssetId", "message": "No reference asset supplied."})

    return ValidationComparison(
        comparisonId=str(uuid.uuid4()),
        sessionId=session_id,
        projectId=project_id,
        referenceAssetId=reference_asset_id,
        generatedAssetId=generated_asset_id,
        referenceMeta=ref_meta,
        generatedMeta=gen_meta,
        differences=differences,
        createdAt=datetime.utcnow().isoformat() + "Z",
    )
