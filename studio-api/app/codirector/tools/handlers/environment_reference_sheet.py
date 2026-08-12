"""Closed-registry handlers for Co-Director Environment Reference Sheets."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ....codirector.bible.domain.schemas import LocationData
from ....codirector.bible.domain_service import BibleDomainService
from ....generation_tools.lineage import register_derived_asset
from ....image_pipeline.orchestrator import generate_candidates_for_plan
from ....image_pipeline.store import load_candidate_group, save_candidate_group, save_plan
from ....project_library.codirector import storage_preflight
from ....project_library.service import resolve_path
from ....spatial_map.service import list_documents
from ....db import Asset
from ....environment_reference_sheet import orchestrator, store
from ....environment_reference_sheet.continuity import validate_sheet
from ....environment_reference_sheet.contracts import ERSExportRecord, ERSProvenanceRecord
from ....environment_reference_sheet.exports import (
    build_offline_package,
    render_pdf,
    render_png,
    update_export_record,
)
from ..definitions import ToolContext, ToolPreview


def _project_id(ctx: ToolContext) -> str:
    return str(ctx.project_id or "").strip()


def _text(args: dict[str, Any], key: str) -> str:
    value = args.get(key)
    return str(value).strip() if value is not None else ""


def _require(args: dict[str, Any], key: str) -> str:
    value = _text(args, key)
    if not value:
        raise ValueError(f"{key} is required")
    return value


def _load_sheet(ctx: ToolContext, sheet_id: str):
    sheet = store.load_sheet(_project_id(ctx), sheet_id)
    if sheet is None:
        raise ValueError("ERS sheet not found")
    return sheet


def _view(sheet, direction: str):
    for item in sheet.directionalViews:
        if item.direction == direction:
            return item
    return None


async def list_sheets(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    sheets = store.list_sheets(_project_id(ctx))
    return {
        "projectId": _project_id(ctx),
        "sheets": [
            {
                "sheetId": sheet.sheetId,
                "name": sheet.name,
                "status": sheet.status,
                "continuityStatus": sheet.continuity.status,
                "approvedDirections": [view.direction for view in sheet.directionalViews if view.approvedAssetId],
                "updatedAt": sheet.updatedAt,
            }
            for sheet in sheets
        ],
        "_evidence": {"source": "environment_reference_sheet.store"},
    }


async def get_sheet(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    sheet = _load_sheet(ctx, _require(args, "sheetId"))
    return {
        "projectId": sheet.projectId,
        "sheet": sheet.model_dump(mode="json"),
        "_evidence": {"source": "environment_reference_sheet.store"},
    }


def preview_create_sheet(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    name = _require(args, "name")
    description = _require(args, "description")
    return ToolPreview(
        summary=f"Create ERS draft '{name}'.",
        lines=[
            f"Environment: {name}",
            f"Scene: {_text(args, 'sceneId') or 'none bound yet'}",
            "Creates the canonical ERS draft only. It does not generate views until a later approved action.",
            f"Description: {description[:140]}",
        ],
        resourceKind="project",
        resourceId=_project_id(ctx),
    )


def apply_create_sheet(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    sheet = orchestrator.create_sheet(
        project_id=_project_id(ctx),
        name=_require(args, "name"),
        description=_require(args, "description"),
        scene_id=_text(args, "sceneId") or None,
        creator_notes=_text(args, "creatorNotes") or None,
    )
    store.save_sheet(sheet)
    return {
        "ok": True,
        "sheetId": sheet.sheetId,
        "sheet": sheet.model_dump(mode="json"),
        "_summary": sheet.creationPlan.creatorPreview,
        "_evidence": {"source": "environment_reference_sheet.orchestrator.create_sheet + store.save_sheet"},
    }


def preview_attach_spatial_map(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    project_id = _project_id(ctx)
    maps = list_documents(ctx.db, project_id)
    return ToolPreview(
        summary="Attach a Spatial Map to this ERS.",
        lines=[
            f"Sheet: {_require(args, 'sheetId')}",
            f"Spatial Map: {_require(args, 'spatialMapId')}",
            f"Project maps available: {len(maps)}",
            "Locks north before view planning and reuses the real Spatial Map prompts.",
        ],
        resourceKind="project",
        resourceId=project_id,
    )


def apply_attach_spatial_map(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    sheet = _load_sheet(ctx, _require(args, "sheetId"))
    sheet = orchestrator.attach_spatial_map(ctx.db, sheet, spatial_map_id=_require(args, "spatialMapId"))
    store.save_sheet(sheet)
    return {
        "ok": True,
        "sheetId": sheet.sheetId,
        "sheet": sheet.model_dump(mode="json"),
        "_summary": "Spatial Map attached and north lock prepared.",
        "_evidence": {"source": "spatial_map.service + environment_reference_sheet.orchestrator.attach_spatial_map"},
    }


def preview_generate_directional_views(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    sheet = _load_sheet(ctx, _require(args, "sheetId"))
    warnings = []
    if sheet.spatialMap is None:
        warnings.append("A Spatial Map must be attached first.")
    return ToolPreview(
        summary="Generate north/east/south/west ERS view plans.",
        lines=[
            f"Sheet: {sheet.sheetId}",
            "Directions: North, East, South, West",
            "Uses Image Pipeline plan + candidate groups for each direction.",
            "No direction is silently approved.",
        ],
        resourceKind="project",
        resourceId=_project_id(ctx),
        warnings=warnings,
    )


def apply_generate_directional_views(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    sheet = _load_sheet(ctx, _require(args, "sheetId"))
    if sheet.spatialMap is None:
        raise ValueError("Spatial Map is required before directional view generation.")
    quality = _text(args, "qualityProfile") or "cinematic"
    deployment = _text(args, "deploymentPreference") or "best-match"
    queued: list[dict[str, Any]] = []
    for direction in ("north", "east", "south", "west"):
        view = _view(sheet, direction)
        if view is None:
            continue
        plan = orchestrator.build_directional_view_image_plan(
            sheet,
            direction=direction,  # type: ignore[arg-type]
            quality_profile=quality,
            deployment_preference=deployment,
        )
        save_plan(plan)
        group = generate_candidates_for_plan(plan, requested_count=2, db=ctx.db)
        save_candidate_group(group)
        view.imagePipelinePlanId = plan.planId
        view.candidateGroupId = group.groupId
        view.status = "queued" if group.status == "queued" else "planned"
        view.warnings = list(dict.fromkeys(view.warnings + [group.explanation] if getattr(group, "explanation", None) else view.warnings))
        queued.append({"direction": direction, "planId": plan.planId, "groupId": group.groupId, "groupStatus": group.status})
    sheet.status = "continuity_review"
    sheet.updatedAt = store.load_sheet(sheet.projectId, sheet.sheetId).updatedAt if store.load_sheet(sheet.projectId, sheet.sheetId) else sheet.updatedAt
    sheet.continuity = validate_sheet(sheet)
    for stage in sheet.creationPlan.stages:
        if stage.stageKey == "directional_views":
            stage.status = "complete"
            stage.summary = "Directional Image Pipeline plans were prepared for North, East, South, and West."
        if stage.stageKey == "continuity":
            stage.status = "ready"
            stage.summary = "Ready for continuity review after candidate approval."
    store.save_sheet(sheet)
    return {
        "ok": True,
        "sheetId": sheet.sheetId,
        "queuedViews": queued,
        "sheet": sheet.model_dump(mode="json"),
        "_summary": "Directional view plans were created through Image Pipeline for all four primary directions.",
        "_evidence": {"source": "environment_reference_sheet + image_pipeline.orchestrator.generate_candidates_for_plan"},
    }


def preview_approve_direction(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    sheet = _load_sheet(ctx, _require(args, "sheetId"))
    direction = _require(args, "direction")
    view = _view(sheet, direction)
    lines = [
        f"Sheet: {sheet.sheetId}",
        f"Direction: {direction.title()}",
        f"Candidate group: {view.candidateGroupId if view else 'missing'}",
        "Records the approved keeper for this direction only.",
    ]
    return ToolPreview(summary=f"Approve the {direction} ERS direction.", lines=lines, resourceKind="project", resourceId=_project_id(ctx))


def apply_approve_direction(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    sheet = _load_sheet(ctx, _require(args, "sheetId"))
    direction = _require(args, "direction")
    asset_id = _text(args, "assetId")
    candidate_id = _text(args, "candidateId")
    view = _view(sheet, direction)
    if view is None:
        raise ValueError("Direction not found.")
    if not asset_id and view.candidateGroupId and candidate_id:
        group = load_candidate_group(sheet.projectId, view.candidateGroupId)
        candidate = next((item for item in (group.candidates if group else []) if item.candidateId == candidate_id), None)
        if candidate and candidate.assetId:
            asset_id = candidate.assetId
    if not asset_id:
        raise ValueError("assetId or candidateId with a registered asset is required.")
    sheet = orchestrator.approve_direction(
        sheet,
        direction=direction,  # type: ignore[arg-type]
        approved_asset_id=asset_id,
        selected_candidate_id=candidate_id or None,
    )
    store.save_sheet(sheet)
    return {
        "ok": True,
        "sheetId": sheet.sheetId,
        "sheet": sheet.model_dump(mode="json"),
        "_summary": f"{direction.title()} view approved for the ERS.",
        "_evidence": {"source": "environment_reference_sheet.orchestrator.approve_direction + store.save_sheet"},
    }


def preview_validate_continuity(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    sheet = _load_sheet(ctx, _require(args, "sheetId"))
    return ToolPreview(
        summary="Validate ERS continuity across primary directions.",
        lines=[
            f"Sheet: {sheet.sheetId}",
            f"Approved directions: {len([item for item in sheet.directionalViews if item.approvedAssetId])}",
            "Uses metadata and approval state only. It does not claim pixel-level vision review.",
        ],
        resourceKind="project",
        resourceId=_project_id(ctx),
    )


def apply_validate_continuity(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    sheet = _load_sheet(ctx, _require(args, "sheetId"))
    sheet.continuity = validate_sheet(sheet)
    sheet.updatedAt = sheet.continuity.evaluatedAt
    store.save_sheet(sheet)
    return {
        "ok": True,
        "sheetId": sheet.sheetId,
        "continuity": sheet.continuity.model_dump(mode="json"),
        "_summary": sheet.continuity.summary,
        "_evidence": {"source": "environment_reference_sheet.continuity.validate_sheet"},
    }


def preview_compose_sheet(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    sheet = _load_sheet(ctx, _require(args, "sheetId"))
    return ToolPreview(
        summary="Prepare ERS composition metadata for rendering.",
        lines=[
            f"Sheet: {sheet.sheetId}",
            f"Continuity status: {sheet.continuity.status}",
            "Builds the creator-facing sheet layout state. Rendering/export is a separate explicit action.",
        ],
        resourceKind="project",
        resourceId=_project_id(ctx),
    )


def apply_compose_sheet(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    sheet = _load_sheet(ctx, _require(args, "sheetId"))
    sheet = orchestrator.compose_sheet_metadata(sheet)
    store.save_sheet(sheet)
    return {
        "ok": True,
        "sheetId": sheet.sheetId,
        "composition": sheet.composition.model_dump(mode="json"),
        "sheet": sheet.model_dump(mode="json"),
        "_summary": "ERS composition metadata is ready.",
        "_evidence": {"source": "environment_reference_sheet.orchestrator.compose_sheet_metadata"},
    }


def preview_register_project(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    sheet = _load_sheet(ctx, _require(args, "sheetId"))
    return ToolPreview(
        summary="Register this ERS back into the project.",
        lines=[
            f"Sheet: {sheet.sheetId}",
            f"Environment: {sheet.name}",
            "Creates or updates the linked Production Bible location record only after approval.",
        ],
        resourceKind="project",
        resourceId=_project_id(ctx),
    )


def apply_register_project(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    sheet = _load_sheet(ctx, _require(args, "sheetId"))
    existing_stable_id = _text(args, "locationStableId") or sheet.registration.locationStableId or ""
    location_payload = LocationData(
        description=sheet.description,
        atmosphere=", ".join(sheet.profile.atmosphere[:6]),
        lightingNotes=", ".join(sheet.profile.lightingNotes[:6]),
        notes=f"Registered from ERS {sheet.sheetId}",
        readiness="generation_ready",
        sourceAssetIds=[view.approvedAssetId for view in sheet.directionalViews if view.approvedAssetId],
    ).model_dump(mode="json")
    if existing_stable_id:
        entity = BibleDomainService.update_entity(
            ctx.db,
            _project_id(ctx),
            existing_stable_id,
            display_name=sheet.name,
            data=location_payload,
        )
    else:
        entity = BibleDomainService.create_entity(
            ctx.db,
            _project_id(ctx),
            entity_type="location",
            entity_key=f"location_{sheet.name.lower().replace(' ', '_')[:48]}",
            display_name=sheet.name,
            data=location_payload,
            slug=sheet.name.lower().replace(" ", "-")[:64],
        )
    folder_plan = storage_preflight(
        ctx.db,
        _project_id(ctx),
        task="environment reference sheet",
        system_key="scenes.locations",
        filename_hint=f"{sheet.name}-ers",
    )
    sheet.registration.locationStableId = entity.get("stableId")
    sheet.registration.locationDisplayName = entity.get("displayName")
    sheet.registration.libraryFolderPath = str(folder_plan.get("targetPath") or resolve_path(ctx.db, _project_id(ctx), system_key="scenes.locations"))
    sheet.registration.linkedSceneIds = [sheet.sceneId] if sheet.sceneId else []
    sheet.registration.projectMemoryNotes = [
        f"ERS registered for {sheet.name}.",
        f"Location stable id: {sheet.registration.locationStableId}.",
    ]
    sheet.registration.registeredAt = ERSProvenanceRecord().createdAt
    sheet.status = "registered"
    for stage in sheet.creationPlan.stages:
        if stage.stageKey == "registration":
            stage.status = "complete"
            stage.summary = "Production Bible location link recorded."
    store.save_sheet(sheet)
    return {
        "ok": True,
        "sheetId": sheet.sheetId,
        "registration": sheet.registration.model_dump(mode="json"),
        "sheet": sheet.model_dump(mode="json"),
        "_summary": "ERS registered to the project location record.",
        "_evidence": {"source": "BibleDomainService + project_library.storage_preflight"},
    }


def preview_set_optional_three_d(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Record the optional 3D truth label for this ERS.",
        lines=[
            f"Sheet: {_require(args, 'sheetId')}",
            f"Truth label: {_require(args, 'truthLabel')}",
            "This records truthful 3D disclosure only. It does not fabricate a mesh claim.",
        ],
        resourceKind="project",
        resourceId=_project_id(ctx),
    )


def apply_set_optional_three_d(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    sheet = _load_sheet(ctx, _require(args, "sheetId"))
    truth_label = _require(args, "truthLabel")
    sheet.optionalThreeD.truthLabel = truth_label  # type: ignore[assignment]
    sheet.optionalThreeD.assetId = _text(args, "assetId") or None
    sheet.optionalThreeD.note = _text(args, "note")
    sheet.optionalThreeD.status = "linked" if sheet.optionalThreeD.assetId else "blocked"
    sheet.updatedAt = ERSProvenanceRecord().createdAt
    store.save_sheet(sheet)
    return {
        "ok": True,
        "sheetId": sheet.sheetId,
        "optionalThreeD": sheet.optionalThreeD.model_dump(mode="json"),
        "_summary": f"Optional 3D labeled as {truth_label}.",
        "_evidence": {"source": "environment_reference_sheet.optional_three_d"},
    }


def preview_export_sheet(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    sheet = _load_sheet(ctx, _require(args, "sheetId"))
    export_kind = _require(args, "exportKind")
    return ToolPreview(
        summary=f"Render and register a {export_kind} ERS export.",
        lines=[
            f"Sheet: {sheet.sheetId}",
            f"Kind: {export_kind}",
            "Creates a real export file, registers it as a project asset, and keeps media local to the active project.",
        ],
        resourceKind="project",
        resourceId=_project_id(ctx),
    )


def apply_export_sheet(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    sheet = _load_sheet(ctx, _require(args, "sheetId"))
    sheet = orchestrator.compose_sheet_metadata(sheet)
    export_kind = _require(args, "exportKind")
    export_root = store.exports_dir(sheet.projectId, sheet.sheetId)
    if export_kind == "png":
        png_path = render_png(ctx.db, sheet)
        asset = register_derived_asset(
            ctx.db,
            project_id=sheet.projectId,
            source_path=png_path,
            kind="image",
            tag=f"{sheet.name} ERS",
            parent_asset_id=None,
            op="ers_export",
            prompt_meta={"sheetId": sheet.sheetId, "exportKind": "png"},
            library_key="exports.drafts",
            filename=png_path.name,
        )
        record = ERSExportRecord(
            exportKind="png",
            status="created",
            assetId=asset.id,
            filePath=str(png_path),
            archiveName=png_path.name,
            message="PNG ERS export rendered and registered.",
            createdAt=ERSProvenanceRecord().createdAt,
        )
    elif export_kind == "pdf":
        png_path = render_png(ctx.db, sheet)
        pdf_path = render_pdf(png_path, sheet)
        asset = register_derived_asset(
            ctx.db,
            project_id=sheet.projectId,
            source_path=pdf_path,
            kind="document",
            tag=f"{sheet.name} ERS PDF",
            parent_asset_id=None,
            op="ers_export",
            prompt_meta={"sheetId": sheet.sheetId, "exportKind": "pdf"},
            library_key="exports.drafts",
            filename=pdf_path.name,
        )
        record = ERSExportRecord(
            exportKind="pdf",
            status="created",
            assetId=asset.id,
            filePath=str(pdf_path),
            archiveName=pdf_path.name,
            message="PDF ERS export rendered and registered.",
            createdAt=ERSProvenanceRecord().createdAt,
        )
    elif export_kind == "offline_html":
        payload, archive_name = build_offline_package(ctx.db, sheet)
        zip_path = export_root / archive_name
        zip_path.write_bytes(payload)
        asset = register_derived_asset(
            ctx.db,
            project_id=sheet.projectId,
            source_path=zip_path,
            kind="document",
            tag=f"{sheet.name} ERS Offline Package",
            parent_asset_id=None,
            op="ers_export",
            prompt_meta={"sheetId": sheet.sheetId, "exportKind": "offline_html"},
            library_key="exports.drafts",
            filename=zip_path.name,
        )
        record = ERSExportRecord(
            exportKind="offline_html",
            status="created",
            assetId=asset.id,
            filePath=str(zip_path),
            archiveName=zip_path.name,
            message="Offline HTML package created with relative media paths.",
            createdAt=ERSProvenanceRecord().createdAt,
        )
    else:
        raise ValueError("Unsupported exportKind")
    sheet = update_export_record(sheet, record)
    for stage in sheet.creationPlan.stages:
        if stage.stageKey == "export":
            stage.status = "complete"
            stage.summary = "At least one ERS export has been created."
    store.save_sheet(sheet)
    return {
        "ok": True,
        "sheetId": sheet.sheetId,
        "export": record.model_dump(mode="json"),
        "sheet": sheet.model_dump(mode="json"),
        "_summary": record.message,
        "_evidence": {"source": "environment_reference_sheet.exports + generation_tools.register_derived_asset"},
    }
