"""Scene Batch Orchestrator — cancel/resume boundaries, partial failure, snapshots."""

from __future__ import annotations

from typing import Any, Literal

from sqlalchemy.orm import Session

from ..director_timeline import DirectorTimeline, parse_director_timeline
from .camera_catalog import detect_camera_contradictions, summarize_camera_strategy
from .capabilities import disclose_inpaint_strategy, get_generator, validate_duration
from .contracts import (
    ApprovedClip,
    BatchBlock,
    CancelAction,
    CancelRequest,
    CancelResult,
    CandidateVersion,
    DurationState,
    ExecutionSnapshot,
    GenerationJobRef,
    HostedCancelSupport,
    RepairRange,
    SceneTimelineMaster,
    _now,
)
from .migration import compute_config_fingerprint
from .repair_policy import apply_repair_overlap_policy
from . import store


def _batch_map(master: SceneTimelineMaster) -> dict[str, BatchBlock]:
    return {b.id: b for b in master.batchBlocks}


def _load_director_timeline(
    db: Session | None,
    project_id: str | None,
    scene_id: str | None,
) -> DirectorTimeline | None:
    if not db or not project_id or not scene_id:
        return None
    scene = store.get_scene(db, project_id, scene_id)
    if not scene:
        return None
    return parse_director_timeline(
        scene.director_json,
        fallback_duration=float(scene.duration_sec or 5.0),
        fallback_prompt=scene.prompt or "",
    )


def create_execution_snapshot(
    batch: BatchBlock,
    *,
    continuity: dict[str, Any] | None = None,
    guidance_priority: str | None = None,
    camera_clips: list[Any] | None = None,
    prompt_intelligence: dict[str, Any] | None = None,
) -> ExecutionSnapshot:
    settings: dict[str, Any] = {"label": batch.label, "order": batch.order}
    if guidance_priority:
        settings["guidancePriority"] = guidance_priority
    if camera_clips:
        settings["cameraStrategy"] = summarize_camera_strategy(camera_clips)
    pi = prompt_intelligence if isinstance(prompt_intelligence, dict) else None
    segments = [
        {
            "id": p.id,
            "text": (
                str((pi or {}).get("finalProviderPrompt") or p.text)
                if pi and idx == 0
                else p.text
            ),
            "start": p.start,
            "length": p.length,
            "strategy": p.executionStrategy,
            "versionId": p.versionId,
        }
        for idx, p in enumerate(batch.promptSegments)
    ]
    compiled: dict[str, Any] = {"segments": segments}
    if pi and pi.get("finalProviderPrompt"):
        compiled["finalProviderPrompt"] = pi.get("finalProviderPrompt")
        compiled["creatorPrompt"] = pi.get("creatorPrompt") or pi.get("originalPrompt")
    return ExecutionSnapshot(
        batchBlockId=batch.id,
        compiledPrompts=compiled,
        promptLayerVersionIds=[p.versionId for p in batch.promptSegments],
        references=list(batch.references),
        selectedGenerator=batch.generatorId,
        capabilityStrategy="dock_resolver",
        settings=settings,
        runtime=None,
        providerId=None,
        duration=batch.duration.model_copy(),
        sourceAnchors=[a.model_dump() for a in batch.sourceAnchors],
        continuityState=dict(continuity or {}),
        promptIntelligence=dict(pi) if isinstance(pi, dict) else None,
    )


def _resolve_guidance_priority(
    guidance_priority: str | None,
    db: Session | None = None,
    project_id: str | None = None,
    scene_id: str | None = None,
) -> str | None:
    if guidance_priority:
        return guidance_priority
    if db and project_id and scene_id:
        from . import store

        scene = store.get_scene(db, project_id, scene_id)
        if scene:
            ws = store.extract_timeline_workspace(scene.director_json)
            return str(ws.get("guidancePriority") or "") or None
    return None


def _load_prompt_intelligence_record(
    db: Session | None,
    project_id: str,
    scene_id: str,
) -> dict[str, Any] | None:
    try:
        scene_row = store.get_scene(db, project_id, scene_id) if db else None
        if scene_row and scene_row.director_json:
            import json as _json

            raw_dj = scene_row.director_json
            dj = _json.loads(raw_dj) if isinstance(raw_dj, str) else (raw_dj or {})
            if isinstance(dj, dict) and isinstance(dj.get("promptIntelligence"), dict):
                return dj["promptIntelligence"]
    except Exception:
        pass
    return None


