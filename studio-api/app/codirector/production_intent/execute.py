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


def _is_h3_engine(engine: str) -> bool:
    token = (engine or "").strip().lower().replace("_", "-")
    return token in {"h3", "minimax", "minimax-h3"} or token.startswith("minimax-h3")


def _enqueue_standalone_video(db: Session, intent: ProductionIntent) -> dict[str, Any]:
    """Standalone Co-Director video — never Timeline render_scene / Scene-table lookup."""
    store = get_intent_store()
    store.save(intent)
    meta = dict(intent.metadata or {})
    if meta.get("forceEnqueueFailure"):
        raise IntentExecutionError(
            "Could not start the video generation job. Please retry.",
            code="force_enqueue_failure",
        )
    engine = str(intent.enginePreference or meta.get("engine") or "")
    if _is_h3_engine(engine):
        return _enqueue_h3_standalone(db, intent)

    params = to_studio_job_params(intent, {})
    params["standalone"] = True
    params["workspaceSceneId"] = intent.sceneId or meta.get("sceneId") or ""
    params["videoMode"] = meta.get("videoMode") or "t2v"
    params["creativeContext"] = {
        **(params.get("creativeContext") or {}),
        "executionId": meta.get("executionId") or "",
    }
    # TEXT-ONLY CONTRACT: standalone txt2vid is text-to-video. It must NOT
    # inherit a start frame / source image from Co-Director sourceAssets —
    # that is Image-to-Video (1 Frame / 3 Frame / render_scene), not T2V.
    # to_studio_job_params may have copied source asset ids; strip them so the
    # T2V compile path stays text-only.
    for _ref_key in ("start_asset_id", "source_asset_id", "reference_asset_ids", "referenceAssetIds"):
        params.pop(_ref_key, None)
    job = Job(
        id=str(uuid.uuid4()),
        project_id=intent.projectId,
        scene_id=None,
        kind="txt2vid",
        status="queued",
        progress=0.0,
        message="Standalone Co-Director video queued",
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
        workflow_key="standalone.txt2vid",
    )
    return {
        "ok": True,
        "intentId": intent.intentId,
        "jobId": job.id,
        "jobKind": job.kind,
        "status": "queued",
        "workflowKey": "standalone.txt2vid",
        "completed": False,
        "note": "Standalone video queued. Success only after the runtime finishes and the asset is registered.",
    }


def _enqueue_h3_standalone(db: Session, intent: ProductionIntent) -> dict[str, Any]:
    """Reconnect standalone H3 to the existing Route A service — not Timeline Scene render."""
    store = get_intent_store()
    meta = dict(intent.metadata or {})
    try:
        from ...minimax_h3.contracts import AdeptMiniMaxH3Request, H3ReferenceAssignment, H3TimelineContext
        from ...minimax_h3.service import create_job_or_block, prepare_plan, readiness
    except Exception as exc:
        raise IntentExecutionError(
            "MiniMax H3 is not available for standalone video.",
            code="h3_unavailable",
        ) from exc

    snap = readiness()
    if not snap.get("ready") and not snap.get("onDemand"):
        raise IntentExecutionError(
            str(snap.get("creatorStatus") or "MiniMax H3 is not ready. I will not switch to another generator."),
            code="h3_not_ready",
        )

    source = intent.sourceAssets[0] if intent.sourceAssets else ""
    mode = "one-frame" if source else "text-to-video"
    assignments = []
    if source:
        assignments.append(H3ReferenceAssignment(role="start", assetId=str(source), displayName="Start"))
    request = AdeptMiniMaxH3Request(
        projectId=intent.projectId,
        prompt=intent.prompt or "",
        sourceSurface="codirector",
        mode=mode,
        deployment="local_weights",
        durationSec=float(intent.duration or 5),
        referenceAssignments=assignments,
        timelineContext=H3TimelineContext(sceneId=intent.sceneId or meta.get("sceneId") or None),
        creatorNotes="standalone Co-Director video",
    )
    plan = prepare_plan(request)
    result = create_job_or_block(intent.projectId, plan.planId)
    if not result.get("ok") or not result.get("jobId"):
        raise IntentExecutionError(
            str(result.get("message") or "MiniMax H3 could not start. I will not switch to another generator."),
            code=str(result.get("status") or "h3_blocked"),
        )
    job_id = str(result["jobId"])
    store.update_state(
        intent.projectId,
        intent.intentId,
        execution_state="queued",
        approval_policy="approved",
        job_id=job_id,
        workflow_key="minimax-h3-route-a",
    )
    return {
        "ok": True,
        "intentId": intent.intentId,
        "jobId": job_id,
        "jobKind": "minimax-h3",
        "status": str(result.get("status") or "queued"),
        "workflowKey": "minimax-h3-route-a",
        "completed": False,
        "note": str(result.get("message") or "MiniMax H3 generation started."),
    }


