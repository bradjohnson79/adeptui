"""Timeline Master service façade."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from . import orchestrator, store
from .camera_catalog import camera_catalog_payload
from .capabilities import list_generators, registry_snapshot, validate_duration
from .contracts import BatchBlock, CancelRequest, DurationState, SceneTimelineMaster, TimelinePromptSegment, _now
from .migration import compute_config_fingerprint, load_or_migrate_scene_master


def _overlay_live_queue_progress(db: Session, master: SceneTimelineMaster, progress: dict[str, Any]) -> dict[str, Any]:
    """Prefer the live Studio job row. Percent only when Comfy reported a real step."""
    if str(progress.get("sceneStatus") or "").lower() not in {"generating", "queued", "waiting"}:
        return progress
    batches = sorted(master.batchBlocks or [], key=lambda b: int(getattr(b, "order", 0) or 0))
    idx = int(progress.get("currentBatchIndex") or 1) - 1
    if idx < 0 or idx >= len(batches):
        return progress
    jobs = [
        j
        for j in (batches[idx].generationJobs or [])
        if str(getattr(j, "status", "") or "").lower() in {"queued", "running", "pending"}
    ]
    pick = jobs[-1] if jobs else None
    qid = str(getattr(pick, "queueJobId", None) or "").strip() if pick is not None else ""
    if not qid:
        return progress
    try:
        from ..db import Job
        from ..video_runtime.progress_telemetry import (
            comfy_step_fraction,
            format_render_status_line,
            is_grounded_progress_message,
            telemetry_from_job_row,
        )

        row = db.get(Job, qid)
        if row is None:
            return progress
        tel = telemetry_from_job_row(row)
        row_message = str(getattr(row, "message", "") or "")
        step = comfy_step_fraction(row_message)
        grounded = bool(tel.get("progressGrounded")) or is_grounded_progress_message(row_message)
        pct = max(0.0, min(1.0, float(getattr(row, "progress", 0.0) or 0.0)))
        if step is not None:
            grounded = True
            pct = max(0.0, min(1.0, step[0] / step[1]))
        elif not grounded:
            stored = tel.get("progress")
            if stored is not None:
                pct = max(0.0, min(1.0, float(stored)))
            else:
                pct = 0.0
    except Exception:
        return progress
    progress["batchProgress"] = pct if grounded else 0.0
    progress["progressGrounded"] = grounded
    progress["comfyMessage"] = row_message
    progress["phase"] = tel.get("phase") or progress.get("phase")
    progress["phaseLabel"] = tel.get("phaseLabel")
    progress["lastProgressAt"] = tel.get("lastProgressAt")
    progress["lastRuntimeEventAt"] = tel.get("lastRuntimeEventAt")
    progress["elapsedActiveTime"] = tel.get("elapsedActiveTime")
    progress["stalled"] = bool(tel.get("stalled"))
    progress["currentNode"] = tel.get("currentNode")
    progress["stallLabel"] = tel.get("stallLabel")
    n = progress.get("currentBatchIndex")
    m = progress.get("totalBatches")
    label = progress.get("renderingTakeLabel")
    line = format_render_status_line(
        batch_index=int(n or 1),
        total_batches=int(m or 1),
        take_label=label,
        scene_status=str(progress.get("sceneStatus") or "generating"),
        progress=pct,
        progress_grounded=grounded,
        phase=progress.get("phase"),
        phase_label=progress.get("phaseLabel"),
        stalled=bool(progress.get("stalled")),
        last_runtime_event_at=progress.get("lastRuntimeEventAt"),
        elapsed_active_time=progress.get("elapsedActiveTime"),
        gpu_active=progress.get("gpuActive"),
        message=row_message,
    )
    progress["message"] = line.split("\n", 1)[0]
    extra = [ln for ln in line.split("\n")[1:] if ln]
    progress["statusLines"] = [progress["message"], *extra] + [
        ln
        for ln in (progress.get("statusLines") or [])
        if not str(ln).startswith("Render Batch ")
        and not str(ln).startswith("Rendering ")
        and not str(ln).startswith("Queued")
        and not str(ln).startswith("Preparing")
        and not str(ln).startswith("Generating")
        and not str(ln).startswith("Generation may be stalled")
        and not str(ln).startswith("Last activity:")
        and not str(ln).startswith("Last runtime event:")
        and not str(ln).startswith("Elapsed:")
        and not str(ln).startswith("Runtime active")
        and not str(ln).startswith("GPU active")
        and " — Batch " not in str(ln)
    ]
    return progress


def set_library_asset_ids(db: Session, project_id: str, scene_id: str, asset_ids: list[str]) -> dict[str, Any]:
    return store.set_library_asset_ids(db, project_id, scene_id, asset_ids)


def workspace(db: Session, project_id: str, scene_id: str) -> dict[str, Any]:
    result = store.load_master(db, project_id, scene_id)
    if not result.get("ok"):
        return result
    # P6 bounce recovery: derive terminals from durable Jobs — never leave Generating forever.
    try:
        from .generation.timeline_reconciler import reconcile_scene

        rec = reconcile_scene(db, project_id, scene_id)
        if rec.get("reconciled"):
            result = store.load_master(db, project_id, scene_id)
            if not result.get("ok"):
                return result
    except Exception:
        pass
    try:
        master = SceneTimelineMaster.model_validate(result["master"])
        from .current_take import stamp_current_take_fields
        from .current_take import compute_generation_progress

        from .scene_takes import adopt_legacy_retakes, ensure_scene_takes

        from .scene_takes import close_previous_session_render

        changed = ensure_scene_takes(master)
        # SINGLE-STORE: adopt_legacy_retakes reads Master batch.visualClips.
        changed = adopt_legacy_retakes(master) or changed
        changed = close_previous_session_render(master) or changed
        if changed:
            store.save_master(db, project_id, scene_id, master, touch_batches=False)
        try:
            from .orchestrator import submit_next_queued_batch

            chain = submit_next_queued_batch(db, project_id, scene_id)
            if chain.get("submitted"):
                reloaded = store.load_master(db, project_id, scene_id)
                if reloaded.get("ok"):
                    master = SceneTimelineMaster.model_validate(reloaded["master"])
        except Exception:
            pass
        for batch in master.batchBlocks:
            stamp_current_take_fields(batch, master)
        result["master"] = master.model_dump()
        progress = compute_generation_progress(master)
        progress = _overlay_live_queue_progress(db, master, progress)
    except Exception:
        progress = {
            "currentBatchIndex": 0,
            "totalBatches": 0,
            "currentBatchId": None,
            "batchStatus": "idle",
            "batchProgress": 0.0,
            "sceneStatus": "idle",
            "message": "No batches",
        }
    result["generationProgress"] = progress
    if isinstance(result.get("master"), dict):
        result["master"]["generationProgress"] = progress
    scene = store.get_scene(db, project_id, scene_id)
    if scene:
        workspace_state = store.extract_timeline_workspace(scene.director_json)
        result["libraryAssetIds"] = list(workspace_state.get("libraryAssetIds") or [])
    return result


def load_timeline_bundle(db: Session, project_id: str, scene_id: str) -> dict[str, Any]:
    scene = store.get_scene(db, project_id, scene_id)
    if not scene:
        return {"ok": False, "error": "SCENE_NOT_FOUND", "mock": False}
    master, _director_tl, _data = load_or_migrate_scene_master(
        scene.director_json,
        scene_id=scene_id,
        fallback_duration=float(scene.duration_sec or 5.0),
        fallback_prompt=scene.prompt or "",
    )
    from ..lipsync_tracks import parse_lipsync_tracks
    from .scene_takes import adopt_legacy_retakes, ensure_scene_takes

    changed = ensure_scene_takes(master)
    # SINGLE-STORE: adopt_legacy_retakes reads Master batch.visualClips.
    changed = adopt_legacy_retakes(master) or changed
    if changed:
        store.save_master(db, project_id, scene_id, master, touch_batches=False)
    workspace_state = store.extract_timeline_workspace(scene.director_json)
    return {
        "ok": True,
        "projectId": project_id,
        "sceneId": scene_id,
        "master": master,
        "workspace": workspace_state,
        "playhead": float(workspace_state.get("playhead") or 0.0),
        "lipsyncTracks": parse_lipsync_tracks(getattr(scene, "lipsync_tracks_json", None)),
        "mock": False,
    }


def put_master(db: Session, project_id: str, scene_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return store.replace_master(db, project_id, scene_id, payload)


def patch_scene_metadata(db: Session, project_id: str, scene_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    return store.patch_scene_metadata(db, project_id, scene_id, patch)


def _mint_if_window_topology_changed(prev_master, master, *, reason: str):
    """Systems P5: batch window CRUD changes execution topology → new stk_."""
    from .scene_takes import enforce_execution_boundary_if_topology_changed

    return enforce_execution_boundary_if_topology_changed(prev_master, master, reason=reason)



def dismiss_failure(db: Session, project_id: str, scene_id: str, job_id: str) -> dict[str, Any]:
    """Creator acknowledgment of a terminal failure: record the job id on the
    master so the Preview Monitor stops pinning the scene to that failure.
    Idempotent; the job row and batch status are deliberately untouched, and the
    save does not touch batch updatedAt provenance (touch_batches=False)."""
    from ..db import Job  # deferred: service is imported by modules that must not cycle

    job_id = (job_id or "").strip()
    if not job_id:
        return {"ok": False, "error": "JOB_ID_REQUIRED", "mock": False}
    job = (
        db.query(Job)
        .filter(Job.id == job_id, Job.project_id == project_id, Job.scene_id == scene_id)
        .one_or_none()
    )
    if job is None:
        return {"ok": False, "error": "JOB_NOT_FOUND", "mock": False}
    if job.status != "failed":
        return {"ok": False, "error": "JOB_NOT_FAILED", "mock": False}
    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return payload
    master = SceneTimelineMaster.model_validate(payload["master"])
    if job_id not in master.dismissedFailureJobIds:
        master.dismissedFailureJobIds.append(job_id)
        store.save_master(db, project_id, scene_id, master, touch_batches=False)
    return {
        "ok": True,
        "projectId": project_id,
        "sceneId": scene_id,
        "master": master.model_dump(),
        "mock": False,
    }


def add_batch(
    db: Session,
    project_id: str,
    scene_id: str,
    *,
    label: str | None = None,
    planned_duration: float | None = None,
    generator_id: str | None = None,
    at_order: int | None = None,
) -> dict[str, Any]:
    """Creator path gated — Execution Windows are CD-plan driven."""
    from .execution_window_materialize import creator_batch_mutation_blocked

    return creator_batch_mutation_blocked("add_batch")


def duplicate_batch(db: Session, project_id: str, scene_id: str, batch_id: str) -> dict[str, Any]:
    """Creator path gated — Execution Windows are CD-plan driven."""
    from .execution_window_materialize import creator_batch_mutation_blocked

    return creator_batch_mutation_blocked("duplicate_batch")


def delete_batch(db: Session, project_id: str, scene_id: str, batch_id: str) -> dict[str, Any]:
    """Creator path gated — Execution Windows are CD-plan driven."""
    from .execution_window_materialize import creator_batch_mutation_blocked

    return creator_batch_mutation_blocked("delete_batch")



def rematerialize_execution_windows(
    db: Session,
    project_id: str,
    scene_id: str,
    *,
    windows: Any | None = None,
    plan: Any | None = None,
    spec: Any | None = None,
    generator_id: str | None = None,
    duration_seconds: float | None = None,
    allow_scene_take_id: str | None = None,
    allow_revision: int | None = None,
    previous_scene_take_id: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Rematerialize master.batchBlocks from CD execution window plan.

    Systems P5: when topology/generator switch requires new take, caller must
    first put_master/replace_master (mints new stk_ + executionRevision), then
    pass allow_scene_take_id == response currentSceneTakeId (NEW).
    """
    from .execution_window_materialize import rematerialize_batch_blocks_from_plan

    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return payload
    master = SceneTimelineMaster.model_validate(payload["master"])
    scene = store.get_scene(db, project_id, scene_id)
    dur = duration_seconds
    gid = generator_id or master.sceneGeneratorId
    if dur is None and scene is not None:
        dur = float(scene.duration_sec or 0.0) or None
    result = rematerialize_batch_blocks_from_plan(
        master,
        windows=windows,
        plan=plan,
        spec=spec,
        generator_id=gid,
        scene_id=scene_id,
        duration_seconds=dur,
        allow_scene_take_id=allow_scene_take_id,
        allow_revision=allow_revision,
        previous_scene_take_id=previous_scene_take_id,
        force=force,
    )
    if not result.get("ok"):
        return result
    store.save_master(db, project_id, scene_id, master)
    out = {
        **result,
        "projectId": project_id,
        "sceneId": scene_id,
        "master": master.model_dump(),
        "mock": False,
    }
    for key in ("currentSceneTakeId", "activeSceneTakeId"):
        if hasattr(master, key):
            out[key] = getattr(master, key)
    return out