def _prepare_and_store_snapshot(
    db: Session,
    project_id: str,
    scene_id: str,
    master: SceneTimelineMaster,
    batch: BatchBlock,
    *,
    continuity: dict[str, Any] | None = None,
    guidance_priority: str | None = None,
) -> ExecutionSnapshot:
    """Create + store an immutable ExecutionSnapshot for a batch.

    Shared by submit_batch_generation (submit now) and sequential staging
    (snapshot READY, provider submission deferred). Never mutates prior
    snapshots.
    """
    from .generation.registry import get_registry

    gen = get_generator(batch.generatorId)
    adapter = get_registry().get(batch.generatorId)
    locality: Literal["local", "hosted"] = (
        "hosted" if adapter.capabilities.executionType == "api" else "local"
    )
    if gen is not None:
        locality = gen.locality
    resolved_guidance = _resolve_guidance_priority(guidance_priority, db, project_id, scene_id)
    director_timeline = _load_director_timeline(db, project_id, scene_id)
    pi_record = _load_prompt_intelligence_record(db, project_id, scene_id)
    snap = create_execution_snapshot(
        batch,
        continuity=continuity,
        guidance_priority=resolved_guidance,
        camera_clips=(director_timeline.camera_clips if director_timeline else None),
        prompt_intelligence=pi_record,
    )
    snap.runtime = locality
    snap.providerId = gen.providerId if gen else adapter.capabilities.id
    snap.selectedGenerator = adapter.id
    # Immutability: store once; never update later
    master.executionSnapshots[snap.id] = snap
    return snap


