"""Execute ProductionIntent via WorkflowResolver → studio Job (never builders)."""

from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session

from ...db import Job
from .approval import build_disclosure, evaluate_approval_requirement
from .bridge import studio_job_kind_for, to_resolver_request, to_studio_job_params
from .recovery import classify_failure
from .schemas import ProductionIntent
from .store import get_intent_store


class IntentExecutionError(RuntimeError):
    def __init__(self, message: str, *, code: str = "intent_execution_failed", recovery: Any = None):
        super().__init__(message)
        self.code = code
        self.recovery = recovery


def _resolve_contract(intent: ProductionIntent) -> dict[str, Any]:
    from ...video_runtime.workflow_resolver import resolve_workflow, resolve_from_scene_params

    req = to_resolver_request(intent)
    ri = str(req.get("intent") or "")
    present = {
        "start_asset_id": req.get("startAssetId"),
        "middle_asset_id": req.get("middleAssetId"),
        "end_asset_id": req.get("endAssetId"),
        "audio_asset_id": (intent.metadata or {}).get("audioAssetId"),
    }
    engine = str(req.get("engine") or "minimax-h3")

    if intent.operation == "video.lipsync" or ri == "lipsync":
        contract = resolve_workflow("lipsync", engine=engine, present_inputs=present)
    elif intent.operation == "video.extend" or ri == "extend":
        contract = resolve_workflow("extend", engine=engine, present_inputs=present)
    elif intent.operation == "video.timeline_render" or ri == "timeline_render":
        contract = resolve_workflow("timeline_render", engine=engine, present_inputs=present)
    elif intent.operation == "video.batch_timeline" or ri == "batch_timeline":
        contract = resolve_workflow("batch_timeline", engine=engine, present_inputs=present)
    elif intent.operation == "video.shot_render" or ri == "shot_render":
        contract = resolve_from_scene_params(
            engine=engine,
            start_asset_id=present.get("start_asset_id"),
            middle_asset_id=present.get("middle_asset_id"),
            end_asset_id=present.get("end_asset_id"),
            audio_asset_id=present.get("audio_asset_id"),
            wants_ingredients=bool((intent.metadata or {}).get("ingredients")),
            intent="shot_render",
        )
    elif intent.operation in {"video.generate", "video.scene_render", "video.three_frame"}:
        contract = resolve_from_scene_params(
            engine=engine,
            start_asset_id=present.get("start_asset_id"),
            middle_asset_id=present.get("middle_asset_id"),
            end_asset_id=present.get("end_asset_id"),
            audio_asset_id=present.get("audio_asset_id"),
            wants_ingredients=bool((intent.metadata or {}).get("ingredients")),
            intent="scene_render",
        )
    else:
        raise IntentExecutionError(
            f"Operation {intent.operation} has no video resolver intent (non-video adapter).",
            code="non_video_operation",
        )
    return contract.to_dict() if hasattr(contract, "to_dict") else dict(contract)


def preflight_intent(intent: ProductionIntent) -> dict[str, Any]:
    """Resolve + approval disclosure without enqueue."""
    store = get_intent_store()
    store.save(intent)
    approval = evaluate_approval_requirement(intent)
    result: dict[str, Any] = {
        "intentId": intent.intentId,
        "operation": intent.operation,
        "approval": {
            "state": approval.state,
            "required": approval.required,
            "reasons": approval.reasons,
            "disclosure": approval.disclosure,
        },
    }
    if intent.modality == "video" and intent.operation.startswith("video."):
        try:
            contract = _resolve_contract(intent)
            if str(contract.get("status") or "").lower() in {"blocked", "deferred"}:
                recovery = classify_failure(
                    "workflow blocked",
                    context={"code": "workflow_blocked"},
                )
                raise IntentExecutionError(
                    f"Workflow not executable: {contract.get('workflow_key')}",
                    code="workflow_blocked",
                    recovery=recovery,
                )
            intent = store.update_state(
                intent.projectId,
                intent.intentId,
                execution_state="awaiting_approval" if approval.required else "ready",
                approval_policy=approval.state,
                workflow_key=contract.get("workflow_key") or contract.get("workflowKey"),
                workflow_id=contract.get("workflow_id") or contract.get("workflowId"),
                workflow_version=contract.get("workflow_version")
                or contract.get("workflowVersion"),
            ) or intent
            result["contract"] = {
                "workflowId": contract.get("workflow_id") or contract.get("workflowId"),
                "workflowKey": contract.get("workflow_key") or contract.get("workflowKey"),
                "workflowVersion": contract.get("workflow_version")
                or contract.get("workflowVersion"),
                "provider": contract.get("provider_kind") or contract.get("provider"),
                "status": contract.get("status"),
                "requiredInputs": contract.get("required_inputs") or contract.get("requiredInputs"),
                "cancellationPolicy": contract.get("cancellation_policy")
                or contract.get("cancellationPolicy"),
            }
            result["approval"]["disclosure"] = build_disclosure(
                intent, reasons=approval.reasons, contract=contract
            )
        except IntentExecutionError:
            raise
        except Exception as exc:
            recovery = classify_failure(exc)
            raise IntentExecutionError(str(exc), code=recovery.diagnosticCode, recovery=recovery) from exc
    else:
        store.update_state(
            intent.projectId,
            intent.intentId,
            execution_state="awaiting_approval" if approval.required else "ready",
            approval_policy=approval.state,
        )
    return result


