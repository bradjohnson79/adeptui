"""Server authority for supplementary views. Persist on the Spatial Map document."""

from __future__ import annotations

import json
import os
import random
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..service import _save_document, get_document
from .confidence import summarize_confidence
from .contracts import (
    SUPPLEMENTARY_PURPOSE,
    SUPPLEMENTARY_TASK_CLASS,
    SpatialReferenceRecord,
    SupplementaryState,
    ViewSlot,
    _now,
    observed_asset_ids,
)
from .gate import evaluate_set_gate, evaluate_view_gate
from .mutex import assert_can_start
from .select import prompt_for_role, select_camera_role
from . import strips


def _state_from_doc(document) -> SupplementaryState:
    raw = getattr(document, "supplementaryViews", None)
    if isinstance(raw, SupplementaryState):
        return raw
    if isinstance(raw, dict):
        return SupplementaryState.model_validate(raw)
    return SupplementaryState(masterAssetId=str(document.backgroundAssetId or document.originalEnvironmentReferenceAssetId or ""))


def _job_output_asset_id(job: Any) -> str:
    raw = getattr(job, "params_json", None) or ""
    try:
        params = json.loads(raw) if raw else {}
    except Exception:
        params = {}
    if not isinstance(params, dict):
        return ""
    return str(params.get("output_asset_id") or params.get("outputAssetId") or "").strip()


def _job_prompt_id(job: Any) -> str:
    pid = str(getattr(job, "comfy_prompt_id", "") or "").strip()
    if pid:
        return pid
    raw = getattr(job, "history_json", None) or ""
    try:
        hist = json.loads(raw) if raw else {}
    except Exception:
        hist = {}
    if isinstance(hist, dict):
        return str(hist.get("prompt_id") or hist.get("comfyPromptId") or hist.get("promptId") or "").strip()
    return ""


def _reference_payload(record: SpatialReferenceRecord) -> dict[str, Any]:
    return {
        "assetId": record.assetId,
        "referenceRole": record.referenceRole,
        "evidenceClass": record.evidenceClass,
        "source": record.source,
        "cameraRole": record.cameraRole,
        "sourceAssetId": record.sourceAssetId,
        "generationEngine": record.generationEngine,
        "confidence": record.confidence,
        "approvedForSpatialReasoning": record.approvedForSpatialReasoning,
        "status": record.status,
        "notGeometryEvidence": record.evidenceClass == "INFERRED",
    }


def _sync_packet_references(db: Session, document, state: SupplementaryState) -> None:
    packet_id = str(getattr(document, "reconstructionPacketId", "") or "").strip()
    project_id = str(getattr(document, "projectId", "") or "").strip()
    if not packet_id or not project_id:
        return
    from ..reconstruction.persist import load_reconstruction_packet, save_reconstruction_packet

    packet = load_reconstruction_packet(db, project_id, packet_id)
    if packet is None:
        return
    master = SpatialReferenceRecord(
        slot="MASTER",
        assetId=state.masterAssetId,
        referenceRole="PRIMARY_ENVIRONMENT",
        evidenceClass="OBSERVED",
        source="USER",
        approvedForSpatialReasoning=True,
        status="READY",
    )
    refs = [master]
    if state.viewA and state.viewA.status != "REJECTED":
        refs.append(state.viewA)
    if state.viewB and state.viewB.status != "REJECTED":
        refs.append(state.viewB)
    packet.references = [_reference_payload(item) for item in refs]
    packet.sourceAssetIds = observed_asset_ids(master_asset_id=state.masterAssetId, references=refs)
    save_reconstruction_packet(db, packet)


def _persist(db: Session, document, state: SupplementaryState):
    state.updatedAt = _now()
    document.supplementaryViews = state.model_dump()
    _sync_packet_references(db, document, state)
    from ..models import SpatialMapDocumentRow

    row = db.get(SpatialMapDocumentRow, document.id)
    if row is None:
        raise HTTPException(404, "Spatial Map was not found.")
    return _save_document(db, row, document)


def _asset_path(db: Session, project_id: str, asset_id: str) -> Path | None:
    from ...db import Asset

    if not asset_id:
        return None
    asset = db.get(Asset, asset_id)
    if asset is None or str(asset.project_id or "") != project_id:
        return None
    path = Path(str(asset.path or ""))
    return path if path.is_file() else None


