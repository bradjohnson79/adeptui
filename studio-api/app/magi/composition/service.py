"""Enqueue + run deterministic overlay compose jobs (canonical registration path)."""

from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ...db import Asset, Job
from ...image_product.history import append_history
from ..overlays.store import get_composition
from ..overlays.validate import validate_composition
from .render import render_composition_to_png


def _source_path(db: Session, project_id: str, asset_id: str | None) -> Path | None:
    if not asset_id:
        return None
    asset = db.query(Asset).filter(Asset.id == asset_id, Asset.project_id == project_id).first()
    if not asset or not asset.path:
        return None
    p = Path(asset.path)
    return p if p.is_file() else None


def run_overlay_compose_job(db: Session, job: Job) -> dict[str, Any]:
    params = json.loads(job.params_json or "{}")
    project_id = job.project_id
    composition_id = params.get("compositionId")
    composition = params.get("composition") or get_composition(project_id, composition_id)
    if not composition:
        job.status = "failed"
        job.message = "Composition not found"
        db.commit()
        return {"ok": False, "error": "composition_missing"}

    v = validate_composition(composition, project_id=project_id)
    if not v.get("ok"):
        job.status = "failed"
        job.message = "; ".join(v.get("errors") or ["validation failed"])
        db.commit()
        return {"ok": False, "error": "validation", "errors": v.get("errors")}

    source_id = composition.get("sourceAssetId") or params.get("sourceAssetId")
    src = _source_path(db, project_id, source_id)
    if source_id and src is None:
        job.status = "failed"
        job.message = "Source asset missing or inaccessible"
        db.commit()
        return {"ok": False, "error": "source_missing"}

    job.status = "running"
    job.stage = "Compositing"
    job.progress = 0.2
    db.commit()

    with tempfile.TemporaryDirectory(prefix="magi_overlay_") as td:
        out = Path(td) / "overlay_compose.png"
        try:
            meta = render_composition_to_png(
                source_image_path=src,
                composition=composition,
                out_path=out,
            )
        except Exception as exc:
            job.status = "failed"
            job.message = f"Overlay render failed: {exc}"
            job.progress = 1.0
            db.commit()
            append_history(
                project_id,
                {
                    "kind": "overlay_render_failed",
                    "jobId": job.id,
                    "compositionId": composition.get("compositionId"),
                    "error": str(exc),
                },
            )
            return {"ok": False, "error": "render_failed", "message": str(exc)}

        from ...generation_tools.lineage import register_derived_asset

        provenance = {
            "ops": [
                "overlay_composition_rendered",
                "text_overlay_applied",
                "lower_third_applied",
                "vector_graphic_applied",
                "derived_from_source_asset",
            ],
            "compositionId": composition.get("compositionId"),
            "schemaVersion": composition.get("schemaVersion"),
            "overlayElementIds": meta.get("overlayIds"),
            "fontsUsed": meta.get("fontsUsed"),
            "sourceAssetId": source_id,
            "staticRender": True,
            "animationCertified": False,
            "magiRenderer": "deterministic_pillow_v1",
            "nonDestructive": True,
            "sourcePreserved": True,
        }
        asset = register_derived_asset(
            db,
            project_id=project_id,
            source_path=out,
            kind="image",
            tag="magi_overlay",
            parent_asset_id=source_id,
            op="magi_overlay_compose",
            model="magi.composition",
            prompt_meta=provenance,
        )
        try:
            from ...image_product import versions as version_store

            if source_id:
                version_store.create_version(
                    project_id,
                    source_asset_id=source_id,
                    output_asset_id=asset.id,
                    name=f"Overlay {str(composition.get('compositionId', ''))[:8]}",
                    state="PendingReview",
                )
        except Exception:
            pass

        job.status = "done"
        job.stage = "Completed"
        job.progress = 1.0
        job.message = f"Overlay composed → {asset.id}"
        job.result_json = json.dumps({"assetId": asset.id, "provenance": provenance})
        db.commit()
        append_history(
            project_id,
            {
                "kind": "overlay_rendered",
                "jobId": job.id,
                "assetId": asset.id,
                "compositionId": composition.get("compositionId"),
                "sourceAssetId": source_id,
                "event": "Output registered",
            },
        )
        return {
            "ok": True,
            "assetId": asset.id,
            "jobId": job.id,
            "sourcePreserved": True,
            "provenance": provenance,
        }


def enqueue_overlay_compose(
    db: Session,
    project_id: str,
    *,
    composition_id: str | None = None,
    composition: dict[str, Any] | None = None,
) -> dict[str, Any]:
    comp = composition
    if composition_id and not comp:
        comp = get_composition(project_id, composition_id)
    if not comp:
        return {"ok": False, "queued": False, "error": "composition_required"}
    v = validate_composition(comp, project_id=project_id)
    if not v.get("ok"):
        return {"ok": False, "queued": False, "errors": v.get("errors")}

    # Font substitution warning (non-blocking)
    from ..overlays.fonts import resolve_font

    warnings: list[str] = []
    for el in comp.get("overlays") or []:
        if el.get("type") != "text":
            continue
        style = el.get("textStyle") or {}
        fid = style.get("fontFamily") or style.get("fontId")
        r = resolve_font(str(fid) if fid else None)
        if r.get("substituted") and fid:
            warnings.append(f"Font '{fid}' missing — will use {(r.get('font') or {}).get('id')}")

    job = Job(
        id=str(uuid.uuid4()),
        project_id=project_id,
        kind="magi_overlay_compose",
        status="queued",
        progress=0.0,
        stage="Queued",
        message="MAGI overlay compose (deterministic)",
        params_json=json.dumps(
            {
                "compositionId": comp.get("compositionId"),
                "composition": comp,
                "sourceAssetId": comp.get("sourceAssetId"),
                "magiRenderer": "deterministic_pillow_v1",
            }
        ),
    )
    db.add(job)
    db.commit()
    append_history(
        project_id,
        {
            "kind": "overlay_enqueued",
            "jobId": job.id,
            "compositionId": comp.get("compositionId"),
            "event": "Job enqueued",
        },
    )
    result = run_overlay_compose_job(db, job)
    return {
        "ok": bool(result.get("ok")),
        "queued": True,
        "jobId": job.id,
        "warnings": warnings,
        **result,
    }
