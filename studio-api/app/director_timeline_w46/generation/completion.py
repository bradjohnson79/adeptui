"""Shared post-generation completion: Library asset → candidate → approve → place clips."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ...director_timeline import TimelineClip
from .. import orchestrator, store
from ..contracts import ApprovedClip, SceneTimelineMaster
from .contracts import NormalizedJobSubmission, TimelineGenerationResult


def _label_draft_library_asset(db: Session, asset_id: str) -> None:
    """Mark the Library asset as a draft without deleting or replacing it."""
    if not (asset_id or "").strip():
        return
    try:
        from ...db import Asset

        row = db.get(Asset, str(asset_id))
        if not row:
            return
        tag = (row.tag or "").strip()
        if "draft" not in tag.lower():
            row.tag = f"{tag}-draft" if tag else "draft"
        import json

        meta: dict[str, Any] = {}
        raw = getattr(row, "prompt_meta_json", None) or "{}"
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(parsed, dict):
                meta = parsed
        except Exception:
            meta = {}
        meta["quality"] = "draft"
        row.prompt_meta_json = json.dumps(meta)
        db.add(row)
        db.commit()
    except Exception:
        pass


def _stash_generation_lineage(
    db: Session,
    *,
    project_id: str,
    scene_id: str,
    batch_id: str,
    execution_snapshot_id: str,
    result: TimelineGenerationResult,
    job: NormalizedJobSubmission | None,
    asset_id: str,
    quality: str,
) -> None:
    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = next((b for b in master.batchBlocks if b.id == batch_id), None)
    if not batch:
        return
    for j in batch.generationJobs:
        if j.executionSnapshotId == execution_snapshot_id:
            j.status = "completed"
            if job:
                j.queueJobId = job.queueJobId or j.queueJobId
                if hasattr(j, "providerJobId"):
                    j.providerJobId = job.providerJobId  # type: ignore[attr-defined]
                if hasattr(j, "generatorId"):
                    j.generatorId = result.generatorId  # type: ignore[attr-defined]
                if hasattr(j, "apiUsed"):
                    j.apiUsed = result.apiUsed  # type: ignore[attr-defined]
    meta = result.providerMetadata if isinstance(result.providerMetadata, dict) else {}
    lineage = {
        "kind": "timelineGenerationLineage",
        "projectId": project_id,
        "sceneId": scene_id,
        "batchBlockId": batch_id,
        "executionSnapshotId": execution_snapshot_id,
        "internalJobId": result.internalJobId,
        "providerJobId": result.providerJobId,
        "queueJobId": result.queueJobId,
        "generatorId": result.generatorId,
        "outputAssetId": asset_id,
        "apiUsed": result.apiUsed,
        "startImageAssetId": meta.get("startImageAssetId"),
        "startImageSha256": meta.get("startImageSha256"),
        "comfyImageName": meta.get("comfyImageName"),
        "workflowId": meta.get("workflowId"),
        "videoReferenceAssetId": meta.get("videoReferenceAssetId"),
        "draftMode": meta.get("draftMode") if meta.get("draftMode") is not None else quality == "draft",
        "draftPathway": meta.get("draftPathway"),
        "aspectRatio": meta.get("aspectRatio"),
        "resolution": meta.get("resolution"),
        "quality": quality,
    }
    refs = [
        r
        for r in (batch.references or [])
        if not (
            isinstance(r, dict)
            and r.get("kind") == "timelineGenerationLineage"
            and r.get("executionSnapshotId") == execution_snapshot_id
        )
    ]
    refs.append(lineage)
    batch.references = refs
    store.save_master(db, project_id, scene_id, master)


def apply_shared_completion(
    db: Session,
    *,
    project_id: str,
    scene_id: str,
    batch_id: str,
    execution_snapshot_id: str,
    result: TimelineGenerationResult,
    job: NormalizedJobSubmission | None = None,
    auto_approve: bool = True,
) -> dict[str, Any]:
    """Idempotent completion path used by all adapters."""
    if result.status != "completed":
        return {
            "ok": False,
            "error": result.errorCode or "GENERATION_NOT_COMPLETE",
            "message": result.errorMessage or "Generation is not complete.",
            "mock": False,
        }
    if not result.outputAssetIds:
        return {
            "ok": False,
            "error": "OUTPUT_ASSET_MISSING",
            "message": "Normalized result has no outputAssetIds.",
            "mock": False,
        }

    asset_id = str(result.outputAssetIds[0])
    duration = float(result.duration or 5.0)

    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return payload
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = next((b for b in master.batchBlocks if b.id == batch_id), None)
    if not batch:
        return {"ok": False, "error": "BATCH_NOT_FOUND", "mock": False}

    # Idempotency: if already approved with same asset + snapshot, only ensure placement.
    if (
        batch.approvedClip
        and batch.approvedClip.assetId == asset_id
        and batch.approvedClip.executionSnapshotId == execution_snapshot_id
        and batch.status == "Approved"
    ):
        place = place_approved_batches_on_timeline(db, project_id, scene_id)
        return {
            "ok": True,
            "idempotent": True,
            "candidate": None,
            "approvedClip": batch.approvedClip.model_dump(),
            "placement": place,
            "mock": False,
        }

    # Avoid duplicate candidates for the same snapshot+asset
    existing = next(
        (
            c
            for c in batch.candidateVersions
            if c.executionSnapshotId == execution_snapshot_id and c.assetId == asset_id
        ),
        None,
    )
    if existing:
        cand_id = existing.id
        complete = {
            "ok": True,
            "candidate": existing.model_dump(),
            "idempotent": True,
        }
    else:
        complete = orchestrator.complete_batch_candidate(
            db,
            project_id,
            scene_id,
            batch_id,
            asset_id=asset_id,
            generated_duration=duration,
            execution_snapshot_id=execution_snapshot_id,
        )
        if not complete.get("ok"):
            return complete
        cand_id = complete["candidate"]["id"]

    # Continuity-aware Re-Take must not overwrite Take A. The new candidate
    # stays selectable as Take B until the creator activates it.
    payload_now = store.load_master(db, project_id, scene_id)
    live = SceneTimelineMaster.model_validate(payload_now["master"]) if payload_now.get("ok") else master
    live_batch = next((b for b in live.batchBlocks if b.id == batch_id), batch)
    new_cand = next((c for c in live_batch.candidateVersions if c.id == cand_id), None)
    take_state = dict(new_cand.takeState or {}) if new_cand else {}
    is_draft = str(take_state.get("quality") or "").lower() == "draft"
    if is_draft:
        auto_approve = False
        _label_draft_library_asset(db, asset_id)
    if (
        auto_approve
        and live_batch.approvedClip
        and new_cand
        and (new_cand.reTakeReason or new_cand.parentTakeId)
    ):
        auto_approve = False

    _stash_generation_lineage(
        db,
        project_id=project_id,
        scene_id=scene_id,
        batch_id=batch_id,
        execution_snapshot_id=execution_snapshot_id,
        result=result,
        job=job,
        asset_id=asset_id,
        quality="draft" if is_draft else "final",
    )

    approved = None
    if auto_approve:
        approved = orchestrator.approve_candidate(db, project_id, scene_id, batch_id, cand_id)
        if not approved.get("ok"):
            return approved
        payload2 = store.load_master(db, project_id, scene_id)
        master2 = SceneTimelineMaster.model_validate(payload2["master"])
        batch2 = next((b for b in master2.batchBlocks if b.id == batch_id), None)
        if batch2 and batch2.approvedClip:
            batch2.approvedClip = ApprovedClip(
                assetId=batch2.approvedClip.assetId,
                executionSnapshotId=batch2.approvedClip.executionSnapshotId,
                candidateId=batch2.approvedClip.candidateId,
                approvedAt=batch2.approvedClip.approvedAt,
                playable=True,
            )
            store.save_master(db, project_id, scene_id, master2)

    placement = place_approved_batches_on_timeline(db, project_id, scene_id)
    return {
        "ok": True,
        "idempotent": False,
        "candidate": complete.get("candidate"),
        "approved": approved,
        "placement": placement,
        "lineage": {
            "projectId": project_id,
            "sceneId": scene_id,
            "batchBlockId": batch_id,
            "executionSnapshotId": execution_snapshot_id,
            "internalJobId": result.internalJobId,
            "providerJobId": result.providerJobId,
            "queueJobId": result.queueJobId,
            "generatorId": result.generatorId,
            "outputAssetId": asset_id,
        },
        "mock": False,
    }


def place_approved_batches_on_timeline(
    db: Session,
    project_id: str,
    scene_id: str,
) -> dict[str, Any]:
    """Place/update video_clips from approved batches in batch order (not completion order)."""
    bundle = store.load_master(db, project_id, scene_id)
    if not bundle.get("ok"):
        return bundle
    master = SceneTimelineMaster.model_validate(bundle["master"])
    scene = store.get_scene(db, project_id, scene_id)
    if not scene:
        return {"ok": False, "error": "SCENE_NOT_FOUND", "mock": False}

    from ...director_timeline import parse_director_timeline

    director_tl = parse_director_timeline(
        scene.director_json,
        fallback_duration=float(scene.duration_sec or 5.0),
        fallback_prompt=scene.prompt or "",
    )

    # Keep non-batch-managed clips (manual) — replace only clips tagged with batch ids.
    managed_prefix = "bbclip_"
    retained = [c for c in (director_tl.video_clips or []) if not str(c.id).startswith(managed_prefix)]
    placed: list[TimelineClip] = []
    cursor = 0.0
    for batch in sorted(master.batchBlocks, key=lambda b: b.order):
        if not batch.approvedClip or not batch.approvedClip.assetId:
            continue
        length = float(
            batch.duration.timelineVisibleDuration
            or batch.duration.generatedDuration
            or batch.duration.plannedDuration
            or 5.0
        )
        clip_id = f"{managed_prefix}{batch.id}"
        # Idempotent upsert by stable id
        clip = TimelineClip(
            id=clip_id,
            asset_id=batch.approvedClip.assetId,
            start=cursor,
            length=length,
            label=batch.label or f"Batch {batch.order + 1}",
        )
        placed.append(clip)
        cursor += length

    director_tl.video_clips = retained + placed
    director_tl.media_mode = "video"
    if placed:
        director_tl.duration_sec = max(float(director_tl.duration_sec or 0.0), cursor)

    store.save_master(db, project_id, scene_id, master, director_tl=director_tl, bump_revision=True)
    return {
        "ok": True,
        "placedCount": len(placed),
        "clipIds": [c.id for c in placed],
        "totalDuration": cursor,
        "mock": False,
    }