def enqueue_intent(db: Session, intent: ProductionIntent) -> dict[str, Any]:
    """Enqueue studio job from approved intent. Returns job binding — does not fake success."""
    store = get_intent_store()
    store.save(intent)
    if (intent.metadata or {}).get("standalone") and intent.operation in {
        "video.generate",
        "video.three_frame",
    }:
        return _enqueue_standalone_video(db, intent)
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
    jobs = result.get("jobs") if isinstance(result.get("jobs"), list) else []
    first_job = jobs[0] if jobs and isinstance(jobs[0], dict) else {}
    job_id = result.get("jobId") or first_job.get("jobId")
    workflow_key = result.get("workflowKey") or first_job.get("workflowKey")
    store.update_state(
        intent.projectId,
        intent.intentId,
        execution_state="completed" if result.get("ok") else "failed",
        approval_policy="approved",
        job_id=str(job_id) if job_id else None,
        workflow_key=str(workflow_key) if workflow_key else None,
        metadata_patch={"result": result, "assetId": asset_id},
    )
    binding: dict[str, Any] = {
        "ok": bool(result.get("ok", True)),
        "intentId": intent.intentId,
        "result": result,
        "completed": bool(result.get("ok", True)),
    }
    # Image Product returns the job id inside its own payload. The tool
    # receipt and approval check read it from this binding, the same way
    # video enqueue does.
    if job_id:
        binding["jobId"] = job_id
    if workflow_key:
        binding["workflowKey"] = workflow_key
    if result.get("queued") or result.get("status"):
        binding["status"] = result.get("status") or "queued"
    return binding


def _place_asset(db: Session, intent: ProductionIntent) -> dict[str, Any]:
    """Place a durable asset on the Director Timeline.

    ORDER19: Visual assets (image/video) land on image_clips / video_clips.
    Audio kinds keep m29 AudioService.place_cue (music/ambience HOLD).
    """
    asset_id = intent.sourceAssets[0] if intent.sourceAssets else None
    if not asset_id:
        raise IntentExecutionError("editor.place requires sourceAssets[0]", code="missing_asset")
    placement = intent.targetPlacement or {}
    scene_id = intent.sceneId or placement.get("sceneId")
    start_sec = float(placement.get("startSec") or 0)
    duration_sec = float(placement.get("durationSec") or intent.duration or 2.0)
    track = str(placement.get("track") or placement.get("kind") or "").strip().lower()

    asset_kind = ""
    try:
        from ...db import Asset

        row = db.get(Asset, str(asset_id))
        if row is not None:
            asset_kind = str(getattr(row, "kind", "") or "").strip().lower()
    except Exception:
        asset_kind = ""

    audio_kinds = {"audio", "music", "sfx", "voice", "ambience", "dialogue", "sound"}
    audio_tracks = {"dialogue", "music", "sfx", "ambience"}
    if not track:
        if asset_kind in audio_kinds:
            track = "dialogue" if asset_kind in {"audio", "voice", "dialogue"} else asset_kind
        else:
            track = "video"

    want_audio = track in audio_tracks or asset_kind in audio_kinds
    if want_audio and track != "video":
        try:
            from ..m29.audio.service import AudioService

            out = AudioService.place_cue(
                db,
                project_id=intent.projectId,
                kind=str(track or "dialogue"),
                asset_id=asset_id,
                scene_id=scene_id,
                start_sec=start_sec,
                duration_sec=duration_sec,
            )
            return {"ok": True, "assetId": asset_id, "placement": out, "destination": "audio_cue"}
        except Exception as exc:
            return {
                "ok": False,
                "assetId": asset_id,
                "error": str(exc),
                "note": "Placement adapter unavailable — no silent success.",
            }

    if not scene_id:
        raise IntentExecutionError(
            "editor.place visual requires sceneId (targetPlacement.sceneId or intent.sceneId)",
            code="missing_scene",
        )
    try:
        from ...db import Scene
        from ...director_timeline_w46.contracts import BatchClip
        from ...director_timeline_w46.service import load_timeline_bundle
        from ...director_timeline_w46 import store as timeline_store

        scene = db.get(Scene, str(scene_id))
        if scene is None or str(scene.project_id) != str(intent.projectId):
            raise IntentExecutionError(
                f"Scene not found for editor.place: {scene_id}",
                code="scene_not_found",
            )
        bundle = load_timeline_bundle(db, str(intent.projectId), str(scene_id))
        if not bundle.get("ok"):
            raise IntentExecutionError(
                f"Scene timeline not found for editor.place: {scene_id}",
                code="scene_not_found",
            )
        master = bundle["master"]
        duration = float(getattr(scene, "duration_sec", None) or 5.0)
        existing = []
        for batch in getattr(master, "batchBlocks", None) or []:
            existing.extend(getattr(batch, "visualClips", None) or [])
        length = max(0.1, min(float(duration_sec), duration))
        start = max(0.0, float(start_sec))
        is_video = asset_kind == "video"
        if start_sec == 0 and existing:
            start = max(
                (float(getattr(c, "start", 0) or 0) + float(getattr(c, "length", 0) or 0) for c in existing),
                default=0.0,
            )
        clip = BatchClip(
            kind="video" if is_video else "image",
            assetId=str(asset_id),
            start=start,
            length=min(2.0, length) if (not is_video and duration_sec == 2.0) else length,
            label=str(placement.get("label") or ("Video" if is_video else f"Image {len(existing) + 1}")),
            role=None if is_video else "guide",
        )
        blocks = sorted(
            list(getattr(master, "batchBlocks", None) or []),
            key=lambda b: int(getattr(b, "order", 0) or 0),
        )
        if not blocks:
            raise IntentExecutionError(
                "Timeline Master has no execution windows yet. Rematerialize windows before placing a clip.",
                code="no_windows",
            )
        cursor = 0.0
        target = blocks[0]
        for batch in blocks:
            dur = getattr(batch, "duration", None)
            planned = max(0.1, float(getattr(dur, "plannedDuration", None) or 0.0))
            end = cursor + planned
            if start + 1e-6 >= cursor and start < end - 1e-9:
                target = batch
                break
            cursor = end
            target = batch
        target.visualClips = list(getattr(target, "visualClips", None) or []) + [clip]
        timeline_store.save_master(db, str(intent.projectId), str(scene_id), master, bump_revision=True)
        dest = "visualClips"
        return {
            "ok": True,
            "assetId": asset_id,
            "sceneId": scene_id,
            "destination": dest,
            "clipId": clip.id,
            "start": clip.start,
            "length": clip.length,
            "placement": {"track": track or "video", "destination": dest, "clipId": clip.id},
        }
    except IntentExecutionError:
        raise
    except Exception as exc:
        return {
            "ok": False,
            "assetId": asset_id,
            "error": str(exc),
            "note": "Visual placement adapter unavailable — no silent success.",
        }



