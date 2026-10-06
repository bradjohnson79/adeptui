"""Shared post-generation completion: Library asset → candidate → approve → place clips."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .. import orchestrator, store
from ..contracts import ApprovedClip, BatchClip, SceneTimelineMaster
from .contracts import NormalizedJobSubmission, TimelineGenerationResult

MANAGED_DIRECTOR_CLIP_PREFIX = "bbclip_"
MANAGED_BATCH_VISUAL_PREFIX = "bbvclip_"


def _latest_candidate_with_asset(batch: Any) -> Any | None:
    cands = [c for c in (batch.candidateVersions or []) if getattr(c, "assetId", None)]
    if not cands:
        return None
    return max(cands, key=lambda c: (getattr(c, "createdAt", None) or "", getattr(c, "id", None) or ""))


def _playable_take_for_batch(
    batch: Any,
    preferred_assets: dict[str, str] | None = None,
) -> tuple[str, float] | None:
    # OWNER-PROTECTED (Timeline Batch Architecture Guard). CURRENT TAKE's member
    # asset takes precedence over a stale approvedClip — this is the 12B visual
    # track model. Fences: tests/test_timeline_architecture_guard.py
    """Latest viewable take for Visual: approved clip, else newest candidate asset.

    Approve stays a separate creator action. A finished generate still belongs
    on the Visual track so the take can be watched without a Library drag.

    12B working-Timeline precedence: the CURRENT whole-scene Take's member
    asset wins over a stale approvedClip. An approvedClip left from a
    historical Take (e.g. Take A) must not shadow the take the creator is
    actually looking at — that placed a dead Take A asset on the Visual track
    while Take N was current (Cade Scene 3 regression).
    """
    approved_id = (
        batch.approvedClip.assetId
        if batch.approvedClip and getattr(batch.approvedClip, "assetId", None)
        else None
    )
    preferred = str((preferred_assets or {}).get(str(batch.id or "")) or "").strip()
    latest = _latest_candidate_with_asset(batch)
    duration_hint = None
    # A09: when a current-take preferred map is supplied, never borrow another
    # take's candidate/approved asset under the current-take stamp.
    if preferred_assets is not None:
        if not preferred:
            return None
        asset_id = preferred
        if latest and latest.assetId == preferred:
            duration_hint = latest.generatedDuration
    elif preferred:
        # Current take membership is the display authority.
        asset_id = preferred
        if latest and latest.assetId == preferred:
            duration_hint = latest.generatedDuration
    elif approved_id:
        asset_id = str(approved_id)
        if latest and latest.assetId == approved_id:
            duration_hint = latest.generatedDuration
    elif latest and latest.assetId:
        asset_id = str(latest.assetId)
        duration_hint = latest.generatedDuration
    else:
        return None
    length = float(
        batch.duration.timelineVisibleDuration
        or batch.duration.generatedDuration
        or duration_hint
        or batch.duration.plannedDuration
        or 5.0
    )
    return asset_id, length


def _upsert_managed_visual_take(batch: Any, asset_id: str, length: float) -> None:
    clip_id = f"{MANAGED_BATCH_VISUAL_PREFIX}{batch.id}"
    kept = [c for c in (batch.visualClips or []) if c.id != clip_id]
    kept.append(
        BatchClip(
            id=clip_id,
            kind="video",
            assetId=asset_id,
            start=0.0,
            length=length,
            label=batch.label or "Take",
            role="take",
        )
    )
    batch.visualClips = kept


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
                    # Prefer fal request id from result when hosted adapter promoted it.
                    j.providerJobId = (  # type: ignore[attr-defined]
                        result.providerJobId or job.providerJobId or j.providerJobId
                    )
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
        "generationMode": meta.get("generationMode") or getattr(result, "generationMode", None),
        "adapterKind": meta.get("adapterKind") or getattr(result, "adapterKind", None),
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
        "falModelId": meta.get("falModelId"),
        "falRequestId": meta.get("falRequestId") or result.providerJobId,
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
    measured = float(result.duration) if result.duration else 0.0

    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return payload
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = next((b for b in master.batchBlocks if b.id == batch_id), None)
    if not batch:
        return {"ok": False, "error": "BATCH_NOT_FOUND", "mock": False}
    duration = measured if measured > 0 else float(batch.duration.plannedDuration or 5.0)

    snap = master.executionSnapshots.get(execution_snapshot_id)
    range_rep = dict((snap.continuityState or {}).get("rangeReplacement") or {}) if snap else {}
    existing_for_snap = next(
        (c for c in batch.candidateVersions if c.executionSnapshotId == execution_snapshot_id),
        None,
    )
    # Range retake: keep the generated SLICE as replacementAssetId.
    # Visual authority is replace_visual_range (A|Retake|B) — not Library MP4 stitch.
    is_range_retake = bool(range_rep.get("length"))
    range_source_id = ""
    if is_range_retake:
        range_source_id = str(
            range_rep.get("sourceAssetId")
            or (batch.approvedClip.assetId if batch.approvedClip else "")
            or ""
        )
        if not range_source_id and not existing_for_snap:
            return {
                "ok": False,
                "error": "SOURCE_VIDEO_MISSING",
                "message": "Bounded Re-take needs the current take to keep the unmarked parts.",
                "mock": False,
            }
        if existing_for_snap and existing_for_snap.assetId:
            asset_id = existing_for_snap.assetId
            duration = float(
                existing_for_snap.generatedDuration
                or range_rep.get("length")
                or duration
            )
        else:
            # Candidate duration is the marked slice — do not stretch to full planned.
            duration = float(measured if measured > 0 else range_rep.get("length") or duration)
    elif existing_for_snap and existing_for_snap.assetId:
        asset_id = existing_for_snap.assetId
        duration = float(batch.duration.plannedDuration or existing_for_snap.generatedDuration or duration)

    # Idempotency: if already approved with same asset + snapshot, only ensure placement.
    if (
        batch.approvedClip
        and batch.approvedClip.assetId == asset_id
        and batch.approvedClip.executionSnapshotId == execution_snapshot_id
        and batch.status == "Approved"
    ):
        if is_range_retake:
            place = _apply_range_visual_replacement(
                db,
                project_id=project_id,
                scene_id=scene_id,
                batch_id=batch_id,
                range_rep=range_rep,
                replacement_asset_id=asset_id,
                replacement_duration=duration,
                source_asset_id=range_source_id,
            )
        else:
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
    repair_id = str(range_rep.get("repairId") or "")
    if repair_id:
        for repair in live_batch.repairRanges:
            if repair.id == repair_id:
                repair.status = "ready"
                repair.executionSnapshotId = execution_snapshot_id
                repair.candidateId = cand_id
                store.save_master(db, project_id, scene_id, live)
                break
    new_cand = next((c for c in live_batch.candidateVersions if c.id == cand_id), None)
    take_state = dict(new_cand.takeState or {}) if new_cand else {}
    is_draft = str(take_state.get("quality") or "").lower() == "draft"
    if is_draft:
        auto_approve = False
        _label_draft_library_asset(db, asset_id)
    if (
        getattr(live, "activeSceneTakeId", None)
        and live.activeSceneTakeId
        and live.activeSceneTakeId != getattr(live, "currentSceneTakeId", None)
    ):
        auto_approve = False
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

    # Range retake complete: always insert via replace_visual_range even when
    # auto_approve is False (insertion is Timeline composition, not approve).
    if is_range_retake:
        # Batch visible span stays the full take (A|R|B); candidate holds slice duration.
        payload_vis = store.load_master(db, project_id, scene_id)
        if payload_vis.get("ok"):
            live_vis = SceneTimelineMaster.model_validate(payload_vis["master"])
            live_b = next((b for b in live_vis.batchBlocks if b.id == batch_id), None)
            if live_b:
                planned = float(live_b.duration.plannedDuration or 0.0)
                if planned > 0:
                    live_b.duration.timelineVisibleDuration = planned
                    store.save_master(db, project_id, scene_id, live_vis)
        placement = _apply_range_visual_replacement(
            db,
            project_id=project_id,
            scene_id=scene_id,
            batch_id=batch_id,
            range_rep=range_rep,
            replacement_asset_id=asset_id,
            replacement_duration=duration,
            source_asset_id=range_source_id,
        )
        if not placement.get("ok"):
            return placement
    else:
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



def _apply_range_visual_replacement(
    db: Session,
    *,
    project_id: str,
    scene_id: str,
    batch_id: str,
    range_rep: dict[str, Any],
    replacement_asset_id: str,
    replacement_duration: float | None = None,
    source_asset_id: str | None = None,
) -> dict[str, Any]:
    """Visual A|Retake|B write for range retake complete. Never bbclip_ whole-take.

    SINGLE-STORE: replace_visual_range resolves the active take from Master
    batch.visualClips (managed bbvclip_ take, prior A|Middle|B composition, or
    the batch playable take). No legacy director_json video_clips seeding —
    save_master persists Master only, so a legacy seed would be a dead write.
    """
    from ..visual_range import replace_visual_range

    start = float(range_rep.get("start") or 0.0)
    length = float(range_rep.get("length") or 0.0)
    mark_in = start
    mark_out = start + length
    repair_id = str(range_rep.get("repairId") or "") or None
    src = str(
        source_asset_id
        or range_rep.get("sourceAssetId")
        or ""
    )

    ref_img = str(
        range_rep.get('referenceImageAssetId')
        or range_rep.get('startImageAssetId')
        or ''
    ).strip() or None
    return replace_visual_range(
        db,
        project_id,
        scene_id,
        mark_in=mark_in,
        mark_out=mark_out,
        replacement_asset_id=replacement_asset_id,
        retake_id=repair_id,
        source_batch_id=batch_id,
        source_asset_id=src or None,
        replacement_duration=replacement_duration,
        reference_image_asset_id=ref_img,
    )


def place_approved_batches_on_timeline(
    db: Session,
    project_id: str,
    scene_id: str,
) -> dict[str, Any]:
    """Place/update Master batch.visualClips managed takes from playable takes.

    Approved takes win when present so a Re-Take candidate does not overwrite
    the active take. Otherwise the latest finished candidate is placed so a
    draft generate appears on Visual without Approve or a Library drag.
    Idempotent upsert by bbvclip_{batchId} (batch-local start=0.0).
    Batches with an active A|Middle|B range composition are never overwritten.

    SINGLE-STORE: Master batch.visualClips is the sole Visual authority. The
    retired legacy video_clips array is never read or written here.
    """
    bundle = store.load_master(db, project_id, scene_id)
    if not bundle.get("ok"):
        return bundle
    master = SceneTimelineMaster.model_validate(bundle["master"])
    scene = store.get_scene(db, project_id, scene_id)
    if not scene:
        return {"ok": False, "error": "SCENE_NOT_FOUND", "mock": False}

    from ..visual_range import clip_belongs_to_range_batch, range_retake_batch_ids

    range_batches = range_retake_batch_ids(master)
    placed_ids: list[str] = []
    cursor = 0.0
    # 12B working-Timeline precedence: the CURRENT whole-scene Take's member
    # assets are the Visual display authority (see _playable_take_for_batch).
    current_take = next(
        (
            t
            for t in (master.sceneTakes or [])
            if t.id == getattr(master, "currentSceneTakeId", None)
        ),
        None,
    )
    # The take being rendered is what the creator is watching. Its deposited
    # windows go on Visual as they finish. With no render in flight, the
    # current take stays the display authority.
    active_take = next(
        (
            t
            for t in (master.sceneTakes or [])
            if t.id == getattr(master, "activeSceneTakeId", None) and t.status == "rendering"
        ),
        None,
    )
    display_take = active_take or current_take
    # A09: only enter current-take fail-closed mode when a current scene take exists.
    # None keeps legacy approved/latest placement for scenes without sceneTakes.
    preferred_assets = (
        {
            str(m.batchId): str(m.assetId or "").strip()
            for m in (display_take.batches or [])
            if getattr(m, "assetId", None)
        }
        if display_take is not None
        else None
    )
    for batch in sorted(master.batchBlocks, key=lambda b: b.order):
        if batch.id in range_batches:
            # A|Middle|B composition active on Master — never overwrite with a
            # whole-take managed clip. Advance the cursor by the composition end.
            related = [
                c
                for c in (batch.visualClips or [])
                if clip_belongs_to_range_batch(c, str(batch.id))
            ]
            if related:
                end = max(float(c.start or 0.0) + float(c.length or 0.0) for c in related)
                cursor = max(cursor, end)
            else:
                take = _playable_take_for_batch(batch, preferred_assets)
                if take:
                    cursor += float(take[1])
            continue
        take = _playable_take_for_batch(batch, preferred_assets)
        if not take:
            # A window the in-flight take has not deposited yet must not keep
            # the previous take's bar.
            if active_take is not None:
                clip_id = f"{MANAGED_BATCH_VISUAL_PREFIX}{batch.id}"
                batch.visualClips = [c for c in (batch.visualClips or []) if c.id != clip_id]
            # A09: missing window asset still advances the placement cursor so
            # later batches keep scene-absolute starts (no collapse/borrow).
            planned = float(
                getattr(getattr(batch, "duration", None), "timelineVisibleDuration", None)
                or getattr(getattr(batch, "duration", None), "generatedDuration", None)
                or getattr(getattr(batch, "duration", None), "plannedDuration", None)
                or 5.0
            )
            cursor += max(0.1, planned)
            continue
        asset_id, length = take
        dismissed = str(getattr(batch, "dismissedVisualAssetId", None) or "").strip()
        if dismissed and dismissed == asset_id:
            # Creator removed this video from Visual. Do not put the same asset back.
            cursor += length
            continue
        if dismissed and dismissed != asset_id:
            batch.dismissedVisualAssetId = None
        _upsert_managed_visual_take(batch, asset_id, length)
        placed_ids.append(f"{MANAGED_BATCH_VISUAL_PREFIX}{batch.id}")
        cursor += length

    store.save_master(db, project_id, scene_id, master, bump_revision=True)
    return {
        "ok": True,
        "placedCount": len(placed_ids),
        "clipIds": placed_ids,
        "totalDuration": cursor,
        "mock": False,
    }
