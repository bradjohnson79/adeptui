"""Capability handler: ers.generate

Enqueues ONE Image Core job (purpose=environment_reference_sheet) for an
Environment Reference Sheet from a Spatial Map. The completed Library asset
is persisted onto the sheet (ers_composite_asset_id) so list_sheets /
resolve_ers_for_sheet can report has_reference.

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

Law #18: the one Image Core job goes through image-product
(``resolve_image_capability`` -> ``enqueue_imagegen_job`` / generate_images)
- no silent provider/model substitution. Creator-selected model =
requested = resolved = executed = provenance.
Law #7: this handler submits REAL jobs (no mock completion).
Async persist: handle stamps the sheet with the job id. When that imagegen
job completes, queue_worker._imagegen_commit_asset calls
persist_ers_composite_asset and sets sheet.ers_composite_asset_id.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


_DIRECTIONS: tuple[str, ...] = ("north", "east", "south", "west")
_ERS_PURPOSE = "environment_reference_sheet"


def image_core_prompt(plan: Any, fallback: str = "") -> str:
    """Image Core intent/prompt contract.

    ImageGenerationPlan has request / shotIntent / creativeDirection.
    Never read a top-level ``prompt`` attribute on the plan object.
    Prefer shotIntent.prompt, then request.prompt, then fallback.
    """
    shot = getattr(plan, "shotIntent", None)
    if shot is not None:
        text = getattr(shot, "prompt", None)
        if isinstance(text, str) and text.strip():
            return text.strip()
    request = getattr(plan, "request", None)
    if request is not None:
        text = getattr(request, "prompt", None)
        if isinstance(text, str) and text.strip():
            return text.strip()
    return (fallback or "").strip()


def _creator_model_body(
    *,
    hosted_model_id: str = "",
    model: str = "",
    model_family_preference: str = "",
    source: str = "",
    kie_image_model_id: str = "",
    fal_image_model_id: str = "",
    provider_kind: str = "",
    force_workflow_key: str = "",
    lock_model_family: bool = False,
) -> dict[str, Any]:
    """Pass through the creator-selected model. Never invent a default local workflow."""
    out: dict[str, Any] = {}
    if hosted_model_id:
        out["hostedModelId"] = hosted_model_id
    if model:
        out["model"] = model
    if model_family_preference:
        out["modelFamilyPreference"] = model_family_preference
    kind = (source or provider_kind or "").strip().lower()
    if kind:
        out["source"] = kind
        out["providerKind"] = kind
    if kie_image_model_id:
        out["kieImageModelId"] = kie_image_model_id
    if fal_image_model_id:
        out["falImageModelId"] = fal_image_model_id
    if force_workflow_key:
        out["forceWorkflowKey"] = force_workflow_key
        out["allow_force_workflow_key"] = True
        out["lockModelFamily"] = True
    if lock_model_family:
        out["lockModelFamily"] = True
    if out.get("hostedModelId") or out.get("kieImageModelId") or out.get("falImageModelId"):
        out["lockModelFamily"] = True
        out.setdefault("source", "api")
    return out


def build_ers_image_body(
    *,
    prompt: str,
    direction: str,
    execution_id: str,
    sheet_id: str,
    spatial_map_id: str,
    visual_style: str = "",
    north_lock: str = "north",
    operation: str = "image.generate",
    source_asset_id: str | None = None,
    selected: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Image-product body. Creator-selected model is requested=resolved=executed."""
    selected = dict(selected or {})
    body: dict[str, Any] = {
        "prompt": prompt,
        "negative_prompt": "",
        "width": 1280,
        "height": 720,
        "tag": f"codirector_ers_{execution_id[:8]}_{direction}",
        "purpose": _ERS_PURPOSE,
        "operation": operation,
        "aspectRatio": "16:9",
        "batchCount": 1,
        "creativeContext": {
            "objective": _ERS_PURPOSE,
            "executionId": execution_id,
            "direction": direction,
            "environmentReferenceSheetId": sheet_id,
            "spatialMapId": spatial_map_id,
            "northLockDirection": north_lock,
            "visualStyle": visual_style or "",
            "orientationNote": (
                "Scene-relative direction. North = top edge of the Atlas Shot."
            ),
        },
    }
    body.update(selected)
    if source_asset_id and operation == "image.edit":
        body["sourceAssetId"] = source_asset_id
        body["source_asset_id"] = source_asset_id
        body["edit"] = True
        body["referenceImage"] = source_asset_id
        body["reference_image"] = source_asset_id
    return body