def enqueue_intent(db: Session, intent: ProductionIntent) -> dict[str, Any]:
    """Enqueue studio job from approved intent. Returns job binding — does not fake success."""
    store = get_intent_store()
    store.save(intent)
    kind = studio_job_kind_for(intent.operation)
    if kind is None and intent.operation.startswith("video."):
        raise IntentExecutionError(
            f"No studio job kind for {intent.operation}",
            code="unsupported_operation",
        )

    contract: dict[str, Any] = {}
    if intent.modality == "video" and intent.operation.startswith("video."):
        # Production Dock preference → engine + early degraded-mode block.
        try:
            from ...production_control.runtime_map import apply_video_dock_preference
            from fastapi import HTTPException

            dock = apply_video_dock_preference(
                intent.projectId, engine_hint=getattr(intent, "enginePreference", None)
            )
            if dock.get("engine") and not getattr(intent, "enginePreference", None):
                intent.enginePreference = str(dock["engine"])
            meta = dict(intent.metadata or {})
            meta["productionDock"] = dock
            meta["preferenceProvenance"] = dock.get("provenance")
            intent.metadata = meta
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
            raise IntentExecutionError(
                str(detail.get("message") or "No executable video route"),
                code=str(detail.get("code") or "NO_EXECUTABLE_ROUTE"),
            ) from exc
        except Exception:
            pass
        contract = _resolve_contract(intent)
        status = str(contract.get("status") or "").lower()
        if status in {"blocked", "deferred"}:
            recovery = classify_failure("workflow blocked", context={"code": "workflow_blocked"})
            raise IntentExecutionError(
                f"Refusing uncertified/blocked workflow: {contract.get('workflow_key')}",
                code="workflow_blocked",
                recovery=recovery,
            )

    if intent.operation in {
        "music.generate",
        "sfx.generate",
        "image.generate",
        "image.edit",
        "voice.generate",
        "subtitle.generate",
        "editor.place",
        "job.cancel",
        "job.retry",
    }:
        return _enqueue_non_video(db, intent)

    params = to_studio_job_params(intent, contract)
    job = Job(
        id=str(uuid.uuid4()),
        project_id=intent.projectId,
        scene_id=intent.sceneId,
        kind=kind or "render_scene",
        status="queued",
        progress=0.0,
        message=f"W6P {intent.operation} via certified contract",
        params_json=json.dumps(params),
    )
    db.add(job)
    db.commit()
    try:
        from ..executive.imagegen_adapter import schedule_job_queue_enqueue

        schedule_job_queue_enqueue(job.id)
    except Exception:
        pass

    store.update_state(
        intent.projectId,
        intent.intentId,
        execution_state="queued",
        approval_policy="approved",
        job_id=job.id,
        workflow_key=contract.get("workflow_key") or contract.get("workflowKey"),
        workflow_id=contract.get("workflow_id") or contract.get("workflowId"),
        workflow_version=contract.get("workflow_version") or contract.get("workflowVersion"),
        certification_record_id=contract.get("certificationRecordId")
        or (contract.get("fingerprint_expected") or {}).get("certification_record_id"),
    )
    return {
        "ok": True,
        "intentId": intent.intentId,
        "jobId": job.id,
        "jobKind": job.kind,
        "status": "queued",
        "workflowKey": contract.get("workflow_key") or contract.get("workflowKey"),
        "completed": False,
        "note": "Job queued. Success only after Output Gate + asset registration.",
    }


