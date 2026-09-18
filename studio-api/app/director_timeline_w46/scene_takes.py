"""Whole-scene Takes — one complete multi-batch render of a Timeline scene.

Canonical store is SceneTimelineMaster.sceneTakes. Batch candidateVersions remain
the per-batch generation ledger. gfx/sequence stores are untouched.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from . import store
from .contracts import (
    ApprovedClip,
    SceneTake,
    SceneTakeBatchMember,
    SceneTakeQuality,
    SceneTimelineMaster,
    _nid,
    _now,
)
from .current_take import resolve_current_take

logger = logging.getLogger(__name__)

PLAYABLE_BATCH = frozenset(
    {
        "Approved",
        "CandidateReady",
        "ApprovedConfigurationChanged",
        "RegenerationRecommended",
        "NeedsDialogueRetake",
    }
)


def scene_take_letter(index: int) -> str:
    """1-based: 1→A … 26→Z, 27→Z1, 28→Z2. Never AA/AB."""
    if index < 1:
        raise ValueError("take index must be >= 1")
    if index <= 26:
        return chr(ord("A") + index - 1)
    return f"Z{index - 26}"


def scene_take_display(label: str) -> str:
    text = str(label or "").strip()
    if text.lower().startswith("take "):
        return text
    return f"Take {text}" if text else "Take"


def next_scene_take_index(master: SceneTimelineMaster) -> int:
    used = [int(t.letterIndex or 0) for t in (master.sceneTakes or []) if int(t.letterIndex or 0) > 0]
    return (max(used) + 1) if used else 1


def current_scene_take(master: SceneTimelineMaster | None) -> SceneTake | None:
    if master is None:
        return None
    cid = str(getattr(master, "currentSceneTakeId", None) or "").strip()
    takes = list(getattr(master, "sceneTakes", None) or [])
    if cid:
        hit = next((t for t in takes if t.id == cid), None)
        if hit is not None:
            return hit
    return takes[0] if takes else None


def active_scene_take(master: SceneTimelineMaster | None) -> SceneTake | None:
    if master is None:
        return None
    aid = str(getattr(master, "activeSceneTakeId", None) or "").strip()
    if not aid:
        return None
    return next((t for t in (master.sceneTakes or []) if t.id == aid), None)


def _batch_playable_asset(batch: Any, master: SceneTimelineMaster | None = None) -> dict[str, Any]:
    """WAVE 3 FAIL-CLOSED: current Take asset only — no approved/latest fallbacks."""
    resolved = resolve_current_take(batch, master) or {}
    asset = str(resolved.get("assetId") or "").strip()
    duration = None
    try:
        duration = float(
            getattr(getattr(batch, "duration", None), "timelineVisibleDuration", None)
            or getattr(getattr(batch, "duration", None), "generatedDuration", None)
            or getattr(getattr(batch, "duration", None), "plannedDuration", None)
            or 0
        ) or None
    except (TypeError, ValueError):
        duration = None
    return {
        "assetId": asset or None,
        "candidateId": resolved.get("candidateId"),
        "batchTakeId": resolved.get("takeId") or getattr(batch, "currentTakeId", None),
        "durationSec": duration,
        "status": str(getattr(batch, "status", "") or ""),
        "ok": bool(asset),
        "error": None if asset else "CURRENT_TAKE_ASSET_REQUIRED",
        "source": resolved.get("source"),
    }


def _scene_has_complete_render(master: SceneTimelineMaster) -> bool:
    batches = list(master.batchBlocks or [])
    if not batches:
        return False
    if master.sceneStitch and str(master.sceneStitch.assetId or "").strip():
        return True
    return all(str(_batch_playable_asset(b).get("assetId") or "").strip() for b in batches)


def capture_batch_members(master: SceneTimelineMaster) -> list[SceneTakeBatchMember]:
    rows: list[SceneTakeBatchMember] = []
    for batch in sorted(master.batchBlocks or [], key=lambda b: (int(getattr(b, "order", 0) or 0), str(b.id))):
        info = _batch_playable_asset(batch, master)
        rows.append(
            SceneTakeBatchMember(
                batchId=batch.id,
                order=int(getattr(batch, "order", 0) or 0),
                assetId=info.get("assetId"),
                candidateId=info.get("candidateId"),
                batchTakeId=info.get("batchTakeId"),
                durationSec=info.get("durationSec"),
                status=str(info.get("status") or "pending"),
            )
        )
    return rows


def snapshot_generation_config(master: SceneTimelineMaster) -> dict[str, Any]:
    batches = sorted(master.batchBlocks or [], key=lambda b: int(getattr(b, "order", 0) or 0))
    first = batches[0] if batches else None
    prompts: list[dict[str, Any]] = []
    for batch in batches:
        for seg in getattr(batch, "promptSegments", None) or []:
            prompts.append(
                {
                    "batchId": batch.id,
                    "id": getattr(seg, "id", None),
                    "start": getattr(seg, "start", None),
                    "length": getattr(seg, "length", None),
                    "text": getattr(seg, "text", None),
                }
            )
    refs: list[Any] = []
    for batch in batches:
        for ref in getattr(batch, "references", None) or []:
            if isinstance(ref, dict):
                refs.append({k: ref.get(k) for k in ("id", "kind", "assetId", "label") if k in ref})
    return {
        "sceneGeneratorId": master.sceneGeneratorId,
        "turboLora": bool(getattr(master, "turboLora", False)),
        "orchestratorMode": getattr(master, "orchestratorMode", None),
        "batchIds": [b.id for b in batches],
        "batchCount": len(batches),
        "durations": [
            {
                "batchId": b.id,
                "plannedDuration": float(getattr(getattr(b, "duration", None), "plannedDuration", None) or 0),
            }
            for b in batches
        ],
        "h3Resolution": getattr(first, "h3Resolution", None) if first else None,
        "ltxQuality": getattr(first, "ltxQuality", None) if first else None,
        "prompts": prompts,
        "references": refs,
        "continuityAuto": bool(getattr(getattr(master, "continuityPolicy", None), "autoContinuity", False)),
        "capturedAt": _now(),
    }


def snapshot_quality(master: SceneTimelineMaster) -> SceneTakeQuality:
    batches = list(master.batchBlocks or [])
    first = batches[0] if batches else None
    gid = str(master.sceneGeneratorId or (getattr(first, "generatorId", None) if first else "") or "") or None
    h3 = getattr(first, "h3Resolution", None) if first else None
    ltx = getattr(first, "ltxQuality", None) if first else None
    megapixels = None
    width = None
    height = None
    mode = None
    if isinstance(h3, dict):
        mode = str(h3.get("mode") or "") or None
        try:
            megapixels = float(h3.get("megapixels")) if h3.get("megapixels") is not None else None
        except (TypeError, ValueError):
            megapixels = None
        try:
            from ..video_runtime.legal_canvas import resolve_h3_timeline_canvas

            canvas = resolve_h3_timeline_canvas(h3, draft_mode=False)
            megapixels = float(canvas.get("megapixels") or megapixels or 0) or megapixels
            width = int(canvas.get("width") or 0) or None
            height = int(canvas.get("height") or 0) or None
            mode = str(canvas.get("mode") or mode or "") or mode
        except Exception:
            pass
    duration = 0.0
    for batch in batches:
        try:
            duration += float(getattr(getattr(batch, "duration", None), "plannedDuration", None) or 0)
        except (TypeError, ValueError):
            pass
    return SceneTakeQuality(
        generatorId=gid,
        h3Mode=mode,
        h3Megapixels=megapixels,
        width=width,
        height=height,
        ltxQuality=str(ltx) if ltx else None,
        durationSec=duration or None,
        batchCount=len(batches),
    )


def _freeze_take_from_live(master: SceneTimelineMaster, take: SceneTake) -> None:
    take.batches = capture_batch_members(master)
    if master.sceneStitch and str(master.sceneStitch.assetId or "").strip():
        take.resultAssetId = str(master.sceneStitch.assetId).strip()
    elif len(take.batches) == 1 and take.batches[0].assetId:
        take.resultAssetId = take.batches[0].assetId


def adopt_legacy_retakes(master: SceneTimelineMaster, director_tl: Any) -> bool:
    """Bind pre-Takes Visual Re-Take clips to Take A so they do not follow later Takes."""
    first = next((t for t in (master.sceneTakes or []) if int(t.letterIndex or 0) == 1), None)
    if first is None or first.retakeIds:
        return False
    ids: list[str] = []
    for clip in getattr(director_tl, "video_clips", None) or []:
        meta = getattr(clip, "metadata", None) or {}
        rid = str(meta.get("retakeId") or "").strip() if isinstance(meta, dict) else ""
        if rid and rid not in ids:
            ids.append(rid)
    if not ids:
        return False
    first.retakeIds = ids
    return True


def _historical_batch_members(master: SceneTimelineMaster, *, before: str | None = None) -> list[SceneTakeBatchMember]:
    """Assets that existed before a later Take launched. Never invents media."""
    rows: list[SceneTakeBatchMember] = []
    for batch in sorted(master.batchBlocks or [], key=lambda b: (int(getattr(b, "order", 0) or 0), str(b.id))):
        cands = []
        for cand in getattr(batch, "candidateVersions", None) or []:
            asset = str(getattr(cand, "assetId", None) or "").strip()
            if not asset:
                continue
            created = str(getattr(cand, "createdAt", None) or "")
            if before and created and created >= before:
                continue
            cands.append(cand)
        latest = max(cands, key=lambda c: (str(getattr(c, "createdAt", None) or ""), str(getattr(c, "id", None) or ""))) if cands else None
        if latest is None:
            info = _batch_playable_asset(batch)
            asset = str(info.get("assetId") or "").strip() or None
            rows.append(
                SceneTakeBatchMember(
                    batchId=batch.id,
                    order=int(getattr(batch, "order", 0) or 0),
                    assetId=asset,
                    candidateId=info.get("candidateId") if asset else None,
                    batchTakeId=info.get("batchTakeId") if asset else None,
                    durationSec=info.get("durationSec") if asset else None,
                    status=str(info.get("status") or "pending") if asset else "pending",
                )
            )
            continue
        rows.append(
            SceneTakeBatchMember(
                batchId=batch.id,
                order=int(getattr(batch, "order", 0) or 0),
                assetId=str(latest.assetId).strip(),
                candidateId=str(latest.id),
                batchTakeId=getattr(latest, "takeId", None),
                durationSec=float(getattr(latest, "generatedDuration", None) or getattr(getattr(batch, "duration", None), "plannedDuration", None) or 0) or None,
                status=str(getattr(batch, "status", "") or "ready"),
            )
        )
    return rows


_PROVIDER_LIVE_JOB = frozenset({"running", "submitted", "pending"})
_LIVE_CANCEL_JOB = frozenset({"queued", "running", "pending", "submitted", "cancelling"})


def batch_has_provider_live_job(batch: Any) -> bool:
    """True when this batch has a provider-bound in-flight job.

    A leftover ``Queued`` status or a historic job with status=queued is not live.
    Sequential later batches stay Queued while an earlier batch is Generating —
    that sibling Generating/Waiting is what keeps the scene live.
    """
    if getattr(batch, "activeJobId", None):
        return True
    for job in getattr(batch, "generationJobs", None) or []:
        if str(getattr(job, "status", "") or "").lower() in _PROVIDER_LIVE_JOB:
            return True
    return False


def scene_has_live_render(master: SceneTimelineMaster | None) -> bool:
    """Identity-safe: sequential Queued without Generating/provider job is stale."""
    if master is None:
        return False
    generating = False
    queued_live = False
    for batch in master.batchBlocks or []:
        status = str(getattr(batch, "status", "") or "")
        if status in {"Generating", "Waiting"}:
            generating = True
        if status == "Queued" and batch_has_provider_live_job(batch):
            queued_live = True
        for job in getattr(batch, "generationJobs", None) or []:
            if str(getattr(job, "status", "") or "").lower() in _LIVE_CANCEL_JOB:
                generating = True
    return generating or queued_live


def take_has_live_jobs(master: SceneTimelineMaster, take: SceneTake | None) -> bool:
    """True when an in-flight job is bound to this Take, regardless of Take status."""
    if take is None:
        return False
    for batch in master.batchBlocks or []:
        if str(getattr(batch, "status", "") or "") in {"Generating", "Waiting"}:
            if not getattr(batch, "generationJobs", None):
                return True
        for job in getattr(batch, "generationJobs", None) or []:
            status = str(getattr(job, "status", "") or "").lower()
            if status not in _LIVE_CANCEL_JOB and status not in _PROVIDER_LIVE_JOB:
                continue
            job_take = str(getattr(job, "sceneTakeId", None) or "")
            if job_take and job_take != take.id:
                continue
            if job_take == take.id or (not job_take and str(getattr(batch, "status", "") or "") in {"Generating", "Waiting"}):
                return True
    return False


def take_render_is_live(master: SceneTimelineMaster, take: SceneTake | None = None) -> bool:
    """True only when a real in-flight job belongs to this Take."""
    active = take or active_scene_take(master)
    if active is None:
        return False
    if take_has_live_jobs(master, active):
        return True
    if active.status != "rendering":
        return False
    generating = False
    for batch in master.batchBlocks or []:
        if str(getattr(batch, "status", "") or "") in {"Generating", "Waiting"}:
            generating = True
        if getattr(batch, "activeJobId", None):
            return True
    return generating


def clear_stale_queued_batches(master: SceneTimelineMaster) -> bool:
    """Queued with no Generating sibling and no provider job is leftover queue state."""
    if scene_has_live_render(master):
        return False
    changed = False
    for batch in master.batchBlocks or []:
        if str(getattr(batch, "status", "") or "") != "Queued":
            continue
        if batch_has_provider_live_job(batch):
            continue
        info = _batch_playable_asset(batch)
        batch.status = "CandidateReady" if info.get("assetId") else "Draft"
        if getattr(batch, "pendingSnapshotId", None) and batch.status == "Draft":
            batch.pendingSnapshotId = None
        changed = True
    return changed


def reclaim_misallocated_take_a(master: SceneTimelineMaster) -> bool:
    """If letter-A was reused for a later render, restore historical assets onto Take A."""
    takes = list(master.sceneTakes or [])
    if len(takes) != 1:
        return False
    take = takes[0]
    if int(take.letterIndex or 0) != 1:
        return False
    if take_render_is_live(master, take):
        return False
    if take.status != "rendering":
        return False
    hist = _historical_batch_members(master, before=str(take.createdAt or "") or None)
    if not any(m.assetId for m in hist):
        if take.status == "rendering" and not take_render_is_live(master, take):
            take.status = "incomplete" if any(m.assetId for m in take.batches) else "cancelled"
            take.completedAt = take.completedAt or _now()
            master.activeSceneTakeId = None
            return True
        return False
    take.batches = hist
    take.status = "ready" if all(m.assetId for m in hist) else "incomplete"
    take.completedAt = take.completedAt or _now()
    if take.status == "ready" and not take.resultAssetId:
        _freeze_take_from_live(master, take)
    if master.activeSceneTakeId == take.id:
        master.activeSceneTakeId = None
    if not master.currentSceneTakeId:
        master.currentSceneTakeId = take.id
    return True


def allocate_rendering_take(master: SceneTimelineMaster) -> SceneTake:
    """Mint the next whole-scene Take and make it the active render target."""
    current = current_scene_take(master)
    if current and current.status == "ready":
        _freeze_take_from_live(master, current)
    index = next_scene_take_index(master)
    take = SceneTake(
        id=_nid("stk_"),
        label=scene_take_letter(index),
        letterIndex=index,
        status="rendering",
        createdAt=_now(),
        generationSnapshot=snapshot_generation_config(master),
        quality=snapshot_quality(master),
        batches=[
            SceneTakeBatchMember(batchId=b.id, order=int(b.order or 0), status="pending")
            for b in sorted(master.batchBlocks or [], key=lambda x: int(x.order or 0))
        ],
    )
    master.sceneTakes = list(master.sceneTakes or [])
    master.sceneTakes.append(take)
    master.activeSceneTakeId = take.id
    return take


def bind_generation_to_active_take(master: SceneTimelineMaster, job: Any, candidate_id: str | None = None) -> None:
    take = active_scene_take(master)
    if take is None or job is None:
        return
    if hasattr(job, "sceneTakeId"):
        job.sceneTakeId = take.id
    if candidate_id and hasattr(job, "candidateId"):
        job.candidateId = candidate_id


def scene_take_candidate_label(master: SceneTimelineMaster | None) -> str:
    take = active_scene_take(master) if master is not None else None
    if take is not None:
        return scene_take_display(take.label)
    return "Take A"


def ensure_scene_takes(master: SceneTimelineMaster) -> bool:
    """Migrate existing generated media to Take A. No rerender. Returns True if saved needed."""
    if master.sceneTakes:
        changed = False
        if not master.currentSceneTakeId and master.sceneTakes:
            master.currentSceneTakeId = master.sceneTakes[0].id
            changed = True
        changed = reclaim_misallocated_take_a(master) or changed
        changed = clear_stale_queued_batches(master) or changed
        changed = sync_rendering_take(master) or changed
        return changed
    members = capture_batch_members(master)
    if not any(m.assetId for m in members) and not _scene_has_complete_render(master):
        return False
    complete = _scene_has_complete_render(master) or (members and all(m.assetId for m in members))
    take = SceneTake(
        id=_nid("stk_"),
        label=scene_take_letter(1),
        letterIndex=1,
        status="ready" if complete else "incomplete",
        createdAt=_now(),
        completedAt=_now(),
        generationSnapshot=snapshot_generation_config(master),
        quality=snapshot_quality(master),
        batches=members,
    )
    if complete:
        _freeze_take_from_live(master, take)
    if not any(m.assetId for m in take.batches) and not take.resultAssetId:
        return False
    master.sceneTakes = [take]
    master.currentSceneTakeId = take.id
    clear_stale_queued_batches(master)
    return True


def _take_or_error(master: SceneTimelineMaster, take_id: str) -> SceneTake | None:
    tid = str(take_id or "").strip()
    return next((t for t in (master.sceneTakes or []) if t.id == tid), None)


def delete_block_reason(master: SceneTimelineMaster, take: SceneTake) -> str | None:
    if master.currentSceneTakeId == take.id:
        return "This is the current take. Make another take current before deleting it."
    pub = master.scenePublish
    if pub and (str(pub.takeId or "") == take.id or (take.publishedAssetId and str(pub.publishedAssetId or "") == take.publishedAssetId)):
        return "This take is published. Publish another take before deleting it."
    if pub and take.resultAssetId and str(pub.publishedAssetId or "") == take.resultAssetId:
        return "MAGI / published lineage still points at this take."
    if pub and take.resultAssetId and str(pub.sourceSceneStitchAssetId or "") == take.resultAssetId:
        return "The published master was stitched from this take."
    return None


def apply_take_to_live_batches(master: SceneTimelineMaster, take: SceneTake) -> None:
    """Point live batch playable fields at this Take without regenerating."""
    by_id = {m.batchId: m for m in take.batches}
    for batch in master.batchBlocks or []:
        member = by_id.get(batch.id)
        if not member or not member.assetId:
            continue
        batch.currentTakeAssetId = member.assetId
        batch.currentTakeId = member.batchTakeId
        if member.candidateId:
            cand = next((c for c in (batch.candidateVersions or []) if c.id == member.candidateId), None)
            if cand and cand.assetId:
                batch.approvedClip = ApprovedClip(
                    assetId=str(cand.assetId),
                    executionSnapshotId=str(cand.executionSnapshotId or ""),
                    candidateId=cand.id,
                    playable=True,
                )
                continue
        batch.approvedClip = ApprovedClip(
            assetId=str(member.assetId),
            executionSnapshotId="",
            candidateId=member.candidateId,
            playable=True,
        )
    if take.resultAssetId and master.sceneStitch:
        master.sceneStitch.assetId = take.resultAssetId
        master.sceneStitch.sourceAssetIds = [m.assetId for m in take.batches if m.assetId]
        master.sceneStitch.sourceBatchIds = [m.batchId for m in take.batches]
    elif take.resultAssetId and not master.sceneStitch:
        from .contracts import SceneStitch

        master.sceneStitch = SceneStitch(
            assetId=take.resultAssetId,
            sourceBatchIds=[m.batchId for m in take.batches],
            sourceAssetIds=[m.assetId for m in take.batches if m.assetId],
        )
    elif not take.resultAssetId and master.sceneStitch:
        # REBUILD LAW (scene revision/result authority): a take without a
        # result is NOT a stitched scene result. A prior take's stitch asset
        # must never survive becoming this take current — the scene result is
        # the stitched continuity of the CURRENT take, so the stale pointer is
        # cleared and the scene honestly reports "needs stitch" (publish and
        # stitchReady gates re-derive from this state).
        master.sceneStitch = None
    master.currentSceneTakeId = take.id


def capture_members_for_active_take(master: SceneTimelineMaster, take: SceneTake) -> list[SceneTakeBatchMember]:
    """Only assets generated at/after this Take launched — never copy the prior Take."""
    launched = str(take.createdAt or "")
    current = current_scene_take(master)
    frozen = {m.batchId: str(m.assetId or "") for m in (current.batches if current and current.id != take.id else [])}
    rows: list[SceneTakeBatchMember] = []
    for batch in sorted(master.batchBlocks or [], key=lambda b: (int(getattr(b, "order", 0) or 0), str(b.id))):
        cands = []
        for cand in getattr(batch, "candidateVersions", None) or []:
            asset = str(getattr(cand, "assetId", None) or "").strip()
            if not asset:
                continue
            created = str(getattr(cand, "createdAt", None) or "")
            if launched and created and created < launched:
                continue
            if frozen.get(batch.id) and asset == frozen[batch.id]:
                continue
            cands.append(cand)
        latest = max(cands, key=lambda c: (str(getattr(c, "createdAt", None) or ""), str(getattr(c, "id", None) or ""))) if cands else None
        rows.append(
            SceneTakeBatchMember(
                batchId=batch.id,
                order=int(getattr(batch, "order", 0) or 0),
                assetId=str(latest.assetId).strip() if latest is not None else None,
                candidateId=str(latest.id) if latest is not None else None,
                batchTakeId=getattr(latest, "takeId", None) if latest is not None else None,
                durationSec=float(getattr(latest, "generatedDuration", None) or getattr(getattr(batch, "duration", None), "plannedDuration", None) or 0) or None,
                status=str(getattr(batch, "status", "") or "pending"),
            )
        )
    return rows


def _heal_current_take_pointer(master: SceneTimelineMaster, finished_take: SceneTake) -> None:
    # OWNER-PROTECTED (Timeline Batch Architecture Guard). Healing yields ONLY:
    # cancelled current -> any ready take; incomplete current -> strictly newer
    # ready take. A healthy current take is NEVER stolen by a newer finish —
    # the creator switches takes explicitly (Make Current re-places the track).
    """Point currentSceneTakeId at a healthy take when the old current is dead.

    Cade Scene 3 (Take N) regression: currentSceneTakeId stayed on Take A —
    an incomplete take with no Batch 1 asset — while Takes G..N finished
    ready. The UI take filter then dropped every clip whose asset was not in
    Take A's membership, so the first 15 seconds lost its Visual clip.
    Healing rule: a cancelled current yields to any ready take; an
    incomplete current yields only to a strictly newer ready take (never
    resurrects an older take over newer live work).
    """
    current = current_scene_take(master)
    if current is None:
        master.currentSceneTakeId = finished_take.id
        return
    if current.id == finished_take.id:
        return
    if finished_take.status != "ready":
        return
    if current.status == "cancelled":
        master.currentSceneTakeId = finished_take.id
    elif current.status == "incomplete" and str(finished_take.createdAt or "") > str(
        current.createdAt or ""
    ):
        master.currentSceneTakeId = finished_take.id


def sync_rendering_take(master: SceneTimelineMaster) -> bool:
    """Stamp the active rendering take as batches finish. Mark Ready / Incomplete."""
    take = active_scene_take(master)
    if take is None:
        for candidate in reversed(list(master.sceneTakes or [])):
            if take_has_live_jobs(master, candidate):
                master.activeSceneTakeId = candidate.id
                candidate.status = "rendering"
                take = candidate
                break
        if take is None:
            return False
    if take_has_live_jobs(master, take) and take.status not in {"rendering", "cancelling"}:
        take.status = "rendering"
    if take.status not in {"rendering", "incomplete", "cancelling"}:
        if take_has_live_jobs(master, take):
            take.status = "rendering"
            return True
        if master.activeSceneTakeId:
            master.activeSceneTakeId = None
            return True
        return False
    take.batches = capture_members_for_active_take(master, take)
    generating = scene_has_live_render(master)
    failed = any(str(getattr(b, "status", "") or "") in {"Failed", "Cancelled"} for b in (master.batchBlocks or []))
    expected = {m.batchId for m in take.batches}
    have = {m.batchId for m in take.batches if m.assetId}
    if generating:
        return True
    if failed or (expected and have != expected):
        take.status = "incomplete" if have else "cancelled"
        take.completedAt = _now()
        master.activeSceneTakeId = None
        _heal_current_take_pointer(master, take)
        return True
    if expected and have == expected:
        take.status = "ready"
        take.completedAt = _now()
        if len(take.batches) == 1 and take.batches[0].assetId:
            take.resultAssetId = take.batches[0].assetId
        master.activeSceneTakeId = None
        _heal_current_take_pointer(master, take)
        # Keep current take's live playable if this new take is not current.
        current = current_scene_take(master)
        if current and current.id != take.id:
            apply_take_to_live_batches(master, current)
        return True
    return True


def refresh_current_take_after_repair(
    master: SceneTimelineMaster,
    batch_id: str,
    *,
    asset_id: str | None,
    candidate_id: str | None = None,
    batch_take_id: str | None = None,
    retake_id: str | None = None,
) -> bool:
    """Re-Take / approve updates the CURRENT whole-scene Take only."""
    take = current_scene_take(master)
    if take is None or take.status == "rendering":
        return False
    # Historical Takes stay immutable. An incomplete/cancelled current Take is
    # a finished record, not the destination for a later Take's approve.
    if take.status in {"incomplete", "cancelled"}:
        return False
    asset = str(asset_id or "").strip()
    if not asset:
        return False
    changed = False
    for member in take.batches:
        if member.batchId != batch_id:
            continue
        member.assetId = asset
        member.candidateId = candidate_id or member.candidateId
        member.batchTakeId = batch_take_id or member.batchTakeId
        member.status = "repaired"
        changed = True
        break
    if retake_id and retake_id not in (take.retakeIds or []):
        take.retakeIds = list(take.retakeIds or []) + [retake_id]
        changed = True
    if changed and len(take.batches) == 1:
        take.resultAssetId = asset
    return changed


def assemble_take_result(
    db: Session,
    project_id: str,
    scene_id: str,
    take: SceneTake,
) -> str | None:
    """Join take batch assets into one scene result. Does not rewrite live stitch."""
    members = [m for m in sorted(take.batches, key=lambda x: int(x.order or 0)) if m.assetId]
    if not members:
        return take.resultAssetId
    if len(members) == 1:
        take.resultAssetId = members[0].assetId
        return take.resultAssetId
    if take.resultAssetId:
        return take.resultAssetId
    try:
        from pathlib import Path

        from ..config import settings
        from ..generation_tools.lineage import register_derived_asset
        from ..media_ops import stitch_videos
        from .scene_stitch import resolve_asset_file

        paths: list[Path] = []
        for member in members:
            path = resolve_asset_file(db, project_id, str(member.assetId))
            if path is None:
                return None
            paths.append(path)
        tmp_dir = settings.data_dir / "projects" / project_id / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_out = tmp_dir / f"scene_take_{take.label}_{take.id[-8:]}.mp4"
        stitch_videos(paths, tmp_out, fps=24)
        if not tmp_out.is_file() or tmp_out.stat().st_size <= 0:
            return None
        asset = register_derived_asset(
            db,
            project_id=project_id,
            source_path=tmp_out,
            kind="video",
            tag="scene_take_result",
            parent_asset_id=str(members[0].assetId),
            op="scene_take_stitch",
            model="scene_take_stitch",
            prompt_meta={
                "sceneId": scene_id,
                "takeId": take.id,
                "takeLabel": scene_take_display(take.label),
                "batchIds": [m.batchId for m in members],
                "sourceAssetIds": [m.assetId for m in members],
            },
            filename=f"scene_take_{take.label}_{scene_id[:8]}.mp4",
        )
        take.resultAssetId = asset.id
        try:
            tmp_out.unlink(missing_ok=True)
        except Exception:
            pass
        return take.resultAssetId
    except Exception:
        logger.exception("assemble_take_result failed for %s", take.id)
        return None


def _batch_has_playable_output(batch: Any) -> bool:
    clip = getattr(batch, "approvedClip", None)
    if clip and str(getattr(clip, "assetId", None) or "").strip():
        return True
    return any(
        str(getattr(cand, "assetId", None) or "").strip()
        for cand in (getattr(batch, "candidateVersions", None) or [])
    )


def iter_active_render_jobs(master: SceneTimelineMaster) -> list[tuple[Any, Any]]:
    """Jobs that belong to the active render identity — never the selected Take card."""
    active = active_scene_take(master)
    rows: list[tuple[Any, Any]] = []
    for batch in master.batchBlocks or []:
        in_flight = str(getattr(batch, "status", "") or "") in {"Generating", "Waiting", "Queued"}
        for job in getattr(batch, "generationJobs", None) or []:
            status = str(getattr(job, "status", "") or "").lower()
            if status not in _LIVE_CANCEL_JOB:
                continue
            job_take = str(getattr(job, "sceneTakeId", None) or "")
            if active and job_take and job_take != active.id:
                continue
            if active and job_take == active.id:
                rows.append((batch, job))
                continue
            if not job_take and in_flight:
                rows.append((batch, job))
                continue
            # Active pointer missing or stale: still halt the live bound job.
            if active is None and job_take:
                rows.append((batch, job))
    return rows


def cancel_active_render(master: SceneTimelineMaster) -> dict[str, Any]:
    """Cancel the active Take's jobs only. Completed Takes / prompts / refs stay."""
    active = active_scene_take(master)
    preserved_take_ids = [
        t.id
        for t in (master.sceneTakes or [])
        if active is None or t.id != active.id
    ]
    jobs = iter_active_render_jobs(master)
    job_ids = [str(job.id) for _batch, job in jobs]
    queue_ids = [str(getattr(job, "queueJobId", None) or job.id) for _batch, job in jobs]
    affected: list[str] = []
    for _batch, job in jobs:
        job.status = "cancelled"
        if getattr(job, "phase", None):
            job.phase = "cancelled"
    touched = {id(batch) for batch, _job in jobs}
    for batch in master.batchBlocks or []:
        status = str(getattr(batch, "status", "") or "")
        if status not in {"Generating", "Waiting", "Queued"}:
            continue
        if id(batch) not in touched and status == "Queued" and not batch_has_provider_live_job(batch):
            # Sequential leftover for the active take — drop queue, keep history.
            batch.status = "CandidateReady" if _batch_has_playable_output(batch) else "Draft"
            batch.pendingSnapshotId = None
            affected.append(batch.id)
            continue
        if id(batch) not in touched and status != "Queued":
            continue
        if _batch_has_playable_output(batch):
            batch.status = "CandidateReady"
        elif status == "Queued":
            batch.status = "Draft"
        else:
            batch.status = "Cancelled"
        batch.pendingSnapshotId = None
        affected.append(batch.id)
    cancelled_take_id = active.id if active is not None else None
    if active is not None:
        active.status = "cancelling"
    mark_active_take_stopped(master)
    return {
        "cancelledTakeId": cancelled_take_id,
        "cancelledJobIds": job_ids,
        "queueJobIds": queue_ids,
        "affectedBatchIds": list(dict.fromkeys(affected)),
        "preservedTakeIds": preserved_take_ids,
        "jobs": jobs,
    }