def patch_batch(db: Session, project_id: str, scene_id: str, batch_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    return orchestrator.touch_batch_config(db, project_id, scene_id, batch_id, patch)


def stitch_scene(db: Session, project_id: str, scene_id: str) -> dict[str, Any]:
    from .scene_stitch import stitch_scene as _stitch_scene

    return _stitch_scene(db, project_id, scene_id)


def set_mode(db: Session, project_id: str, scene_id: str, mode: str) -> dict[str, Any]:
    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return payload
    master = SceneTimelineMaster.model_validate(payload["master"])
    if mode not in ("image_planning", "video_finishing"):
        return {"ok": False, "error": "INVALID_MODE", "mock": False}
    # Mode switch must not discard Batch state
    master.mode = mode  # type: ignore[assignment]
    store.save_master(db, project_id, scene_id, master)
    return {"ok": True, "mode": master.mode, "batchCount": len(master.batchBlocks), "mock": False}


def generators() -> dict[str, Any]:
    # CAPABILITY_DRIVEN_GENERATOR_MENU: besides the capability registry
    # snapshot, expose the registered Timeline adapter capabilities so UI
    # dropdowns render from the registry instead of hardcoded option lists
    # (audit DEFECT-W3). Additive — existing "generators" payload unchanged.
    from .generation.registry import get_registry

    payload = registry_snapshot()
    payload["timelineAdapters"] = [
        c.model_dump() for c in get_registry().list_capabilities()
    ]
    return payload


def camera_catalog() -> dict[str, Any]:
    return {**camera_catalog_payload(), "mock": False}


def duration_check(generator_id: str | None, planned: float) -> dict[str, Any]:
    return {**validate_duration(generator_id, planned), "mock": False}


def snapshot_get(db: Session, project_id: str, scene_id: str, snapshot_id: str) -> dict[str, Any]:
    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return payload
    master = SceneTimelineMaster.model_validate(payload["master"])
    snap = master.executionSnapshots.get(snapshot_id)
    if not snap:
        return {"ok": False, "error": "SNAPSHOT_NOT_FOUND", "mock": False}
    return {"ok": True, "snapshot": snap.model_dump(), "immutable": True, "mock": False}


def final_check_decision(
    db: Session,
    project_id: str,
    scene_id: str,
    decision: str,
    *,
    runtime_kind: str | None = None,
) -> dict[str, Any]:
    """Apply API/local Final Check repair gate decision. Persist on master.sceneFinalCheck."""
    from .contracts import SceneFinalCheck, SceneFinalCheckRepairGate
    from .scene_final_check import (
        apply_api_repair_decision,
        apply_local_auto_repair,
        classify_runtime_kind,
        open_final_check_after_stitch,
        repair_gate_for_runtime,
    )

    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return payload
    master = SceneTimelineMaster.model_validate(payload["master"])
    gid = getattr(master, "sceneGeneratorId", None)
    if not gid and master.batchBlocks:
        gid = getattr(master.batchBlocks[0], "generatorId", None)
    classified: str = runtime_kind or classify_runtime_kind(generator_id=gid)
    if master.sceneFinalCheck is None:
        state = open_final_check_after_stitch(
            master, runtime_kind=classified, generator_id=gid  # type: ignore[arg-type]
        )
        master.sceneFinalCheck = SceneFinalCheck.model_validate(state)
    fc = master.sceneFinalCheck
    gate = fc.repairGate.model_dump() if fc.repairGate else {
        "runtimeKind": classified,
        "permission": "required" if classified == "api" else "not_required",
        "apiCallCount": 0,
    }
    # Reconcile misclassified gate (e.g. H3 local previously stuck as api ask-once).
    if str(gate.get("runtimeKind") or "") != classified:
        corrected = repair_gate_for_runtime(
            classified,  # type: ignore[arg-type]
            has_auto_eligible=int(getattr(fc, "autoRepairEligibleCount", 0) or 0) > 0,
        )
        corrected["apiCallCount"] = int(gate.get("apiCallCount") or 0)
        corrected["apiCallsDelta"] = int(gate.get("apiCallsDelta") or 0)
        gate = corrected
        fc.repairGate = SceneFinalCheckRepairGate.model_validate(gate)
        master.sceneFinalCheck = fc
    retake_plan = None
    if decision == "auto_retake" or (gate.get("runtimeKind") == "local" and decision in ("repair_automatically", "auto_retake")):
        updated = apply_local_auto_repair(gate)
        # Live hookup: attach PRESERVE pack as dialogueRetakeRepair (ONE retake stack).
        try:
            from .scene_final_check import (
                apply_planned_local_auto_repair_to_final_check,
                execute_local_auto_retakes,
                plan_local_auto_repair_from_final_check,
            )

            # Ensure fc has latest gate before planning.
            fc.repairGate = SceneFinalCheckRepairGate.model_validate(updated)
            fc.lifecycleStatus = str(updated.get("lifecycleStatus") or "REPAIRING")
            master.sceneFinalCheck = fc
            retake_plan = plan_local_auto_repair_from_final_check(master)
            if retake_plan.get("shouldAutoRetake") or retake_plan.get("cleanupFailed"):
                applied = apply_planned_local_auto_repair_to_final_check(master, retake_plan)
                store.save_master(db, project_id, scene_id, master, touch_batches=False)
                fired = execute_local_auto_retakes(db, project_id, scene_id, master, plan=retake_plan)
                fc = master.sceneFinalCheck
                updated = (fc.repairGate.model_dump() if fc.repairGate else updated)
                retake_plan = {**(retake_plan or {}), "applied": applied, "autoRetakes": fired}
        except Exception:
            retake_plan = {"error": "auto_repair_attach_failed"}
    else:
        updated = apply_api_repair_decision(gate, decision)  # type: ignore[arg-type]
    if updated.get("lifecycleStatus"):
        fc.lifecycleStatus = str(updated["lifecycleStatus"])
    if updated.get("creatorVerdict"):
        fc.creatorVerdict = str(updated["creatorVerdict"])
    if updated.get("lifecycleStatus") in ("SCENE_FINISHED", "SCENE_FINISHED_WITH_ACCEPTED_ISSUES"):
        from .contracts import _now

        fc.closedAt = _now()
        fc.unresolvedBlocking = False
    elif updated.get("lifecycleStatus") == "SCENE_NOT_FINISHED":
        fc.unresolvedBlocking = True
    fc.repairGate = SceneFinalCheckRepairGate.model_validate(updated)
    # Decline / dismiss: apiCallCount unchanged (delta 0).
    if decision in ("decline", "dismiss", "keep_current"):
        prev = int(gate.get("apiCallCount") or 0)
        fc.repairGate.apiCallCount = prev
        fc.repairGate.apiCallsDelta = 0
    master.sceneFinalCheck = fc
    store.save_master(db, project_id, scene_id, master, touch_batches=False)
    return {
        "ok": True,
        "decision": decision,
        "sceneFinalCheck": fc.model_dump(),
        "master": master.model_dump(),
        "apiCallCount": fc.repairGate.apiCallCount if fc.repairGate else 0,
        "apiCallsDelta": fc.repairGate.apiCallsDelta if fc.repairGate else 0,
        "retakePlan": retake_plan,
        "mock": False,
    }


def open_or_refresh_final_check(db: Session, project_id: str, scene_id: str) -> dict[str, Any]:
    from .contracts import SceneFinalCheck
    from .scene_final_check import open_final_check_after_stitch

    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return payload
    master = SceneTimelineMaster.model_validate(payload["master"])
    state = open_final_check_after_stitch(master, generator_id=getattr(master, "sceneGeneratorId", None))
    master.sceneFinalCheck = SceneFinalCheck.model_validate(state)
    store.save_master(db, project_id, scene_id, master, touch_batches=False)
    return {"ok": True, "sceneFinalCheck": master.sceneFinalCheck.model_dump(), "master": master.model_dump(), "mock": False}


def publish_scene(
    db: Session,
    project_id: str,
    scene_id: str,
    *,
    update: bool = False,
    expected_version: int | None = None,
    source: str = "stitch",
) -> dict[str, Any]:
    from .scene_publish import publish_scene as _publish_scene

    return _publish_scene(
        db,
        project_id,
        scene_id,
        update=update,
        expected_version=expected_version,
        source=source,
    )


def magi_upscale_full_stitch(
    db: Session,
    project_id: str,
    scene_id: str,
    *,
    engine: str = "ffmpeg-scale",
    model: str = "lanczos",
    target_resolution: str = "",
    asset_id: str | None = None,
) -> dict[str, Any]:
    from .scene_publish import magi_upscale_full_stitch as _magi

    return _magi(
        db,
        project_id,
        scene_id,
        engine=engine,
        model=model,
        target_resolution=target_resolution,
        asset_id=asset_id,
    )


def magi_upscale_options(
    db: Session,
    project_id: str,
    scene_id: str,
    *,
    asset_id: str | None = None,
) -> dict[str, Any]:
    from .scene_publish import magi_upscale_options as _opts

    return _opts(db, project_id, scene_id, asset_id=asset_id)