def submit_batch_generation(
    db: Session,
    project_id: str,
    scene_id: str,
    batch_id: str,
    *,
    continuity: dict[str, Any] | None = None,
    guidance_priority: str | None = None,
    fallback_allowed: bool = False,
    precreated_snapshot_id: str | None = None,
) -> dict[str, Any]:
    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return payload
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = _batch_map(master).get(batch_id)
    if not batch:
        return {"ok": False, "error": "BATCH_NOT_FOUND", "mock": False}

    if not batch.generatorId:
        return {
            "ok": False,
            "error": "GENERATOR_REQUIRED",
            "message": "Select a generator for this Batch — no silent default substitution.",
            "mock": False,
        }

    # PROVIDER_CAPABILITY_GATING: reject Timeline generation for providers
    # whose capabilities report supportsTimelineGeneration=False (e.g. WAN /
    # Hunyuan until a Timeline adapter is registered). This makes future
    # activation a capability flip, not a UI hardcode change.
    from .capabilities import list_generators

    cap = next((g for g in list_generators() if g.id == batch.generatorId), None)
    if cap and not cap.supportsTimelineGeneration:
        return {
            "ok": False,
            "error": "GENERATOR_UNSUPPORTED_FOR_TIMELINE",
            "message": f"{cap.label} does not support Timeline batch generation yet.",
            "mock": False,
        }

    # Provider-agnostic path: resolve adapter before any enqueue.
    from .generation.registry import GeneratorNotFoundError, get_registry
    from .generation.request_builder import build_timeline_generation_request
    from .generation.watcher import start_completion_watcher

    registry = get_registry()
    try:
        adapter = registry.get(batch.generatorId)
    except GeneratorNotFoundError as exc:
        return {"ok": False, "error": "GENERATOR_UNKNOWN", "message": str(exc), "mock": False}

    dur_check = validate_duration(batch.generatorId, batch.duration.plannedDuration)
    if not dur_check.get("ok") and dur_check.get("action") == "choose":
        return {"ok": False, "error": "DURATION_EXCEEDS_GENERATOR", **dur_check, "mock": False}

    gen = get_generator(batch.generatorId)
    locality: Literal["local", "hosted"] = (
        "hosted" if adapter.capabilities.executionType == "api" else "local"
    )
    if gen is not None:
        locality = gen.locality
    if precreated_snapshot_id:
        # SEQUENTIAL_SUBMISSION_CHAIN: reuse the snapshot staged at Generate
        # Scene time. Snapshot identity is preserved — no new snapshot.
        snap = master.executionSnapshots.get(precreated_snapshot_id)
        if not snap or snap.batchBlockId != batch.id or not snap.immutable:
            return {"ok": False, "error": "SNAPSHOT_NOT_FOUND", "mock": False}
    else:
        snap = _prepare_and_store_snapshot(
            db,
            project_id,
            scene_id,
            master,
            batch,
            continuity=continuity,
            guidance_priority=guidance_priority,
        )

    try:
        request = build_timeline_generation_request(
            project_id=project_id,
            scene_id=scene_id,
            batch=batch,
            snapshot=snap,
            fallback_allowed=fallback_allowed,
        )
    except Exception as exc:
        return {"ok": False, "error": "REQUEST_BUILD_FAILED", "message": str(exc), "mock": False}

    # Hard lock: never silently change generator
    if request.generatorId != adapter.id:
        return {
            "ok": False,
            "error": "GENERATOR_MISMATCH",
            "message": "Resolved generator does not match adapter — refusing silent substitution.",
            "mock": False,
        }
    if not fallback_allowed and request.fallbackAllowed:
        return {
            "ok": False,
            "error": "FALLBACK_NOT_AUTHORIZED",
            "message": "Generator fallback requires explicit authorization.",
            "mock": False,
        }

    validation = adapter.validate(request)
    if not validation.ok:
        return {
            "ok": False,
            "error": "CAPABILITY_VALIDATION_FAILED",
            "errors": validation.errors,
            "warnings": validation.warnings,
            "generatorId": adapter.id,
            "mock": False,
        }

    try:
        submission = adapter.submit(request)
    except Exception as exc:
        return {
            "ok": False,
            "error": "ADAPTER_SUBMIT_FAILED",
            "message": str(exc),
            "generatorId": adapter.id,
            "mock": False,
        }

    # Bind projectId for MiniMax status polling
    meta = dict(submission.providerMetadata or {})
    meta["projectId"] = project_id
    submission.providerMetadata = meta

    hosted_cancel: HostedCancelSupport = "unsupported" if locality == "hosted" else "supported"

    job = GenerationJobRef(
        executionSnapshotId=snap.id,
        status=submission.status,
        locality=locality,
        hostedCancelSupport=hosted_cancel,
        queueJobId=submission.queueJobId,
        providerJobId=submission.providerJobId,
        generatorId=adapter.id,
        apiUsed=submission.apiUsed,
        progress=0.0,
    )
    batch.generationJobs.append(job)
    batch.status = "Generating"
    batch.pendingSnapshotId = None
    batch.configFingerprint = compute_config_fingerprint(batch)
    store.save_master(db, project_id, scene_id, master)

    start_completion_watcher(
        project_id=project_id,
        scene_id=scene_id,
        batch_id=batch.id,
        execution_snapshot_id=snap.id,
        submission=submission,
    )

    return {
        "ok": True,
        "batchBlockId": batch.id,
        "job": job.model_dump(),
        "executionSnapshotId": snap.id,
        "generatorId": adapter.id,
        "queueJobId": submission.queueJobId,
        "providerJobId": submission.providerJobId,
        "internalJobId": submission.internalJobId,
        "apiUsed": submission.apiUsed,
        "normalizedRequest": request.model_dump(),
        "hostedCancelSupport": hosted_cancel,
        "message": (
            f"Job submitted via {adapter.id} adapter with immutable execution snapshot."
        ),
        "mock": False,
    }


def complete_batch_candidate(
    db: Session,
    project_id: str,
    scene_id: str,
    batch_id: str,
    *,
    asset_id: str,
    generated_duration: float,
    execution_snapshot_id: str,
) -> dict[str, Any]:
    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return payload
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = _batch_map(master).get(batch_id)
    if not batch:
        return {"ok": False, "error": "BATCH_NOT_FOUND", "mock": False}
    snap = master.executionSnapshots.get(execution_snapshot_id)
    if not snap:
        return {"ok": False, "error": "SNAPSHOT_NOT_FOUND", "mock": False}
    if not snap.immutable:
        return {"ok": False, "error": "SNAPSHOT_NOT_IMMUTABLE", "mock": False}

    cand = CandidateVersion(
        executionSnapshotId=execution_snapshot_id,
        assetId=asset_id,
        label=f"Candidate {len(batch.candidateVersions) + 1}",
        generatedDuration=generated_duration,
    )
    batch.candidateVersions.append(cand)
    batch.duration.generatedDuration = generated_duration
    batch.duration.sourceMediaDuration = generated_duration
    # Visible duration: min(planned, generated) — no silent stretch
    batch.duration.timelineVisibleDuration = min(batch.duration.plannedDuration, generated_duration)
    batch.status = "CandidateReady"
    for job in batch.generationJobs:
        if job.executionSnapshotId == execution_snapshot_id:
            job.status = "completed"
    store.save_master(db, project_id, scene_id, master)
    return {
        "ok": True,
        "candidate": cand.model_dump(),
        "duration": batch.duration.model_dump(),
        "provenance": {
            "executionSnapshotId": snap.id,
            "generator": snap.selectedGenerator,
            "providerId": snap.providerId,
            "runtime": snap.runtime,
        },
        "mock": False,
    }