def _spatial_map_reference_id(plan: Any, spatial_document: Any) -> str:
    raw = (
        getattr(plan, "reference_image", None)
        or getattr(plan, "referenceImage", None)
        or getattr(spatial_document, "backgroundAssetId", None)
    )
    return str(raw).strip() if raw else ""


def _choose_operation(body: dict[str, Any], reference_id: str) -> tuple[str, str]:
    """text_to_image unless a Spatial Map reference exists AND the model supports i2i."""
    if not reference_id:
        return "image.generate", "text_to_image"
    probe = dict(body)
    probe["operation"] = "image.edit"
    probe["edit"] = True
    probe["source_asset_id"] = reference_id
    probe["sourceAssetId"] = reference_id
    from ....image_product.resolve import resolve_image_capability

    cap = resolve_image_capability(probe)
    if cap.get("canExecute"):
        return "image.edit", "i2i"
    return "image.generate", "text_to_image"


def _pin_resolved_capability(body: dict[str, Any]) -> dict[str, Any]:
    """Resolve through image-product. Refuse instead of silently substituting."""
    from ....image_product.resolve import resolve_image_capability

    cap = resolve_image_capability(body)
    if not cap.get("canExecute"):
        reason = str(
            cap.get("reason")
            or "This model cannot run this Environment Reference Sheet request."
        )
        raise RuntimeError(reason)
    ctx = body.setdefault("creativeContext", {})
    if not isinstance(ctx, dict):
        ctx = {}
        body["creativeContext"] = ctx
    provider = str(cap.get("provider") or "")
    adapter = str(cap.get("adapter") or "")
    official = str(cap.get("officialModelId") or "")
    workflow_key = str(cap.get("workflowKey") or "")
    hosted = str(cap.get("hostedModelId") or "")
    ctx["resolvedProvider"] = provider
    ctx["resolvedAdapter"] = adapter
    ctx["resolvedOfficialModelId"] = official
    ctx["resolvedWorkflowKey"] = workflow_key
    if workflow_key:
        ctx["workflowKey"] = workflow_key
    if hosted:
        body["hostedModelId"] = hosted
    if provider == "kie" and official:
        body["kieImageModelId"] = official
        body.pop("falImageModelId", None)
    elif provider == "fal" and official:
        body["falImageModelId"] = official
        body.pop("kieImageModelId", None)
    elif provider == "local" and official and not body.get("modelFamilyPreference"):
        body["modelFamilyPreference"] = official
    return body


def _reuse_existing_ers_job(db: Session | None, project_id: str, tag: str) -> Any | None:
    """Duplicate-submit idempotency: reuse an in-flight job with the same tag."""
    if db is None or not tag:
        return None
    try:
        from ....db import Job
    except Exception:
        return None
    try:
        rows = (
            db.query(Job)
            .filter(Job.project_id == project_id, Job.kind.in_(("imagegen", "imagegen_edit")))
            .order_by(Job.created_at.desc())
            .limit(40)
            .all()
        )
    except Exception:
        return None
    terminal = {"failed", "cancelled", "canceled", "error"}
    for job in rows:
        status = str(getattr(job, "status", "") or "").strip().lower()
        if status in terminal:
            continue
        raw = getattr(job, "params_json", "") or ""
        try:
            params = json.loads(raw) if raw else {}
        except Exception:
            params = {}
        job_tag = str(params.get("tag") or "")
        if job_tag == tag:
            return job
    return None