def get_state(db: Session, project_id: str, document_id: str) -> dict[str, Any]:
    document = get_document(db, project_id, document_id)
    state = _state_from_doc(document)
    if not state.masterAssetId:
        state.masterAssetId = str(document.backgroundAssetId or document.originalEnvironmentReferenceAssetId or "")
    master = SpatialReferenceRecord(
        slot="MASTER",
        assetId=state.masterAssetId,
        referenceRole="PRIMARY_ENVIRONMENT",
        evidenceClass="OBSERVED",
        source="USER",
        approvedForSpatialReasoning=True,
        status="READY",
    )
    state.confidence = summarize_confidence(
        master=master,
        view_a=state.viewA,
        view_b=state.viewB,
        scene_description=document.masterEnvironmentPrompt or "",
    )
    refs = [master]
    if state.viewA and state.viewA.status != "REJECTED":
        refs.append(state.viewA)
    if state.viewB and state.viewB.status != "REJECTED":
        refs.append(state.viewB)
    return {
        "documentId": document.id,
        "master": master.model_dump(),
        "state": state.model_dump(),
        "references": [_reference_payload(item) for item in refs],
        "observedAssetIds": observed_asset_ids(
            master_asset_id=state.masterAssetId,
            references=refs,
        ),
        "notGeometryEvidence": True,
    }


def analyze_next_view(db: Session, project_id: str, document_id: str) -> dict[str, Any]:
    document = get_document(db, project_id, document_id)
    state = _state_from_doc(document)
    master_id = str(document.backgroundAssetId or document.originalEnvironmentReferenceAssetId or "")
    if not master_id:
        raise HTTPException(400, "Choose a master location image first.")
    state.masterAssetId = master_id
    slot: ViewSlot = "B" if state.viewA and state.viewA.approvedForSpatialReasoning else "A"
    if slot == "B" and not (state.viewA and state.viewA.approvedForSpatialReasoning):
        raise HTTPException(409, "Accept View A for Spatial Reasoning before choosing View B.")
    remaining = list(state.confidence.unknown) if state.confidence else []
    picked = select_camera_role(
        scene_description=document.masterEnvironmentPrompt or "",
        environment_type="",
        slot=slot,
        accepted_role_a=state.viewA.cameraRole if state.viewA else None,
        remaining_unknown=remaining,
    )
    if slot == "A":
        state.selectedRoleA = picked["cameraRole"]
    else:
        state.selectedRoleB = picked["cameraRole"]
    _persist(db, document, state)
    return {"slot": slot, **picked, "promptPreview": prompt_for_role(picked["cameraRole"], scene_description=document.masterEnvironmentPrompt or "")}


def _enqueue(db: Session, project_id: str, master_id: str, prompt: str, map_id: str, *, seed: int | None = None) -> Any:
    from ...storyboard_jobs import enqueue_imagegen_job

    body = {
        "purpose": SUPPLEMENTARY_PURPOSE,
        "taskType": SUPPLEMENTARY_TASK_CLASS,
        "sourceAssetId": master_id,
        "forceWorkflowKey": "qwen2512.ref",
        "allow_force_workflow_key": True,
        "model": "qwen2512",
        "modelFamilyPreference": "qwen2512",
        "source": "local",
        "operation": "image.generate",
        "prompt": prompt,
        "tag": "spatial_supplementary_view",
        "spatialMapId": map_id,
    }
    if seed is not None:
        body["seed"] = int(seed)
    return enqueue_imagegen_job(db, project_id, body)