def mark_active_take_stopped(master: SceneTimelineMaster) -> None:
    take = active_scene_take(master)
    if take is None:
        return
    if take.status == "cancelling":
        take.status = "incomplete" if any(m.assetId for m in take.batches) else "cancelled"
    else:
        take.status = "incomplete" if any(m.assetId for m in take.batches) else "cancelled"
    take.completedAt = _now()
    master.activeSceneTakeId = None
    current = current_scene_take(master)
    if current and current.id != take.id:
        apply_take_to_live_batches(master, current)


def start_new_take(
    db: Session,
    project_id: str,
    scene_id: str,
) -> dict[str, Any]:
    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return payload
    master = SceneTimelineMaster.model_validate(payload["master"])
    ensure_scene_takes(master)
    sync_rendering_take(master)
    store.save_master(db, project_id, scene_id, master, touch_batches=False)
    if take_render_is_live(master):
        live = active_scene_take(master)
        return {
            "ok": False,
            "error": "TAKE_ALREADY_RENDERING",
            "message": f"{scene_take_display(live.label if live else 'Take')} is still rendering.",
            "mock": False,
        }
    if not master.batchBlocks:
        return {"ok": False, "error": "NO_BATCHES", "message": "Add scene batches before creating a new take.", "mock": False}

    take = allocate_rendering_take(master)
    store.save_master(db, project_id, scene_id, master, touch_batches=False)

    from . import orchestrator

    gen = orchestrator.generate_scene(
        db,
        project_id,
        scene_id,
        scope="full",
        force_all=True,
        scene_take_id=take.id,
        take_intent="NEW_TAKE",
    )
    payload2 = store.load_master(db, project_id, scene_id)
    if payload2.get("ok"):
        master = SceneTimelineMaster.model_validate(payload2["master"])
        live = _take_or_error(master, take.id)
        if not gen.get("ok") and live is not None and live.status == "rendering":
            if not take_has_live_jobs(master, live):
                live.status = "incomplete" if any(m.assetId for m in live.batches) else "cancelled"
                live.completedAt = _now()
                master.activeSceneTakeId = None
        sync_rendering_take(master)
        store.save_master(db, project_id, scene_id, master, touch_batches=False)
        take = _take_or_error(master, take.id) or take
    return {
        "ok": True,
        "takeAllocated": True,
        "generationStarted": bool(gen.get("ok")),
        "take": take.model_dump(),
        "takeLabel": scene_take_display(take.label),
        "generation": gen,
        "master": master.model_dump(),
        "message": gen.get("message") or f"Rendering {scene_take_display(take.label)}.",
        "mock": False,
        **({k: v for k, v in gen.items() if k in {"error", "errors", "findings"}} if not gen.get("ok") else {}),
    }