def approve_candidate(
    db: Session,
    project_id: str,
    scene_id: str,
    batch_id: str,
    candidate_id: str,
) -> dict[str, Any]:
    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return payload
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = _batch_map(master).get(batch_id)
    if not batch:
        return {"ok": False, "error": "BATCH_NOT_FOUND", "mock": False}
    cand = next((c for c in batch.candidateVersions if c.id == candidate_id), None)
    if not cand or not cand.assetId:
        return {"ok": False, "error": "CANDIDATE_NOT_FOUND", "mock": False}
    for c in batch.candidateVersions:
        c.approved = c.id == candidate_id
    batch.approvedClip = ApprovedClip(
        assetId=cand.assetId,
        executionSnapshotId=cand.executionSnapshotId,
        candidateId=cand.id,
    )
    batch.status = "Approved"
    batch.configFingerprint = compute_config_fingerprint(batch)
    store.save_master(db, project_id, scene_id, master)
    # APPROVE_PLACES_ON_TIMELINE: approval through any path (HTTP endpoint,
    # adapter auto-approve, watcher) must place the approved clip onto the
    # Director timeline. Idempotent upsert by stable bbclip_ id.
    from .generation.completion import place_approved_batches_on_timeline

    placement = place_approved_batches_on_timeline(db, project_id, scene_id)
    # SEQUENTIAL_SUBMISSION_CHAIN: Approved is a terminal state — free the
    # provider slot for the next Queued batch (no-op when none queued).
    chain = submit_next_queued_batch(db, project_id, scene_id)
    return {"ok": True, "approvedClip": batch.approvedClip.model_dump(), "batchStatus": batch.status, "placement": placement, "sequentialChain": chain, "mock": False}


def touch_batch_config(
    db: Session,
    project_id: str,
    scene_id: str,
    batch_id: str,
    patch: dict[str, Any],
) -> dict[str, Any]:
    """Apply config edits; invalidate approval when fingerprint changes after approve."""
    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return payload
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = _batch_map(master).get(batch_id)
    if not batch:
        return {"ok": False, "error": "BATCH_NOT_FOUND", "mock": False}

    prior_fp = batch.configFingerprint
    had_approval = batch.approvedClip is not None and batch.status in (
        "Approved",
        "ApprovedConfigurationChanged",
        "RegenerationRecommended",
    )

    if "label" in patch:
        batch.label = str(patch["label"])
    if "generatorId" in patch:
        batch.generatorId = patch["generatorId"]
        batch.generatorOverride = True
    if "plannedDuration" in patch:
        batch.duration.plannedDuration = float(patch["plannedDuration"])
    if "promptSegments" in patch and isinstance(patch["promptSegments"], list):
        from .contracts import TimelinePromptSegment

        batch.promptSegments = [TimelinePromptSegment.model_validate(p) for p in patch["promptSegments"]]
    if "sourceAnchors" in patch and isinstance(patch["sourceAnchors"], list):
        from .contracts import TimelineVisualAnchor

        batch.sourceAnchors = [TimelineVisualAnchor.model_validate(a) for a in patch["sourceAnchors"]]
    if "references" in patch and isinstance(patch["references"], list):
        batch.references = list(patch["references"])
    if "repairRanges" in patch and isinstance(patch["repairRanges"], list):
        next_ranges: list[RepairRange] = []
        for raw in patch["repairRanges"]:
            repair = RepairRange.model_validate(raw)
            strategy = disclose_inpaint_strategy(batch.generatorId, repair.inPaintStrategy)
            repair.inPaintStrategy = strategy["strategy"]  # type: ignore[assignment]
            next_ranges.append(repair)
        batch.repairRanges = next_ranges
    # Per-batch owned clip arrays (BATCH_OWNED_CLIPS). Replacing one batch's
    # clip array never touches another batch's clips.
    from .contracts import BatchClip

    for _field in ("visualClips", "audioClips", "sfxClips", "cameraInstructions"):
        if _field in patch and isinstance(patch[_field], list):
            setattr(
                batch,
                _field,
                [BatchClip.model_validate(c) for c in patch[_field]],
            )

    new_fp = compute_config_fingerprint(batch)
    batch.configFingerprint = new_fp
    invalidated = False
    if had_approval and prior_fp and new_fp != prior_fp:
        batch.status = "ApprovedConfigurationChanged"
        invalidated = True
        # Prior approved clip remains playable
        if batch.approvedClip:
            batch.approvedClip.playable = True

    # STAGED_SNAPSHOT_INVALIDATION: a Queued batch's staged ExecutionSnapshot
    # was built from the pre-edit config. When the fingerprint changes, that
    # staged snapshot is stale provenance (lineage would claim config A while
    # the provider runs config B). Detach it — the immutable record stays in
    # executionSnapshots as audit — and return the batch to Ready so the next
    # Generate Scene re-stages a fresh snapshot with the current config.
    staged_snapshot_staled = False
    if (
        batch.status == "Queued"
        and batch.pendingSnapshotId
        and prior_fp
        and new_fp != prior_fp
    ):
        batch.pendingSnapshotId = None
        batch.status = "Ready"
        staged_snapshot_staled = True

    store.save_master(db, project_id, scene_id, master)
    return {
        "ok": True,
        "batch": batch.model_dump(),
        "invalidated": invalidated,
        "stagedSnapshotStaled": staged_snapshot_staled,
        "status": batch.status,
        "message": (
            "Approved — Configuration Changed. Regeneration Recommended. Prior clip remains playable from older snapshot."
            if invalidated
            else (
                "Batch updated. Queued staging was reset because the configuration changed — use Generate Scene to re-queue with the new settings."
                if staged_snapshot_staled
                else "Batch updated."
            )
        ),
        "mock": False,
    }