def _voice_generate(db: Session, intent: ProductionIntent) -> dict[str, Any]:
    from ...character_identity.models import CharacterProfileRow, VoiceProfileRow
    from ...character_identity.schemas import DialogueGenerateRequest
    from ...character_identity.voice_runtime import qwen_speech_compatible, run_generate_dialogue

    text = (intent.prompt or "").strip()
    if not text:
        raise IntentExecutionError("voice.generate needs spoken text.", code="missing_prompt")
    meta = intent.metadata or {}
    character_id = str(meta.get("characterId") or meta.get("character_id") or "").strip()
    if not character_id:
        raise IntentExecutionError(
            "voice.generate needs a character so it can use that character's approved voice. It did not invent a generic speaker.",
            code="voice_identity_required",
        )
    profile = db.get(CharacterProfileRow, character_id)
    if not profile or str(profile.project_id) != str(intent.projectId):
        raise IntentExecutionError("Character not found in this project.", code="character_not_found")
    voice_id = str(profile.active_voice_profile_id or meta.get("voiceProfileId") or meta.get("voice_profile_id") or "").strip()
    if not voice_id:
        raise IntentExecutionError("This character has no approved voice yet.", code="voice_identity_required")
    voice = db.get(VoiceProfileRow, voice_id)
    if not voice or str(voice.project_id) != str(intent.projectId) or str(voice.character_profile_id) != character_id:
        raise IntentExecutionError("This character has no approved voice yet.", code="voice_identity_required")
    if (voice.approval_status or "").lower() != "approved":
        raise IntentExecutionError("This character has no approved voice yet.", code="voice_identity_required")
    if not qwen_speech_compatible(voice):
        raise IntentExecutionError(
            "This character's approved voice is not on the shared local Qwen worker, so Co-Director did not switch to another speaker.",
            code="engine_incompatible",
        )
    try:
        out = run_generate_dialogue(
            db,
            intent.projectId,
            character_id,
            voice.id,
            DialogueGenerateRequest(text=text, language="en", allow_kokoro_fallback=False),
        )
    except Exception as exc:
        recovery = classify_failure(exc)
        raise IntentExecutionError(str(exc), code=recovery.diagnosticCode, recovery=recovery) from exc
    return {
        "ok": True,
        "assetId": out.get("assetId"),
        "engine": out.get("engine") or "qwen3-tts",
        "warmWorker": bool(out.get("warmWorker")),
        "voiceProfileId": out.get("voiceProfileId") or voice.id,
        "path": out.get("path"),
    }


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
            "lockModelFamily": bool(meta.get("lockModelFamily")),
            "seed": meta.get("seed"),
            "width": meta.get("width"),
            "height": meta.get("height"),
            "refs": meta.get("refs") or list(intent.references or []),
            "codirectorConversation": bool(meta.get("codirectorConversation")),
        }
        if intent.sourceAssets and intent.operation != "image.edit":
            # The stored reference is the canonical asset. Do not copy it
            # into this project. The existing reference compiler binds it.
            body["sourceAssetId"] = intent.sourceAssets[0]
            body["referenceImage"] = intent.sourceAssets[0]
            body["referenceAssetIds"] = [str(asset_id) for asset_id in intent.sourceAssets if asset_id]
            # Certified reference stills use this purpose. A free-text purpose
            # such as "Cinematic shot" would otherwise be treated as an edit.
            body["purpose"] = "codirector_image_generate"
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