def make_current_take(db: Session, project_id: str, scene_id: str, take_id: str) -> dict[str, Any]:
    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return payload
    master = SceneTimelineMaster.model_validate(payload["master"])
    ensure_scene_takes(master)
    take = _take_or_error(master, take_id)
    if take is None:
        return {"ok": False, "error": "TAKE_NOT_FOUND", "message": "That take is not on this scene.", "mock": False}
    if take.status == "rendering":
        return {
            "ok": False,
            "error": "TAKE_NOT_READY",
            "message": f"{scene_take_display(take.label)} is still rendering.",
            "mock": False,
        }
    if take.status in {"cancelled", "incomplete"} and not any(m.assetId for m in take.batches):
        return {
            "ok": False,
            "error": "TAKE_INCOMPLETE",
            "message": f"{scene_take_display(take.label)} has no finished scene yet.",
            "mock": False,
        }
    if take.status == "ready" and not take.resultAssetId and all(m.assetId for m in take.batches):
        assemble_take_result(db, project_id, scene_id, take)
    apply_take_to_live_batches(master, take)
    store.save_master(db, project_id, scene_id, master, touch_batches=False)
    # Visual re-placement: the placed video_clips must follow the newly
    # current take (approvedClip precedence was stale after a Take switch —
    # Cade Scene 3 showed Take A assets on the track while Take N was
    # current). place_approved_batches_on_timeline now prefers current-take
    # membership, so this refreshes the track to the take the creator chose.
    try:
        from .generation.completion import place_approved_batches_on_timeline

        place_approved_batches_on_timeline(db, project_id, scene_id)
    except Exception:
        pass
    return {
        "ok": True,
        "currentSceneTakeId": take.id,
        "take": take.model_dump(),
        "master": master.model_dump(),
        "mock": False,
    }