def _enqueue_non_video(db: Session, intent: ProductionIntent) -> dict[str, Any]:
    from ...generation_tools import ops
    from .store import get_intent_store

    store = get_intent_store()
    if intent.operation == "music.generate":
        result = ops.run_audio_generate(
            db,
            project_id=intent.projectId,
            kind="music",
            prompt=intent.prompt or "music",
            duration_sec=float(intent.duration or 4),
        )
    elif intent.operation == "sfx.generate":
        result = ops.run_audio_generate(
            db,
            project_id=intent.projectId,
            kind="sfx",
            prompt=intent.prompt or "sfx",
            duration_sec=float(intent.duration or 2),
        )
    elif intent.operation == "video.extend":
        # Should be handled as video — keep safety net
        source = intent.sourceAssets[0] if intent.sourceAssets else ""
        result = ops.run_video_extend(
            db,
            project_id=intent.projectId,
            source_asset_id=source,
            prompt=intent.prompt,
            duration_sec=float(intent.duration or 2),
        )
    elif intent.operation == "job.cancel":
        job_id = (intent.metadata or {}).get("jobId") or intent.jobId
        if not job_id:
            raise IntentExecutionError("job.cancel requires metadata.jobId", code="missing_job_id")
        job = db.get(Job, str(job_id))
        if job is None:
            raise IntentExecutionError("Job not found", code="job_not_found")
        # Mark cancel requested; QueueWorker deep-cancel path owns runtime halt confirmation.
        job.status = "cancel_requested"
        job.message = "Cancel requested via ProductionIntent job.cancel"
        db.commit()
        try:
            from ...main import job_queue  # type: ignore

            if job_queue is not None and hasattr(job_queue, "cancel_and_halt"):
                import asyncio

                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(job_queue.cancel_and_halt(str(job_id)))
                else:
                    loop.run_until_complete(job_queue.cancel_and_halt(str(job_id)))
        except Exception:
            pass
        store.update_state(
            intent.projectId,
            intent.intentId,
            execution_state="cancelling",
            job_id=str(job_id),
        )
        return {
            "ok": True,
            "intentId": intent.intentId,
            "jobId": job_id,
            "status": "cancelling",
            "note": "cancel_requested → cancelling → runtime stop confirmed → cancelled",
        }
    elif intent.operation == "job.retry":
        parent = (intent.metadata or {}).get("parentIntentId") or intent.parentIntentId
        if not parent:
            raise IntentExecutionError("job.retry requires parentIntentId", code="missing_parent")
        parent_intent = store.get(intent.projectId, str(parent))
        if parent_intent is None:
            raise IntentExecutionError("Parent intent not found", code="parent_not_found")
        parent_intent.intentId = intent.intentId
        parent_intent.parentIntentId = str(parent)
        parent_intent.executionState = "draft"
        return enqueue_intent(db, parent_intent)
    elif intent.operation == "editor.place":
        result = _place_asset(db, intent)
    elif intent.operation == "voice.generate":
        result = _voice_generate(db, intent)
    elif intent.operation == "subtitle.generate":
        result = _subtitle_generate(db, intent)
    elif intent.operation in {"image.generate", "image.edit"}:
        result = _image_generate(db, intent)
    else:
        raise IntentExecutionError(
            f"Unsupported non-video operation: {intent.operation}",
            code="unsupported_operation",
        )

    asset_id = result.get("assetId") or result.get("asset_id")
    store.update_state(
        intent.projectId,
        intent.intentId,
        execution_state="completed" if result.get("ok") else "failed",
        approval_policy="approved",
        metadata_patch={"result": result, "assetId": asset_id},
    )
    return {
        "ok": bool(result.get("ok", True)),
        "intentId": intent.intentId,
        "result": result,
        "completed": bool(result.get("ok", True)),
    }


