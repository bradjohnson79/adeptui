"""Capability handler: ers.generate

Generates the four scene-relative directional views (N/E/S/W) for an
Environment Reference Sheet from a Spatial Map, then queues a programmatic
composite (amendment #2 — the ERS sheet is composed in code, NOT generated
by an image model).

Amendment #1 (ATLAS ORDER): ERS sits AFTER Spatial Map and BEFORE Scene
Creator. Workflow: Character Creator → Atlas Shot / Master Environment →
Spatial Map → ERS → Scene Creator → Timeline.

Amendment #2 (ERS COMPOSITION): AI generates the Master/N/E/S/W views.
Adept UI programmatically composites the final ERS sheet from those
actual assets + structured data via
``environment_reference_sheet.exports.render_png`` (REUSED — not duplicated).

Amendment #3 (SPATIAL AUTHORITY): the handler SNAPSHOT-COPIES placements
from the spatial map into the ERS package at generation time. It NEVER
writes back to the spatial map.

Amendment #4 (ORIENTATION): northLockDirection = "north" means the top edge
of the Atlas Shot. N/E/S/W are scene-relative.

Law #18: directional views go through the canonical image gen pipeline
(``enqueue_imagegen_job``) — no silent provider/model substitution.
Law #7: this handler submits REAL jobs (no mock completion).
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


_DIRECTIONS: tuple[str, ...] = ("north", "east", "south", "west")


def handle(
    db: Session,
    project_id: str,
    execution_id: str,
    *,
    spatial_map_id: str,
    scene_id: str = "",
    visual_style: str = "",
    name: str = "",
    description: str = "",
) -> dict[str, Any]:
    """Generate the four directional views for an ERS from a Spatial Map.

    Steps:
    1. ``create_sheet`` (if no ERS exists for this spatial map).
    2. ``attach_spatial_map`` — reads the Spatial Map, builds the reference
       bundle, prepares directional prompts.
    3. For each direction in (north, east, south, west): build the
       directional image plan, submit a real imagegen job (purpose
       ``ers-{direction}-view``).
    4. Snapshot-copy the spatial map placements into an
       ``EnvironmentReferencePackage`` and persist it (amendment #3).
    5. Return 4 directional child_jobs + 1 composite child_job (status
       ``queued``, ``stage=composite``, ``depends_on`` the 4 directionals).
       The composite is assembled programmatically once the directionals
       complete, via a separate REST call (V1 — see ers_contracts.py).

    Returns a dict with ``job_ids``, ``child_jobs``, ``surface_type``,
    ``ers_package_id``, and ``sheet_id``.
    """
    from ....storyboard_jobs import enqueue_imagegen_job
    from ....environment_reference_sheet.orchestrator import (
        attach_spatial_map,
        build_directional_view_image_plan,
        compose_sheet_metadata,
        create_sheet,
    )
    from ....environment_reference_sheet.store import list_sheets, save_sheet
    from ....spatial_map.ers_contracts import EnvironmentReferencePackage
    from ....spatial_map.ers_persistence import save_ers_package
    from ....spatial_map.ers_projection import project_document_placements
    from ....spatial_map.service import get_document

    # 1. Find or create the ERS for this spatial map.
    existing_sheets = list_sheets(project_id)
    sheet = next(
        (
            s
            for s in existing_sheets
            if s.spatialMap and s.spatialMap.mapId == spatial_map_id
        ),
        None,
    )
    if sheet is None:
        sheet_name = (name or "").strip() or "Environment Reference Sheet"
        sheet_description = (
            (description or "").strip()
            or "Programmatically composed environment reference sheet."
        )
        sheet = create_sheet(
            project_id=project_id,
            name=sheet_name,
            description=sheet_description,
            scene_id=scene_id or None,
        )

    # 2. Attach the spatial map (reads placements, builds prompts).
    #    Per amendment #3, this is a read-only snapshot — never writes back.
    sheet = attach_spatial_map(db, sheet, spatial_map_id=spatial_map_id)
    sheet = compose_sheet_metadata(sheet)

    # 3. Submit one real imagegen job per direction.
    child_jobs: list[dict[str, Any]] = []
    job_ids: list[str] = []
    directional_job_ids: list[str] = []

    for direction in _DIRECTIONS:
        try:
            plan = build_directional_view_image_plan(
                sheet,
                direction=direction,  # type: ignore[arg-type]
                quality_profile="cinematic",
                deployment_preference="best-match",
            )
        except Exception as exc:
            logger.error("ERS directional plan failed for %s: %s", direction, exc)
            child_jobs.append(
                {
                    "job_id": f"failed_ers_{direction}",
                    "label": f"{direction.title()} View",
                    "status": "failed",
                    "child_index": len(child_jobs),
                    "metadata": {"direction": direction, "error": str(exc)},
                }
            )
            continue

        # The plan carries the prompt + spatial map payload. Build the
        # imagegen body with the canonical enqueue surface.
        body: dict[str, Any] = {
            "prompt": plan.request.prompt or sheet.description,
            "negative_prompt": "",
            "width": 1280,
            "height": 720,
            "tag": f"codirector_ers_{execution_id[:8]}_{direction}",
            "modelFamilyPreference": "zimage",
            "purpose": f"ers-{direction}-view",
            "aspectRatio": "16:9",
            "batchCount": 1,
            "creativeContext": {
                "objective": "ers_directional_view",
                "executionId": execution_id,
                "direction": direction,
                "environmentReferenceSheetId": sheet.sheetId,
                "spatialMapId": spatial_map_id,
                "northLockDirection": sheet.spatialMap.northLockDirection
                if sheet.spatialMap
                else "north",
                "visualStyle": visual_style or "",
                "orientationNote": (
                    "Scene-relative direction. North = top edge of the Atlas Shot."
                ),
                "workflowKey": "zimage.txt2img",
            },
        }
        # Carry the spatial map payload + reference asset if the plan provides one.
        spatial_payload = getattr(plan, "spatial_map_payload", None) or {}
        if spatial_payload:
            body["creativeContext"]["spatialMapPayload"] = spatial_payload
        reference_asset = getattr(plan, "reference_image", None) or getattr(plan, "referenceImage", None)
        if reference_asset:
            body["referenceImage"] = reference_asset
            body["reference_image"] = reference_asset

        try:
            job = enqueue_imagegen_job(db, project_id, body, scene_id=scene_id or None)
            job_id = job.id
            status = "queued"
        except Exception as exc:
            logger.error("ERS directional enqueue failed for %s: %s", direction, exc)
            job_id = f"failed_ers_{direction}"
            status = "failed"

        job_ids.append(job_id)
        directional_job_ids.append(job_id)
        child_jobs.append(
            {
                "job_id": job_id,
                "label": f"{direction.title()} View",
                "status": status,
                "child_index": len(child_jobs),
                "metadata": {
                    "direction": direction,
                    "purpose": f"ers-{direction}-view",
                },
            }
        )

    # 4. Snapshot the spatial map placements into an ERS package (amendment #3).
    spatial_document = get_document(db, project_id, spatial_map_id)
    package = EnvironmentReferencePackage(
        project_id=project_id,
        scene_layout_id=spatial_map_id,
        atlas_asset_id=spatial_document.backgroundAssetId,
        placements=project_document_placements(spatial_document),
        style_context={"visual_style": visual_style or ""},
        orientation="atlas-north-up",
        directional_assets={d: None for d in _DIRECTIONS},
        metadata={
            "execution_id": execution_id,
            "sheet_id": sheet.sheetId,
            "directional_job_ids": directional_job_ids,
        },
    )
    save_ers_package(db, project_id, package)

    # 5. Composite child job — assembled programmatically (amendment #2).
    #    V1: the runner triggers this via a separate REST call once the four
    #    directional jobs complete. The child_job is queued with a dependency
    #    hint so consumers know to wait.
    composite_job_id = f"ers_composite_{package.id}"
    child_jobs.append(
        {
            "job_id": composite_job_id,
            "label": "ERS Composite",
            "status": "queued",
            "child_index": len(child_jobs),
            "metadata": {
                "stage": "composite",
                "depends_on": directional_job_ids,
                "ers_package_id": package.id,
                "sheet_id": sheet.sheetId,
                "note": (
                    "Programmatically assembled via "
                    "environment_reference_sheet.exports.render_png once "
                    "directional views complete (amendment #2)."
                ),
            },
        }
    )
    job_ids.append(composite_job_id)

    # Persist the sheet so downstream reads (api.py) see the directional prompts.
    save_sheet(sheet)

    return {
        "job_ids": job_ids,
        "child_jobs": child_jobs,
        "surface_type": "ers_generation",
        "ers_package_id": package.id,
        "sheet_id": sheet.sheetId,
        "spatial_map_id": spatial_map_id,
        "purpose": "ers_generation",
    }