def add_clip_to_batch(
    db: Session,
    project_id: str,
    scene_id: str,
    batch_id: str,
    clip_data: dict[str, Any],
) -> dict[str, Any]:
    """Append a single clip to a specific batch's owned clip array.

    BATCH_OWNED_CLIPS: only the target batch is mutated; no other batch's
    clips are touched. The clip gets a stable unique id.
    """
    from .contracts import BatchClip

    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return payload
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = _batch_map(master).get(batch_id)
    if not batch:
        return {"ok": False, "error": "BATCH_NOT_FOUND", "mock": False}

    clip = BatchClip.model_validate(clip_data)
    if not clip.id:
        from .contracts import _nid

        clip.id = _nid("clip_")
    kind = clip.kind
    if kind == "image" or kind == "video":
        batch.visualClips.append(clip)
    elif kind == "audio":
        batch.audioClips.append(clip)
    elif kind == "sfx":
        batch.sfxClips.append(clip)
    elif kind == "camera":
        batch.cameraInstructions.append(clip)
    else:
        return {"ok": False, "error": "UNKNOWN_CLIP_KIND", "mock": False}

    batch.configFingerprint = compute_config_fingerprint(batch)
    store.save_master(db, project_id, scene_id, master)
    return {"ok": True, "batch": batch.model_dump(), "clip": clip.model_dump(), "mock": False}