def _place_asset(db: Session, intent: ProductionIntent) -> dict[str, Any]:
    asset_id = intent.sourceAssets[0] if intent.sourceAssets else None
    if not asset_id:
        raise IntentExecutionError("editor.place requires sourceAssets[0]", code="missing_asset")
    placement = intent.targetPlacement or {}
    try:
        from ..m29.audio.service import AudioService

        out = AudioService.place_cue(
            db,
            project_id=intent.projectId,
            kind=str(placement.get("track") or placement.get("kind") or "dialogue"),
            asset_id=asset_id,
            scene_id=intent.sceneId or placement.get("sceneId"),
            start_sec=float(placement.get("startSec") or 0),
            duration_sec=float(placement.get("durationSec") or intent.duration or 2.0),
        )
        return {"ok": True, "assetId": asset_id, "placement": out}
    except Exception as exc:
        return {
            "ok": False,
            "assetId": asset_id,
            "error": str(exc),
            "note": "Placement adapter unavailable — no silent success.",
        }


def _voice_generate(db: Session, intent: ProductionIntent) -> dict[str, Any]:
    try:
        from ..m210b.adapters.kokoro import generate_voice

        return generate_voice(
            db,
            project_id=intent.projectId,
            text=intent.prompt,
            character_id=(intent.metadata or {}).get("characterId"),
        )
    except Exception as exc:
        recovery = classify_failure(exc)
        raise IntentExecutionError(str(exc), code=recovery.diagnosticCode, recovery=recovery) from exc


def _subtitle_generate(db: Session, intent: ProductionIntent) -> dict[str, Any]:
    # Minimal durable subtitle sidecar — no fake A/V sync claim
    from pathlib import Path

    text = intent.prompt or ""
    if not text:
        raise IntentExecutionError("subtitle.generate requires prompt/transcript", code="missing_input")
    out_dir = Path(__file__).resolve().parents[4] / "data" / "assets" / intent.projectId
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"subtitles_{intent.intentId[:8]}.vtt"
    path.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:05.000\n" + text[:500] + "\n", encoding="utf-8")
    try:
        from ...generation_tools.lineage import register_derived_asset

        asset = register_derived_asset(
            db,
            project_id=intent.projectId,
            source_path=path,
            kind="subtitle",
            tag="subtitle_generate",
            parent_asset_id=intent.sourceAssets[0] if intent.sourceAssets else None,
            op="subtitle.generate",
        )
        return {"ok": True, "assetId": asset.id, "path": str(path)}
    except Exception:
        return {"ok": True, "assetId": None, "path": str(path), "registered": False}


def _image_generate(db: Session, intent: ProductionIntent) -> dict[str, Any]:
    try:
        from ...image_product.service import generate_images

        meta = intent.metadata or {}
        creative = None
        if intent.creativeContext is not None:
            creative = (
                intent.creativeContext.model_dump()
                if hasattr(intent.creativeContext, "model_dump")
                else dict(intent.creativeContext)
            )
        body: dict[str, Any] = {
            "prompt": intent.prompt or intent.objective or "image",
            "purpose": meta.get("purpose") or "stills",
            "operation": intent.operation or "image.generate",
            "modelFamilyPreference": intent.enginePreference
            or meta.get("modelFamilyPreference")
            or "zimage",
            "presetId": meta.get("presetId"),
            "productionIntentId": intent.intentId,
            "acceptedPrompt": meta.get("acceptedPrompt"),
            "useExpandedPrompt": meta.get("acceptExpandedPrompt", meta.get("useExpandedPrompt", True)),
            "sceneId": intent.sceneId or meta.get("sceneId"),
            "creativeContext": creative or meta.get("creativeContext"),
            "aspectRatio": meta.get("aspectRatio") or intent.aspectRatio or meta.get("aspect"),
            "resolution": meta.get("resolution"),
            "quality": meta.get("quality") or intent.qualityProfile,
            "seed": meta.get("seed"),
            "width": meta.get("width"),
            "height": meta.get("height"),
            "refs": meta.get("refs") or list(intent.references or []),
        }
        if intent.operation == "image.edit" and intent.sourceAssets:
            body["operation"] = "image.edit"
            body["sourceAssetId"] = intent.sourceAssets[0]
            body["edit_op"] = str(meta.get("editOp") or "edit")
        return generate_images(db, project_id=intent.projectId, body=body)
    except Exception as exc:
        recovery = classify_failure(exc)
        raise IntentExecutionError(
            f"Image generation failed (no stub fallback): {exc}",
            code=recovery.diagnosticCode,
            recovery=recovery,
        ) from exc