def generate_view(
    db: Session,
    project_id: str,
    document_id: str,
    slot: ViewSlot,
    *,
    e2e_asset_id: str = "",
) -> dict[str, Any]:
    document = get_document(db, project_id, document_id)
    state = _state_from_doc(document)
    master_id = str(document.backgroundAssetId or document.originalEnvironmentReferenceAssetId or "")
    if not master_id:
        raise HTTPException(400, "Choose a master location image first.")
    state.masterAssetId = master_id
    if slot == "B" and not (state.viewA and state.viewA.approvedForSpatialReasoning):
        raise HTTPException(409, "Accept View A for Spatial Reasoning before generating View B.")
    if slot == "A" and state.inFlightSlot == "B":
        raise HTTPException(409, "View B is already running.")
    assert_can_start(db, project_id=project_id, state_in_flight=state.inFlightSlot, slot=slot)
    analysis = select_camera_role(
        scene_description=document.masterEnvironmentPrompt or "",
        slot=slot,
        accepted_role_a=state.viewA.cameraRole if state.viewA else None,
        remaining_unknown=list(state.confidence.unknown) if state.confidence else [],
    )
    role = analysis["cameraRole"]
    prompt = prompt_for_role(role, scene_description=document.masterEnvironmentPrompt or "")
    record = SpatialReferenceRecord(
        slot=slot,
        referenceRole=f"SUPPLEMENTARY_{role}",
        evidenceClass="INFERRED",
        source="QWEN_IMAGE_EDIT",
        cameraRole=role,
        sourceAssetId=master_id,
        generationEngine="qwen2512.ref",
        workflowKey="qwen2512.ref",
        prompt=prompt,
        status="GENERATING",
        approvedForSpatialReasoning=False,
        confidence=0.0,
    )
    e2e = os.environ.get("STUDIO_E2E", "").strip() in {"1", "true", "TRUE"} and e2e_asset_id
    if e2e:
        record.assetId = e2e_asset_id
        record.status = "VALIDATING"
        record = _validate_record(db, project_id, state, record)
    else:
        job = _enqueue(
            db,
            project_id,
            master_id,
            prompt,
            document.id,
            seed=random.randint(1, 2_147_483_646),
        )
        record.jobId = str(getattr(job, "id", "") or "")
        record.promptId = _job_prompt_id(job)
        record.timings = {"queuedAt": _now()}
        record.notGeometryEvidence = True
        state.inFlightSlot = slot
    if slot == "A":
        state.selectedRoleA = role
        state.viewA = record
    else:
        state.selectedRoleB = role
        state.viewB = record
    saved = _persist(db, document, state)
    return {"document": saved.model_dump(), "slot": slot, "view": record.model_dump(), "analysis": analysis}


def _validate_record(db: Session, project_id: str, state: SupplementaryState, record: SpatialReferenceRecord) -> SpatialReferenceRecord:
    master_path = _asset_path(db, project_id, state.masterAssetId)
    cand_path = _asset_path(db, project_id, record.assetId)
    prior = None
    if record.slot == "B" and state.viewA and state.viewA.assetId:
        prior_path = _asset_path(db, project_id, state.viewA.assetId)
        prior = str(prior_path) if prior_path else None
    if not master_path or not cand_path:
        record.status = "FAILED"
        record.gateVerdict = "FAIL"
        record.gateReasons = ["Generated file was missing."]
        return record
    gate = evaluate_view_gate(
        master_path=str(master_path),
        candidate_path=str(cand_path),
        camera_role=record.cameraRole or "",
        slot=record.slot if record.slot in {"A", "B"} else "A",
        prior_inferred_path=prior,
    )
    record.gateVerdict = gate["verdict"]
    record.gateReasons = list(gate.get("reasons") or [])
    if gate["verdict"] in {"FAIL", "FAIL_NO_INFORMATION_GAIN"}:
        record.status = "FAILED"
        record.approvedForSpatialReasoning = False
    else:
        record.status = "READY"
        record.confidence = 0.45 if gate["verdict"] == "PASS_WITH_LOW_CONFIDENCE" else 0.7
    return record


def refresh_job(db: Session, project_id: str, document_id: str) -> dict[str, Any]:
    document = get_document(db, project_id, document_id)
    state = _state_from_doc(document)
    for slot, rec in (("A", state.viewA), ("B", state.viewB)):
        if not rec or rec.status != "GENERATING" or not rec.jobId:
            continue
        from ...db import Job

        job = db.get(Job, rec.jobId)
        if job is None:
            continue
        if str(job.status) in {"completed", "done", "complete"}:
            rec.assetId = _job_output_asset_id(job) or rec.assetId
            rec.promptId = _job_prompt_id(job) or rec.promptId
            rec.timings = {**(rec.timings or {}), "completedAt": _now()}
            rec.status = "VALIDATING"
            rec = _validate_record(db, project_id, state, rec)
            state.inFlightSlot = None
            if slot == "A":
                state.viewA = rec
            else:
                state.viewB = rec
        elif str(job.status) in {"failed", "error", "cancelled"}:
            rec.status = "FAILED"
            rec.gateVerdict = "FAIL"
            rec.gateReasons = [str(getattr(job, "error", "") or "Generation failed.")]
            state.inFlightSlot = None
            if slot == "A":
                state.viewA = rec
            else:
                state.viewB = rec
    _persist(db, document, state)
    return get_state(db, project_id, document_id)