def cancel_scene(db: Session, project_id: str, scene_id: str, body: CancelRequest) -> CancelResult:
    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return CancelResult(ok=False, action=body.action, message="Scene not found")
    master = SceneTimelineMaster.model_validate(payload["master"])
    targets = body.batchBlockIds or [b.id for b in master.batchBlocks]
    affected: list[str] = []
    preserved: list[str] = []
    hosted: HostedCancelSupport = "unknown"

    for batch in master.batchBlocks:
        if batch.id not in targets and body.action != "stop_remaining_scene_jobs":
            continue
        if batch.status in ("Approved", "CandidateReady") and body.action in (
            "stop_remaining_scene_jobs",
            "preserve_completed_batches",
            "resume_incomplete_only",
            "cancel_pending_batch",
        ):
            preserved.append(batch.id)
            continue

        if body.action == "cancel_pending_batch":
            if batch.status in ("Draft", "Ready", "Queued"):
                batch.status = "Cancelled"
                batch.pendingSnapshotId = None
                affected.append(batch.id)
        elif body.action == "cancel_active_local_job":
            for job in batch.generationJobs:
                if job.status in ("queued", "running") and job.locality == "local":
                    job.status = "cancelled"
                    hosted = "supported"
            if batch.status == "Generating":
                batch.status = "Cancelled"
                batch.pendingSnapshotId = None
                affected.append(batch.id)
        elif body.action == "request_hosted_cancellation":
            for job in batch.generationJobs:
                if job.status in ("queued", "running") and job.locality == "hosted":
                    job.hostedCancelSupport = "unsupported"
                    job.error = "Hosted cancellation unsupported for this provider"
                    hosted = "unsupported"
            affected.append(batch.id)
        elif body.action == "stop_remaining_scene_jobs":
            if batch.status in ("Queued", "Generating", "Ready", "Draft"):
                batch.status = "Cancelled"
                batch.pendingSnapshotId = None
                for job in batch.generationJobs:
                    if job.status in ("queued", "running"):
                        job.status = "cancelled"
                affected.append(batch.id)
            else:
                preserved.append(batch.id)
        elif body.action == "resume_incomplete_only":
            if batch.status in ("Cancelled", "Failed"):
                batch.status = "Ready"
                affected.append(batch.id)
            elif batch.status in ("Approved", "CandidateReady"):
                preserved.append(batch.id)

    store.save_master(db, project_id, scene_id, master)
    msg = {
        "cancel_pending_batch": "Pending batches cancelled.",
        "cancel_active_local_job": "Local jobs cancel requested.",
        "request_hosted_cancellation": "Hosted cancellation unsupported — labelled honestly.",
        "stop_remaining_scene_jobs": "Remaining scene jobs stopped; completed batches preserved.",
        "preserve_completed_batches": "Completed batches preserved.",
        "resume_incomplete_only": "Resume targeted incomplete batches only.",
    }.get(body.action, "Cancel processed.")
    return CancelResult(
        ok=True,
        action=body.action,
        affectedBatchIds=affected,
        preservedCompletedBatchIds=list(dict.fromkeys(preserved)),
        hostedCancelSupport=hosted,
        message=msg,
        mock=False,
    )


def add_repair_range(
    db: Session,
    project_id: str,
    scene_id: str,
    batch_id: str,
    range_payload: dict[str, Any],
    *,
    policy: str | None = None,
) -> dict[str, Any]:
    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return payload
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = _batch_map(master).get(batch_id)
    if not batch:
        return {"ok": False, "error": "BATCH_NOT_FOUND", "mock": False}
    incoming = RepairRange.model_validate(range_payload)
    strategy = disclose_inpaint_strategy(batch.generatorId, incoming.inPaintStrategy)
    incoming.inPaintStrategy = strategy["strategy"]  # type: ignore[assignment]
    use_policy = policy or master.repairOverlapPolicy
    decision = apply_repair_overlap_policy(batch.repairRanges, incoming, policy=use_policy)  # type: ignore[arg-type]
    if not decision.ok:
        return {**decision.model_dump(), "mock": False}
    batch.repairRanges = decision.ranges
    store.save_master(db, project_id, scene_id, master)
    return {**decision.model_dump(), "inPaintDisclosure": strategy, "mock": False}


