"""Project-level Prop Creator — PropEntity profiles, generate, approve, delete."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from ..db import Asset, Job
from ..scene_creator.generation import list_local_generator_families
from ..spatial_map.ers_contracts import (
    GeneratorSourceSelection,
    PropCandidate,
    PropEntity,
    normalize_prop_tag,
)
from ..spatial_map.ers_persistence import (
    delete_prop_entity,
    list_prop_entities,
    load_prop_entity_by_id,
    save_prop_entity,
)
from .generation import (
    api_image_models_configured,
    build_prop_candidate_plans,
    persist_generator_selection,
)
from .prompt import compile_prop_prompt

logger = logging.getLogger(__name__)


class PropCreatorError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def is_approved(prop: PropEntity) -> bool:
    return bool((prop.approved_asset_id or "").strip())


def visual_identity_id(prop: PropEntity) -> str:
    return (prop.approved_asset_id or "").strip() or (prop.library_asset_id or "").strip()


def unique_tag(db: Session, project_id: str, label: str, *, exclude_id: str = "") -> str:
    base = normalize_prop_tag(label)
    tags = {p.tag for p in list_prop_entities(db, project_id) if p.id != exclude_id}
    if base not in tags:
        return base
    for i in range(2, 80):
        candidate = f"{base}-{i}"
        if candidate not in tags:
            return candidate
    return f"{base}-{__import__('uuid').uuid4().hex[:6]}"


def list_props(db: Session, project_id: str, *, approved_only: bool = False) -> list[PropEntity]:
    props = list_prop_entities(db, project_id)
    if approved_only:
        props = [p for p in props if is_approved(p)]
    props.sort(key=lambda p: (p.display_label or p.tag or "").lower())
    return props


def get_prop(db: Session, project_id: str, prop_id: str) -> PropEntity:
    prop = load_prop_entity_by_id(db, project_id, prop_id)
    if prop is None or prop.project_id != project_id:
        raise PropCreatorError("Prop not found.", 404)
    _sync_candidates(db, project_id, prop)
    save_prop_entity(db, project_id, prop)
    return prop


def create_or_update_prop(
    db: Session,
    project_id: str,
    *,
    prop_id: str = "",
    name: str = "",
    visual_style: str = "",
    description: str = "",
    reference_asset_id: str | None = None,
    clear_reference: bool = False,
    generator: dict[str, Any] | None = None,
    use_as_identity: bool = False,
    identity_asset_id: str = "",
) -> PropEntity:
    existing = load_prop_entity_by_id(db, project_id, prop_id) if prop_id else None
    if prop_id and existing is None:
        raise PropCreatorError("Prop not found.", 404)
    if existing and existing.project_id != project_id:
        raise PropCreatorError("Prop not found.", 404)
    label = (name or (existing.display_label if existing else "")).strip()
    if not label:
        raise PropCreatorError("Name is required to save a Prop.")
    prop = existing or PropEntity(project_id=project_id)
    prop.display_label = label
    prop.tag = unique_tag(db, project_id, label, exclude_id=prop.id)
    prop.visual_style = (visual_style or "").strip()
    prop.description = (description or "").strip()
    prop.notes = prop.description
    if clear_reference:
        prop.reference_asset_id = None
    elif reference_asset_id is not None:
        prop.reference_asset_id = (reference_asset_id or "").strip() or None
    if generator:
        prop.generator = GeneratorSourceSelection.model_validate(generator)
    save_prop_entity(db, project_id, prop)
    if use_as_identity:
        return use_as_prop_identity(
            db,
            project_id,
            prop.id,
            asset_id=identity_asset_id or (prop.reference_asset_id or ""),
            source_type="library",
        )
    return prop


def generate_candidates(
    db: Session,
    project_id: str,
    prop_id: str,
    *,
    local_enabled: bool = True,
    api_enabled: bool = False,
    local_family: str = "",
    api_model: str = "",
    candidate_count: int = 4,
    generator_sources: dict[str, Any] | None = None,
) -> PropEntity:
    prop = get_prop(db, project_id, prop_id)
    compiled = compile_prop_prompt(prop)
    has_reference = bool((prop.reference_asset_id or "").strip())
    plans = build_prop_candidate_plans(
        local_enabled=local_enabled,
        api_enabled=api_enabled,
        local_family=local_family,
        api_model=api_model,
        has_reference=has_reference,
        candidate_count=candidate_count,
        generator_sources=generator_sources,
    )
    persisted = persist_generator_selection(
        local_enabled=local_enabled,
        api_enabled=api_enabled,
        local_family=local_family,
        api_model=api_model,
        generator_sources=generator_sources,
    )
    prop.generator = GeneratorSourceSelection.model_validate(persisted)

    prop.candidates = _enqueue_plans(db, project_id, prop, compiled, plans)
    save_prop_entity(db, project_id, prop)
    return prop


def retry_candidate(db: Session, project_id: str, prop_id: str, candidate_id: str) -> PropEntity:
    prop = get_prop(db, project_id, prop_id)
    target = next((c for c in prop.candidates if c.id == candidate_id), None)
    if target is None:
        raise PropCreatorError("Candidate not found.")
    compiled = compile_prop_prompt(prop)
    has_reference = bool((prop.reference_asset_id or "").strip())
    if target.source == "api":
        retry_sources: dict[str, Any] = {
            "local": None,
            "api": [
                {
                    "modelId": target.model or target.family,
                    "model": target.model or target.family,
                    "enabled": True,
                    "batchCount": 1,
                    "generationMode": target.conditioning,
                }
            ],
        }
    else:
        retry_sources = {
            "local": [
                {
                    "modelId": target.family or prop.generator.local_family,
                    "family": target.family or prop.generator.local_family,
                    "enabled": True,
                    "batchCount": 1,
                    "generationMode": target.conditioning,
                }
            ],
            "api": None,
        }
    plans = build_prop_candidate_plans(
        local_enabled=target.source != "api",
        api_enabled=target.source == "api",
        local_family=target.family or prop.generator.local_family,
        api_model=target.model,
        has_reference=has_reference,
        candidate_count=1,
        generator_sources=retry_sources,
    )
    replacements = _enqueue_plans(db, project_id, prop, compiled, plans)
    if replacements:
        replacement = replacements[0]
        replacement.index = target.index
        replacement.take_label = target.take_label
        prop.candidates = [replacement if c.id == candidate_id else c for c in prop.candidates]
        save_prop_entity(db, project_id, prop)
    return prop



def use_as_prop_identity(
    db: Session,
    project_id: str,
    prop_id: str,
    *,
    asset_id: str = "",
    source_type: str = "library",
) -> PropEntity:
    """Point Prop visual identity at an existing Library/upload asset. No byte copy.

    Sets approved_asset_id = asset_id and mirrors library_asset_id. PropEntity.id
    is unchanged. Does not enqueue generation.
    """
    prop = get_prop(db, project_id, prop_id)
    aid = (asset_id or prop.reference_asset_id or "").strip()
    if not aid:
        raise PropCreatorError("Attach a reference image before using it as Prop Identity.")
    asset = db.get(Asset, aid)
    if asset is None or asset.project_id != project_id:
        raise PropCreatorError("Reference asset not found.", 404)
    prev = prop.approved_asset_id
    if prev and prev != aid:
        _set_asset_approval(db, project_id, prev, approved=False)
    prop.approved_asset_id = aid
    prop.library_asset_id = aid
    _set_asset_approval(db, project_id, aid, approved=True)
    notes = (prop.notes or "").strip()
    marker = f"identitySource={source_type or 'library'}"
    if marker not in notes:
        prop.notes = f"{notes} {marker}".strip() if notes else marker
    save_prop_entity(db, project_id, prop)
    return prop


def approve_candidate(db: Session, project_id: str, prop_id: str, candidate_id: str) -> PropEntity:
    prop = get_prop(db, project_id, prop_id)
    candidate = next((c for c in prop.candidates if c.id == candidate_id), None)
    if candidate is None:
        raise PropCreatorError("Candidate not found.")
    if candidate.status != "complete" or not candidate.asset_id:
        raise PropCreatorError("That look is not ready yet.")
    prev = prop.approved_asset_id
    if prev and prev != candidate.asset_id:
        _set_asset_approval(db, project_id, prev, approved=False)
    prop.approved_asset_id = candidate.asset_id
    prop.library_asset_id = candidate.asset_id
    _set_asset_approval(db, project_id, candidate.asset_id, approved=True)
    save_prop_entity(db, project_id, prop)
    return prop


def delete_prop(db: Session, project_id: str, prop_id: str) -> dict[str, Any]:
    prop = get_prop(db, project_id, prop_id)
    unlinked = _unlink_spatial_props(db, project_id, prop.id)
    shots_unlinked = _unlink_scene_shots(db, project_id, prop.id)
    deleted = delete_prop_entity(db, project_id, prop.id)
    if deleted is None:
        raise PropCreatorError("Prop not found.", 404)
    return {
        "ok": True,
        "prop_id": prop.id,
        "library_assets_kept": True,
        "spatial_unlinked": unlinked,
        "shots_unlinked": shots_unlinked,
    }


def workspace(db: Session, project_id: str, *, prop_id: str = "") -> dict[str, Any]:
    props = list_props(db, project_id)
    selected = None
    if prop_id:
        selected = next((p for p in props if p.id == prop_id), None)
        if selected is None:
            selected = get_prop(db, project_id, prop_id)
            props = list_props(db, project_id)
    return {
        "props": [p.model_dump() for p in props],
        "selected_prop": selected.model_dump() if selected else None,
        "api_generation_available": api_image_models_configured(),
        "local_families": list_local_generator_families(has_reference=False),
    }


def _fail_api_candidate_error(plan: dict[str, Any], detail: str = "") -> str:
    model = plan.get("hosted_model_id") or plan.get("model") or plan.get("model_id") or "unknown"
    provider = plan.get("provider_id") or "unknown provider"
    extra = f" {detail}" if detail else ""
    return (
        f"No certified API route for {model} ({provider}). "
        "This row was not redirected to a local generator. "
        "Add a provider in Setup or pick a discovered cloud model that can execute."
        f"{extra}"
    )


def _enqueue_api_job(db: Session, project_id: str, body: dict[str, Any], plan: dict[str, Any]) -> Any:
    """Run the hosted model or fail this row. Never substitute a local family."""
    from ..storyboard_jobs import enqueue_imagegen_job

    hosted = str(plan.get("hosted_model_id") or plan.get("model_id") or plan.get("model") or "").strip()
    if not hosted:
        raise PropCreatorError(_fail_api_candidate_error(plan, "No modelId was provided."))
    try:
        from .generation import _hosted_family_for_model

        family = _hosted_family_for_model(hosted) or plan.get("family") or hosted
    except Exception:
        family = plan.get("family") or hosted
    body["modelFamilyPreference"] = family
    body["model"] = hosted
    body["lockModelFamily"] = True
    body["providerPreference"] = "cloud"
    body["hostedModelId"] = hosted
    body.pop("forceWorkflowKey", None)
    body.pop("allow_force_workflow_key", None)
    job = enqueue_imagegen_job(db, project_id, body)
    try:
        params = json.loads(job.params_json or "{}")
    except Exception:
        params = {}
    runtime_key = str((params.get("imageRuntime") or {}).get("workflowKey") or "")
    fal_id = None
    try:
        from ..fal_catalog import fal_image_model_id_for_dock

        fal_id = fal_image_model_id_for_dock(hosted)
    except Exception:
        fal_id = None
    if fal_id:
        params["cloudPaid"] = True
        params["falImageModelId"] = fal_id
        params["hostedModelId"] = hosted
        params["providerPreference"] = "cloud"
        job.params_json = json.dumps(params)
        db.commit()
        db.refresh(job)
        return job
    cloud_paid = bool(params.get("cloudPaid"))
    if not cloud_paid and not runtime_key.startswith("imagen."):
        job.status = "failed"
        job.message = (
            f"API model {hosted} resolved to local workflow {runtime_key or 'unknown'}; "
            "refusing silent Comfy/Z-Image substitute."
        )
        db.commit()
        db.refresh(job)
        raise PropCreatorError(job.message)
    return job


def _enqueue_plans(
    db: Session,
    project_id: str,
    prop: PropEntity,
    compiled: dict[str, Any],
    plans: list[dict[str, Any]],
) -> list[PropCandidate]:
    from ..storyboard_jobs import enqueue_imagegen_job

    candidates: list[PropCandidate] = []
    for plan in plans:
        workflow_key = plan.get("workflow_key") or (
            f"{plan['family']}.ref_edit"
            if plan["conditioning"] == "reference_conditioned"
            else f"{plan['family']}.txt2img"
        )
        body: dict[str, Any] = {
            "prompt": compiled["prompt"],
            "negative_prompt": compiled["negative_prompt"],
            "width": 1024,
            "height": 1024,
            "modelFamilyPreference": plan["family"],
            "model": plan.get("model_id") or plan["model"],
            "lockModelFamily": True,
            "seed": plan["seed"],
            "tag": f"prop_{prop.tag or prop.id[:8]}_c{plan['index'] + 1}",
            "purpose": "project_prop",
            "creativeContext": {
                "objective": "project_prop",
                "propId": prop.id,
                "sheetId": "",
                "workflowKey": workflow_key,
                "candidateIndex": plan["index"],
                "conditioning": plan["conditioning"],
                "visualStyle": compiled["visual_style"],
                "providerKind": plan["source"],
                "hostedModelId": plan.get("hosted_model_id"),
                "providerId": plan.get("provider_id") or "",
                "modelId": plan.get("model_id") or plan["model"],
                "batchIndex": plan.get("batch_index") or (plan["index"] + 1),
                "batchOf": plan.get("batch_of") or 1,
            },
        }
        if plan["conditioning"] == "reference_conditioned" and prop.reference_asset_id:
            body["source_asset_id"] = prop.reference_asset_id
            body["denoise"] = 0.55
            ctx = body["creativeContext"]
            ctx["referenceAssetId"] = prop.reference_asset_id
            ctx["referenceLocked"] = True
            ctx["referenceFidelityMode"] = f"{plan['family']}_ref_edit"
        job_id = f"failed_prop_cand_{plan['index']}"
        status = "failed"
        error = ""
        try:
            if plan["source"] == "api":
                job = _enqueue_api_job(db, project_id, body, plan)
                if (job.status or "").lower() in {"failed", "error"}:
                    job_id = job.id
                    error = job.message or _fail_api_candidate_error(plan)
                else:
                    job_id = job.id
                    status = "queued"
                    error = ""
            else:
                if workflow_key:
                    body["forceWorkflowKey"] = workflow_key
                    body["allow_force_workflow_key"] = True
                job = enqueue_imagegen_job(db, project_id, body)
                job_id = job.id
                status = "queued"
                error = ""
        except PropCreatorError as exc:
            logger.error("Prop API candidate failed honestly: %s", exc)
            error = str(exc)
        except Exception as exc:
            logger.error("Prop candidate enqueue failed: %s", exc)
            error = str(exc)
            if plan["source"] == "api":
                error = _fail_api_candidate_error(plan, str(exc))
        candidates.append(
            PropCandidate(
                prop_id=prop.id,
                index=plan["index"],
                job_id=job_id,
                status=status,  # type: ignore[arg-type]
                source=plan["source"],
                family=plan["family"],
                model=plan["model"],
                seed=plan["seed"],
                provenance_label=plan["provenance_label"],
                conditioning=plan["conditioning"],
                take_label=f"Look {plan['index'] + 1}",
                error=error,
            )
        )
    return candidates


def _sync_candidates(db: Session, project_id: str, prop: PropEntity) -> None:
    for candidate in prop.candidates:
        if candidate.status in {"complete", "failed"} and candidate.asset_id:
            continue
        job_id = candidate.job_id
        if not job_id or job_id.startswith("failed_"):
            candidate.status = "failed"
            continue
        job = db.get(Job, job_id)
        if job is None or job.project_id != project_id:
            continue
        status = (job.status or "").lower()
        if status in {"done", "completed", "complete", "success"}:
            asset_id = _job_asset_id(job)
            candidate.asset_id = asset_id or candidate.asset_id
            candidate.status = "complete" if candidate.asset_id else "generating"
        elif status in {"failed", "error", "cancelled"}:
            candidate.status = "failed"
            candidate.error = job.message or candidate.error
        elif status in {"running", "preview"}:
            candidate.status = "generating"
        else:
            candidate.status = "queued"


def _job_asset_id(job: Job) -> str | None:
    try:
        params = json.loads(job.params_json or "{}")
    except Exception:
        params = {}
    asset_id = params.get("output_asset_id")
    return str(asset_id) if asset_id else None


def _set_asset_approval(db: Session, project_id: str, asset_id: str, *, approved: bool) -> None:
    asset = db.get(Asset, asset_id)
    if asset is None or asset.project_id != project_id:
        return
    asset.production_approval = "approved" if approved else "none"
    try:
        labels = json.loads(asset.labels_json or "[]")
    except Exception:
        labels = []
    if not isinstance(labels, list):
        labels = []
    labels = [str(x) for x in labels if x]
    if approved and "approved_prop" not in labels:
        labels.append("approved_prop")
    if not approved:
        labels = [x for x in labels if x != "approved_prop"]
    asset.labels_json = json.dumps(labels)
    db.commit()


def _unlink_scene_shots(db: Session, project_id: str, prop_id: str) -> int:
    """Drop a deleted PropEntity id from saved SceneShot lists. Keep the shot."""
    try:
        from ..spatial_map.ers_persistence import list_scene_shots, save_scene_shot
    except Exception:
        return 0
    unlinked = 0
    for shot in list_scene_shots(db, project_id):
        changed = False
        ids = list(shot.prop_entity_ids or [])
        if prop_id in ids:
            shot.prop_entity_ids = [item for item in ids if item != prop_id]
            changed = True
        blocking = getattr(getattr(shot, "take_memory", None), "blocking", None)
        if isinstance(blocking, dict):
            block_ids = list(blocking.get("prop_entity_ids") or [])
            if prop_id in block_ids:
                blocking["prop_entity_ids"] = [item for item in block_ids if item != prop_id]
                changed = True
        if changed:
            save_scene_shot(db, project_id, shot)
            unlinked += 1
    return unlinked


def _unlink_spatial_props(db: Session, project_id: str, prop_id: str) -> int:
    try:
        from ..spatial_map.models import SpatialMapDocumentRow
        from ..spatial_map.service import _parse_document, _save_document
    except Exception:
        return 0
    rows = db.query(SpatialMapDocumentRow).filter(SpatialMapDocumentRow.project_id == project_id).all()
    unlinked = 0
    for row in rows:
        doc = _parse_document(row)
        changed = False
        for item in doc.props or []:
            if getattr(item, "propId", None) == prop_id:
                item.propId = None
                changed = True
                unlinked += 1
        if changed:
            _save_document(db, row, doc)
    return unlinked


def _spatial_placements_for_prop(db: Session, project_id: str, prop_id: str) -> int:
    try:
        from ..spatial_map.service import list_documents
        docs = list_documents(db, project_id)
    except Exception:
        return 0
    return sum(1 for doc in docs for item in (doc.props or []) if getattr(item, "propId", None) == prop_id)