def delete_scene_take(db: Session, project_id: str, scene_id: str, take_id: str) -> dict[str, Any]:
    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return payload
    master = SceneTimelineMaster.model_validate(payload["master"])
    take = _take_or_error(master, take_id)
    if take is None:
        return {"ok": False, "error": "TAKE_NOT_FOUND", "message": "That take is not on this scene.", "mock": False}
    reason = delete_block_reason(master, take)
    if reason:
        return {"ok": False, "error": "TAKE_DELETE_BLOCKED", "message": reason, "mock": False}
    master.sceneTakes = [t for t in master.sceneTakes if t.id != take.id]
    store.save_master(db, project_id, scene_id, master, touch_batches=False)
    return {"ok": True, "deletedTakeId": take.id, "master": master.model_dump(), "mock": False}


def resume_scene_take(db: Session, project_id: str, scene_id: str, take_id: str | None = None) -> dict[str, Any]:
    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return payload
    master = SceneTimelineMaster.model_validate(payload["master"])
    take = _take_or_error(master, take_id) if take_id else None
    if take is None:
        take = next((t for t in reversed(master.sceneTakes or []) if t.status in {"incomplete", "cancelled"}), None)
    if take is None:
        return {"ok": False, "error": "NO_INCOMPLETE_TAKE", "message": "There is no incomplete take to resume.", "mock": False}
    done_ids = {m.batchId for m in take.batches if m.assetId}
    resume_ids = [b.id for b in master.batchBlocks if b.id not in done_ids]
    if not resume_ids:
        take.status = "ready"
        take.completedAt = _now()
        store.save_master(db, project_id, scene_id, master, touch_batches=False)
        return {"ok": True, "take": take.model_dump(), "message": f"{scene_take_display(take.label)} is already complete.", "mock": False}
    take.status = "rendering"
    master.activeSceneTakeId = take.id
    store.save_master(db, project_id, scene_id, master, touch_batches=False)
    from . import orchestrator
    from .contracts import CancelRequest

    orchestrator.cancel_scene(
        db,
        project_id,
        scene_id,
        CancelRequest(action="resume_incomplete_only", batchBlockIds=resume_ids),
    )
    gen = orchestrator.generate_scene(
        db,
        project_id,
        scene_id,
        scope="selected",
        batch_ids=resume_ids,
        force_all=True,
        scene_take_id=take.id,
        take_intent="RENDER_CURRENT_TAKE",
    )
    return {
        "ok": bool(gen.get("ok")),
        "take": take.model_dump(),
        "generation": gen,
        "message": f"Resuming {scene_take_display(take.label)}.",
        "mock": False,
    }