def accept_view(db: Session, project_id: str, document_id: str, slot: ViewSlot) -> dict[str, Any]:
    document = get_document(db, project_id, document_id)
    state = _state_from_doc(document)
    rec = state.viewA if slot == "A" else state.viewB
    if rec is None or rec.status != "READY":
        raise HTTPException(409, "That additional view is not ready to accept.")
    if rec.evidenceClass != "INFERRED":
        raise HTTPException(409, "Only inferred views can be accepted for spatial reasoning.")
    rec.approvedForSpatialReasoning = True
    rec.updatedAt = _now()
    if slot == "A":
        state.viewA = rec
    else:
        state.viewB = rec
    master = SpatialReferenceRecord(
        slot="MASTER",
        assetId=state.masterAssetId,
        evidenceClass="OBSERVED",
        source="USER",
        approvedForSpatialReasoning=True,
    )
    set_gate = evaluate_set_gate(master=master, view_a=state.viewA, view_b=state.viewB)
    state.setGateVerdict = set_gate["verdict"]
    state.setGateReasons = list(set_gate.get("reasons") or [])
    state.confidence = summarize_confidence(
        master=master,
        view_a=state.viewA,
        view_b=state.viewB,
        scene_description=document.masterEnvironmentPrompt or "",
    )
    _persist(db, document, state)
    return get_state(db, project_id, document_id)


def reject_view(db: Session, project_id: str, document_id: str, slot: ViewSlot) -> dict[str, Any]:
    document = get_document(db, project_id, document_id)
    state = _state_from_doc(document)
    rec = state.viewA if slot == "A" else state.viewB
    if rec is None:
        raise HTTPException(404, "There is no additional view to reject.")
    rec.status = "REJECTED"
    rec.approvedForSpatialReasoning = False
    rec.updatedAt = _now()
    if slot == "A":
        state.viewA = rec
        # Rejecting A does not destroy accepted B, but B is no longer sequenced from A.
    else:
        state.viewB = rec
    if state.inFlightSlot == slot:
        state.inFlightSlot = None
    _persist(db, document, state)
    return get_state(db, project_id, document_id)


def regenerate_view(db: Session, project_id: str, document_id: str, slot: ViewSlot) -> dict[str, Any]:
    document = get_document(db, project_id, document_id)
    state = _state_from_doc(document)
    if slot == "A":
        # Regenerating A must not destroy accepted B.
        kept_b = state.viewB
        state.viewA = None
        state.inFlightSlot = None
        _persist(db, document, state)
        result = generate_view(db, project_id, document_id, "A")
        document = get_document(db, project_id, document_id)
        state = _state_from_doc(document)
        state.viewB = kept_b
        _persist(db, document, state)
        return get_state(db, project_id, document_id)
    state.viewB = None
    state.inFlightSlot = None
    _persist(db, document, state)
    generate_view(db, project_id, document_id, "B")
    return get_state(db, project_id, document_id)


def write_contact_sheet(db: Session, project_id: str, document_id: str, output_dir: str | Path) -> dict[str, Any]:
    document = get_document(db, project_id, document_id)
    state = _state_from_doc(document)
    master = _asset_path(db, project_id, state.masterAssetId)
    if master is None:
        raise HTTPException(400, "Master image is missing.")
    out = Path(output_dir) / "supplementary_contact_sheet.png"
    result = strips.write_contact_sheet(
        master=master,
        view_a=_asset_path(db, project_id, state.viewA.assetId if state.viewA else ""),
        view_b=_asset_path(db, project_id, state.viewB.assetId if state.viewB else ""),
        output_path=out,
    )
    state.contactSheetAssetId = ""
    _persist(db, document, state)
    return result


def write_owner_review_strip(
    db: Session,
    project_id: str,
    document_id: str,
    output_dir: str | Path,
    *,
    atlas_path: str | Path | None = None,
) -> dict[str, Any]:
    document = get_document(db, project_id, document_id)
    state = _state_from_doc(document)
    master = _asset_path(db, project_id, state.masterAssetId)
    if master is None:
        raise HTTPException(400, "Master image is missing.")
    conf = state.confidence
    if isinstance(conf, dict):
        supported = list(conf.get("inferredSupported") or [])
        notes = list(conf.get("notes") or [])
    else:
        supported = list(conf.inferredSupported)
        notes = list(conf.notes)
    reasoning = " | ".join(supported[:2] or notes[:1])
    out = Path(output_dir) / "owner_review_strip.png"
    result = strips.write_owner_review_strip(
        master=master,
        view_a=_asset_path(db, project_id, state.viewA.assetId if state.viewA else ""),
        view_b=_asset_path(db, project_id, state.viewB.assetId if state.viewB else ""),
        atlas=Path(atlas_path) if atlas_path else None,
        output_path=out,
        reasoning=reasoning,
    )
    state.ownerReviewStripPath = result["path"]
    try:
        _persist(db, document, state)
    except Exception:
        pass
    return result