def _enqueue_ers_image_product(db, project_id, body, scene_id=None):
    """Single image-product enqueue for ERS. Creator model already pinned."""
    from ....storyboard_jobs import enqueue_imagegen_job

    job = enqueue_imagegen_job(db, project_id, body, scene_id=scene_id)
    return {"jobId": job.id, "jobs": [{"jobId": job.id}]}


def persist_ers_composite_asset(
    db: Any = None,
    project_id: str = "",
    *,
    sheet_id: str = "",
    asset_id: str = "",
    package_id: str = "",
    sheet: Any = None,
    package: Any = None,
) -> dict[str, Any]:
    """Bind the completed Image Core Library asset onto the ERS sheet.

    Worker path: queue_worker._imagegen_commit_asset calls this with
    positional (db, project_id) when purpose=environment_reference_sheet.
    Sets sheet.ers_composite_asset_id and package.ers_composite_asset_id
    so list_sheets / resolve_ers_for_sheet has_reference is true.
    """
    from ....environment_reference_sheet.store import load_sheet, save_sheet
    from ....spatial_map.ers_persistence import (
        list_ers_packages,
        load_ers_package,
        save_ers_package,
    )

    asset_id = str(asset_id or "").strip()
    sheet_id = str(sheet_id or "").strip()
    package_id = str(package_id or "").strip()
    project_id = str(project_id or "").strip()

    current_package = package
    if current_package is None and package_id:
        try:
            current_package = load_ers_package(db, project_id, package_id)
        except Exception:
            current_package = None
    if current_package is None and sheet_id:
        try:
            packages = [
                p
                for p in list_ers_packages(db, project_id)
                if str((p.metadata or {}).get("sheet_id") or "") == sheet_id
                and not str(p.id).startswith("runtime-")
            ]
            if packages:
                current_package = sorted(
                    packages,
                    key=lambda p: p.updated_at or p.created_at or "",
                    reverse=True,
                )[0]
        except Exception:
            current_package = None
    if current_package is not None:
        current_package.ers_composite_asset_id = asset_id
        meta = dict(current_package.metadata or {})
        if sheet_id:
            meta["sheet_id"] = sheet_id
        meta["ers_composite_asset_id"] = asset_id
        current_package.metadata = meta
        save_ers_package(
            db, project_id, current_package, provenance="ers_composite_persist"
        )

    current_sheet = sheet
    if current_sheet is None and sheet_id:
        current_sheet = load_sheet(project_id, sheet_id)
    if current_sheet is not None:
        current_sheet.ers_composite_asset_id = asset_id
        composition = getattr(current_sheet, "composition", None)
        if composition is not None:
            ids = dict(getattr(composition, "renderedAssetIds", None) or {})
            ids["composite"] = asset_id
            ids.setdefault("png", asset_id)
            composition.renderedAssetIds = ids
        save_sheet(current_sheet)

    return {
        "sheet_id": sheet_id,
        "asset_id": asset_id,
        "ers_composite_asset_id": asset_id,
        "package_id": getattr(current_package, "id", None),
        "has_reference": bool(asset_id),
    }


def _stamp_ers_job_on_sheet(sheet: Any, *, job_id: str, package_id: str) -> None:
    """Record the queued Image Core job so persist can fill the composite later."""
    provenance = getattr(sheet, "provenance", None)
    if provenance is None:
        return
    details = dict(getattr(provenance, "details", None) or {})
    details["ers_image_job_id"] = job_id
    details["ers_package_id"] = package_id
    provenance.details = details
    provenance.note = (
        "One Image Core job queued (purpose=environment_reference_sheet). "
        "queue_worker._imagegen_commit_asset calls persist_ers_composite_asset "
        "on complete and sets ers_composite_asset_id so has_reference is true."
    )