def run_preflight(
    master: SceneTimelineMaster,
    *,
    director_timeline: DirectorTimeline | None = None,
) -> list[dict[str, Any]]:
    from .contracts import PreflightFinding
    from .store import OPTIONAL_REFS_POLICY_NOTE

    findings: list[PreflightFinding] = []
    for batch in master.batchBlocks:
        if not batch.promptSegments or not any(p.text.strip() for p in batch.promptSegments):
            findings.append(
                PreflightFinding(
                    severity="warning",
                    code="missing_prompt",
                    message=f"{batch.label} has no prompt text.",
                    batchBlockId=batch.id,
                    fixProposal="Add a Prompt Segment before generate.",
                )
            )
        if batch.duration.plannedDuration <= 0:
            findings.append(
                PreflightFinding(
                    severity="error",
                    code="invalid_duration",
                    message=f"{batch.label} plannedDuration must be > 0.",
                    batchBlockId=batch.id,
                )
            )
        for ref in batch.references or []:
            if not isinstance(ref, dict):
                continue
            asset_id = ref.get("assetId") or ref.get("asset_id")
            if asset_id:
                continue
            required = bool(ref.get("required"))
            role = str(ref.get("role") or ref.get("referenceRole") or "supporting")
            gen = get_generator(batch.generatorId)
            generator_requires = bool(required and gen and getattr(gen, "requiresReferences", False))
            if generator_requires:
                findings.append(
                    PreflightFinding(
                        severity="error",
                        code="missing_required_reference",
                        message=f"{batch.label}: {role} reference is required by the selected generator.",
                        batchBlockId=batch.id,
                        fixProposal="Attach the required reference or choose another generator.",
                    )
                )
            else:
                findings.append(
                    PreflightFinding(
                        severity="warning",
                        code="missing_optional_reference",
                        message=(
                            f"{batch.label}: optional {role} reference is not attached yet. "
                            f"{OPTIONAL_REFS_POLICY_NOTE}"
                        ),
                        batchBlockId=batch.id,
                        fixProposal="Attach a supporting reference for stronger continuity, or continue without it.",
                    )
                )
        # Major camera-less end frame hint when multiple anchors without end_frame
        kinds = {a.kind for a in batch.sourceAnchors}
        if "image" in kinds and "end_frame" not in kinds and len(batch.sourceAnchors) >= 2:
            findings.append(
                PreflightFinding(
                    severity="info",
                    code="missing_end_frame",
                    message=f"{batch.label}: multiple anchors without End Frame — continuity risk.",
                    batchBlockId=batch.id,
                    fixProposal="Add an End Frame anchor.",
                )
            )
    if director_timeline and director_timeline.camera_clips:
        strategy = summarize_camera_strategy(director_timeline.camera_clips)
        if strategy["capability"] in ("Approximate", "Unsupported"):
            findings.append(
                PreflightFinding(
                    severity="warning",
                    code="camera_strategy_limit",
                    message=(
                        "Camera plan uses "
                        f"{strategy['capability']} execution, so the generated result may need prompt interpretation."
                    ),
                    fixProposal="Choose a Native or Workflow-Mapped camera move for stronger execution fidelity.",
                )
            )
        for item in detect_camera_contradictions(director_timeline.camera_clips):
            findings.append(
                PreflightFinding(
                    severity=item["severity"],
                    code=item["code"],
                    message=item["message"],
                    batchBlockId=None,
                    fixProposal=item.get("fixProposal"),
                )
            )
    return [f.model_dump() for f in findings]


def stage_batch_snapshot(
    db: Session,
    project_id: str,
    scene_id: str,
    batch_id: str,
) -> dict[str, Any]:
    """SEQUENTIAL_SUBMISSION_CHAIN: create the immutable snapshot for a batch
    and mark it Queued WITHOUT submitting to the provider.

    REQUEST SNAPSHOT CREATED != PROVIDER JOB SUBMITTED. Staged batches wait
    for the sequential slot to free.
    """
    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return payload
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = _batch_map(master).get(batch_id)
    if not batch:
        return {"ok": False, "error": "BATCH_NOT_FOUND", "mock": False}
    if not batch.generatorId:
        return {
            "ok": False,
            "error": "GENERATOR_REQUIRED",
            "message": "Select a generator for this Batch — no silent default substitution.",
            "mock": False,
        }
    from .capabilities import list_generators
    from .generation.registry import GeneratorNotFoundError, get_registry

    cap = next((g for g in list_generators() if g.id == batch.generatorId), None)
    if cap and not cap.supportsTimelineGeneration:
        return {
            "ok": False,
            "error": "GENERATOR_UNSUPPORTED_FOR_TIMELINE",
            "message": f"{cap.label} does not support Timeline batch generation yet.",
            "mock": False,
        }
    try:
        get_registry().get(batch.generatorId)
    except GeneratorNotFoundError as exc:
        return {"ok": False, "error": "GENERATOR_UNKNOWN", "message": str(exc), "mock": False}
    dur_check = validate_duration(batch.generatorId, batch.duration.plannedDuration)
    if not dur_check.get("ok") and dur_check.get("action") == "choose":
        return {"ok": False, "error": "DURATION_EXCEEDS_GENERATOR", **dur_check, "mock": False}

    snap = _prepare_and_store_snapshot(db, project_id, scene_id, master, batch)
    batch.status = "Queued"
    batch.pendingSnapshotId = snap.id
    store.save_master(db, project_id, scene_id, master)
    return {
        "ok": True,
        "staged": True,
        "batchBlockId": batch.id,
        "executionSnapshotId": snap.id,
        "message": "Snapshot staged; awaiting sequential provider slot.",
        "mock": False,
    }


