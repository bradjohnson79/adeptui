"""Capability handler: atlas.assign — use an existing Atlas without generating."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session


def handle(
    db: Session,
    project_id: str,
    execution_id: str,
    *,
    prompt: str = "",
    attachment_asset_ids: list[str] | None = None,
    scene_description: str = "",
    scene_context: str | None = None,
    **_: Any,
) -> dict[str, Any]:
    from ...routing.atlas_classify import classify_atlas_asset
    from ...routing.atlas_source import resolve_atlas_source_asset, source_was_requested
    from ....spatial_map.service import assign_existing_atlas

    source = ((attachment_asset_ids or [None])[0]) or resolve_atlas_source_asset(
        db, project_id, prompt, attachment_asset_ids
    )
    if not source:
        hint = (
            " A location image was mentioned but could not be resolved in this project."
            if source_was_requested(prompt, attachment_asset_ids)
            else ""
        )
        return {
            "error": f"No Atlas image was found.{hint}",
            "child_jobs": [],
            "surface_type": "atlas_assign",
        }
    classification = classify_atlas_asset(db, project_id, source, intended_route="assign")
    if not classification.pixels_read:
        return {
            "error": classification.message,
            "child_jobs": [],
            "surface_type": "atlas_assign",
        }
    # Explicit assign is authoritative. Validation may warn; it must never
    # enqueue GPT Image 2, Flux, Qwen, or any other generator.
    document = assign_existing_atlas(
        db,
        project_id,
        source,
        original_environment_reference_asset_id=source,
        scene_description=scene_description or scene_context or prompt or None,
    )
    warning = "" if classification.action == "assign" else classification.message
    if warning and warning not in document.warnings:
        document.warnings = list(document.warnings) + [warning]
    return {
        "status": "completed",
        "result_asset_ids": [source],
        "job_ids": [execution_id],
        "child_jobs": [
            {
                "job_id": execution_id,
                "label": "Spatial Map",
                "status": "completed",
                "child_index": 0,
                "asset_id": source,
                "metadata": {
                    "purpose": "atlas_shot",
                    "assigned_existing": True,
                    "pixels_unchanged": True,
                    "auto_routed_from_assign": False,
                    "spatial_map_id": document.id,
                    "geometry_source": "supplied",
                    "pixels_read": classification.pixels_read,
                    "validation_kind": classification.kind,
                    "validation_warning": warning,
                },
            }
        ],
        "surface_type": "atlas_assign",
        "spatial_map_id": document.id,
        "creatorAck": warning or "Using the uploaded Spatial Map. No image was generated.",
    }