def list_scene_takes_payload(master: SceneTimelineMaster) -> dict[str, Any]:
    ensure_scene_takes(master)
    pub = master.scenePublish
    published_id = str(getattr(pub, "takeId", None) or "") if pub else ""
    rows = []
    for take in master.sceneTakes or []:
        rows.append(
            {
                **take.model_dump(),
                "displayLabel": scene_take_display(take.label),
                "current": take.id == master.currentSceneTakeId,
                "published": take.id == published_id or bool(take.publishedAssetId),
                "deleteBlocked": delete_block_reason(master, take),
            }
        )
    return {
        "ok": True,
        "currentSceneTakeId": master.currentSceneTakeId,
        "activeSceneTakeId": master.activeSceneTakeId,
        "publishedTakeId": published_id or None,
        "takes": rows,
        "mock": False,
    }


def resolve_take_preview_assets(master: SceneTimelineMaster, take_id: str | None) -> list[dict[str, Any]]:
    take = _take_or_error(master, take_id) if take_id else current_scene_take(master)
    if take is None:
        return []
    if take.resultAssetId and len([m for m in take.batches if m.assetId]) <= 1:
        return [{"batchId": take.batches[0].batchId if take.batches else None, "assetId": take.resultAssetId, "durationSec": take.quality.durationSec}]
    return [
        {"batchId": m.batchId, "assetId": m.assetId, "durationSec": m.durationSec}
        for m in sorted(take.batches, key=lambda x: int(x.order or 0))
        if m.assetId
    ]