def submit_next_queued_batch(
    db: Session,
    project_id: str,
    scene_id: str,
) -> dict[str, Any]:
    """SEQUENTIAL_SUBMISSION_CHAIN: after a batch reaches a terminal state,
    submit the next Queued batch (lowest order) with its staged snapshot.

    Provider submission concurrency stays at 1 for local sequential
    orchestration. Idempotent: never submits while another batch is
    Generating; no-op when nothing is Queued.
    """
    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return payload
    master = SceneTimelineMaster.model_validate(payload["master"])
    if any(b.status == "Generating" for b in master.batchBlocks):
        return {"ok": True, "submitted": False, "reason": "generation_in_progress", "mock": False}
    queued = [b for b in master.batchBlocks if b.status == "Queued"]
    if not queued:
        return {"ok": True, "submitted": False, "reason": "no_queued_batches", "mock": False}
    nxt = sorted(queued, key=lambda b: b.order)[0]
    result = submit_batch_generation(
        db,
        project_id,
        scene_id,
        nxt.id,
        precreated_snapshot_id=nxt.pendingSnapshotId or None,
    )
    return {
        "ok": True,
        "submitted": bool(result.get("ok")),
        "batchBlockId": nxt.id,
        "result": result,
        "mock": False,
    }


def generate_scene(
    db: Session,
    project_id: str,
    scene_id: str,
    *,
    scope: Literal["current", "selected", "ready", "full"] = "full",
    batch_ids: list[str] | None = None,
) -> dict[str, Any]:
    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return payload
    master = SceneTimelineMaster.model_validate(payload["master"])
    director_timeline = _load_director_timeline(db, project_id, scene_id)
    findings = run_preflight(master, director_timeline=director_timeline)
    if master.preflightMode == "strict" and any(f["severity"] == "error" for f in findings):
        return {"ok": False, "error": "PREFLIGHT_STRICT", "findings": findings, "mock": False}

    selected = batch_ids or []
    jobs = []
    errors = []
    # ORCHESTRATOR_MODE_HONORED + SEQUENTIAL_SUBMISSION_CHAIN:
    # Sequential (default): the first eligible batch is submitted to the
    # provider; every later eligible batch gets an immutable snapshot staged
    # (status=Queued) and is submitted only when the active batch reaches a
    # terminal state — provider submission concurrency = 1. Parallel intent
    # submits one immutable request per batch in order immediately (each
    # batch = its own request/snapshot — GENERATION_ISOLATION).
    mode = getattr(master, "orchestratorMode", "sequential_continuity") or "sequential_continuity"
    sequential = mode != "parallel"

    eligible: list[BatchBlock] = []
    for batch in sorted(master.batchBlocks, key=lambda b: b.order):
        if scope == "selected" and batch.id not in selected:
            continue
        if scope == "ready" and batch.status not in ("Ready", "Draft", "RegenerationRecommended", "ApprovedConfigurationChanged"):
            continue
        if scope == "current" and selected and batch.id not in selected:
            continue
        # Skip completed unless explicitly selected for regeneration
        if batch.status in ("Approved", "CandidateReady") and scope == "full":
            continue
        # Never double-submit an in-flight batch
        if batch.status == "Generating":
            continue
        eligible.append(batch)

    any_generating = any(b.status == "Generating" for b in master.batchBlocks)
    for idx, batch in enumerate(eligible):
        if sequential and (idx > 0 or any_generating):
            result = stage_batch_snapshot(db, project_id, scene_id, batch.id)
            if result.get("ok"):
                jobs.append(result)
            else:
                errors.append({"batchBlockId": batch.id, **result})
            continue
        result = submit_batch_generation(
            db,
            project_id,
            scene_id,
            batch.id,
            precreated_snapshot_id=batch.pendingSnapshotId or None,
        )
        if result.get("ok"):
            jobs.append(result)
        else:
            errors.append({"batchBlockId": batch.id, **result})

    return {
        "ok": len(errors) == 0 or len(jobs) > 0,
        "partialFailure": bool(errors) and bool(jobs),
        "jobs": jobs,
        "errors": errors,
        "findings": findings,
        "orchestratorMode": mode,
        "message": "Partial failure preserved successes." if errors and jobs else "Scene generation submitted.",
        "mock": False,
    }