def _ers_sheet_prompt(sheet: Any, spatial_document: Any) -> str:
    view_prompts = [
        str(getattr(view, "prompt", "") or "").strip()
        for view in (getattr(sheet, "directionalViews", None) or [])
        if str(getattr(view, "prompt", "") or "").strip()
    ]
    seed = (
        str(getattr(spatial_document, "masterEnvironmentPrompt", "") or "").strip()
        or (getattr(sheet, "description", None) or "").strip()
        or " ".join(view_prompts)
        or (getattr(sheet, "name", None) or "Environment reference sheet")
    )
    if view_prompts:
        seed = (seed + " " + " ".join(view_prompts)).strip()
        seed = (
            "Environment reference sheet of one locked environment. "
            + seed
            + " North, east, south, and west stay the same place, lighting, "
            "materials, and time of day. Do not redesign the world."
        )
    core_plan = type(
        "ImageCoreIntent",
        (),
        {
            "shotIntent": type("ShotIntent", (), {"prompt": seed})(),
            "request": type("Request", (), {"prompt": seed})(),
        },
    )()
    return image_core_prompt(core_plan, fallback=seed)


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
    hosted_model_id: str = "",
    hostedModelId: str = "",
    model: str = "",
    model_family_preference: str = "",
    modelFamilyPreference: str = "",
    source: str = "",
    kie_image_model_id: str = "",
    kieImageModelId: str = "",
    fal_image_model_id: str = "",
    falImageModelId: str = "",
    provider_kind: str = "",
    providerKind: str = "",
    provider: str = "",
    forceWorkflowKey: str = "",
    lockModelFamily: bool = False,
) -> dict[str, Any]:
    """Enqueue ONE Image Core job (purpose=environment_reference_sheet) and persist the asset."""
    from ....environment_reference_sheet.orchestrator import (
        attach_spatial_map,
        compose_sheet_metadata,
        create_sheet,
    )
    from ....environment_reference_sheet.store import list_sheets, save_sheet
    from ....spatial_map.ers_contracts import EnvironmentReferencePackage
    from ....spatial_map.ers_persistence import save_ers_package
    from ....spatial_map.ers_projection import project_document_placements
    from ....spatial_map.service import get_document

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

    sheet = attach_spatial_map(db, sheet, spatial_map_id=spatial_map_id)
    sheet = compose_sheet_metadata(sheet)
    spatial_document = get_document(db, project_id, spatial_map_id)
    creator_model = _creator_model_body(
        hosted_model_id=hosted_model_id or hostedModelId,
        model=model,
        model_family_preference=model_family_preference or modelFamilyPreference,
        source=source or provider or provider_kind or providerKind,
        kie_image_model_id=kie_image_model_id or kieImageModelId,
        fal_image_model_id=fal_image_model_id or falImageModelId,
        provider_kind=provider_kind or providerKind,
        force_workflow_key=forceWorkflowKey,
        lock_model_family=bool(lockModelFamily),
    )

    seed_prompt = _ers_sheet_prompt(sheet, spatial_document)
    from types import SimpleNamespace

    prompt_text = image_core_prompt(
        SimpleNamespace(
            shotIntent=SimpleNamespace(prompt=seed_prompt),
            request=SimpleNamespace(prompt=str(getattr(sheet, "description", None) or "")),
        ),
        fallback=seed_prompt,
    )
    reference_id = _spatial_map_reference_id(None, spatial_document)
    body = build_ers_image_body(
        prompt=prompt_text,
        direction="sheet",
        execution_id=execution_id,
        sheet_id=sheet.sheetId,
        spatial_map_id=spatial_map_id,
        visual_style=visual_style,
        north_lock=(
            sheet.spatialMap.northLockDirection if sheet.spatialMap else "north"
        ),
        selected=creator_model,
    )
    operation, operation_intent = _choose_operation(body, reference_id)
    body["operation"] = operation
    body["creativeContext"]["operationIntent"] = operation_intent
    if operation == "image.edit" and reference_id:
        body["source_asset_id"] = reference_id
        body["sourceAssetId"] = reference_id
        body["edit"] = True
        body["referenceImage"] = reference_id
        body["reference_image"] = reference_id
    else:
        # Honest T2I: model cannot I2I. Atlas may inform the prompt only.
        # Never claim pixel I2I (no edit=true / source_asset_id).
        body.pop("edit", None)
        body.pop("source_asset_id", None)
        body.pop("sourceAssetId", None)
        body.pop("referenceImage", None)
        body.pop("reference_image", None)
        if reference_id:
            note = (
                " Atlas shot informs this environment as text only "
                f"(asset {reference_id}); not pixel image-to-image."
            )
            prompt = str(body.get("prompt") or "")
            if "not pixel image-to-image" not in prompt:
                body["prompt"] = (prompt + note).strip()
    try:
        from ....image_product.compile import compile_image_request

        compiled = compile_image_request(project_id, body)
        intent = compiled.get("imageIntent") or {}
        core_prompt = str(intent.get("prompt") or "").strip()
        if core_prompt:
            body["prompt"] = core_prompt
    except Exception as exc:
        logger.info("ERS Image Core compile used seed prompt: %s", exc)
    body = _pin_resolved_capability(body)

    package = EnvironmentReferencePackage(
        project_id=project_id,
        scene_layout_id=spatial_map_id,
        atlas_asset_id=getattr(spatial_document, "backgroundAssetId", None),
        placements=project_document_placements(spatial_document),
        style_context={"visual_style": visual_style or ""},
        orientation="atlas-north-up",
        directional_assets={d: None for d in _DIRECTIONS},
        metadata={
            "execution_id": execution_id,
            "sheet_id": sheet.sheetId,
        },
    )
    body.setdefault("creativeContext", {})
    body["creativeContext"]["ersPackageId"] = package.id
    body["creativeContext"]["environmentReferenceSheetId"] = sheet.sheetId

    existing = _reuse_existing_ers_job(db, project_id, str(body.get("tag") or ""))
    if existing is not None:
        job_id = getattr(existing, "id", None) or str(existing)
    else:
        queued = _enqueue_ers_image_product(
            db, project_id, body, scene_id=scene_id or None
        )
        if isinstance(queued, dict):
            job_id = queued.get("jobId") or (queued.get("jobs") or [{}])[0].get("jobId")
        else:
            job_id = getattr(queued, "id", None)
    job_id = str(job_id or "")

    package.metadata = {
        **dict(package.metadata or {}),
        "ers_image_job_id": job_id,
        "directional_job_ids": [job_id],
    }
    _stamp_ers_job_on_sheet(sheet, job_id=job_id, package_id=package.id)
    save_ers_package(db, project_id, package)
    save_sheet(sheet)

    return {
        "job_ids": [job_id],
        "child_jobs": [
            {
                "job_id": job_id,
                "label": "Environment Reference Sheet",
                "status": "queued",
                "child_index": 0,
                "metadata": {
                    "purpose": _ERS_PURPOSE,
                    "operation": body.get("operation"),
                    "operationIntent": body.get("creativeContext", {}).get(
                        "operationIntent"
                    ),
                    "resolvedProvider": body.get("creativeContext", {}).get(
                        "resolvedProvider"
                    ),
                    "resolvedWorkflowKey": body.get("creativeContext", {}).get(
                        "resolvedWorkflowKey"
                    ),
                    "ers_package_id": package.id,
                    "sheet_id": sheet.sheetId,
                },
            }
        ],
        "surface_type": "ers_generation",
        "ers_package_id": package.id,
        "sheet_id": sheet.sheetId,
        "spatial_map_id": spatial_map_id,
        "purpose": _ERS_PURPOSE,
    }
