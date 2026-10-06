"""P6 Timeline Generation Reconciler — bounce-durable terminalization.

Law: Job provider-terminal OR durable output_path/output_asset_id for a Timeline
generationJobs queue id ⇒ batch must leave Generating. Never auto-regen.
Never rematerialize windows. Never invent CandidateReady on Omni miss.

Terminal map:
  MEDIA_COMPLETE_QC_PENDING → QC_Pending
  READY → CandidateReady
  FAILED_GENERATION → Failed
  FAILED_QC → NeedsDialogueRetake
  CANCELLED → Cancelled
"""
from __future__ import annotations

import logging
from typing import Any

from ...db import SessionLocal
from ..contracts import SceneTimelineMaster

logger = logging.getLogger(__name__)

_TERMINAL_BATCH = frozenset({
    "Approved",
    "CandidateReady",
    "NeedsDialogueRetake",
    "QC_Pending",
    "QC_RetryRequired",
    "Failed",
    "Cancelled",
})
_IN_FLIGHT_BATCH = frozenset({"Generating", "Waiting", "Queued"})
_JOB_DONE = frozenset({"done", "completed"})
_JOB_FAIL = frozenset({"failed", "error"})
_JOB_CANCEL = frozenset({"cancelled", "canceled"})


def _job_row(db: Any, queue_job_id: str) -> Any | None:
    if not queue_job_id:
        return None
    from ...db import Job
    return db.query(Job).filter(Job.id == queue_job_id).one_or_none()


def _params(job: Any) -> dict[str, Any]:
    raw = getattr(job, "params_json", None)
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        import json
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}


def _output_asset_id(job: Any, params: dict[str, Any]) -> str | None:
    aid = params.get("output_asset_id")
    if isinstance(aid, str) and aid.strip():
        return aid.strip()
    ids = params.get("outputAssetIds") or []
    if isinstance(ids, list) and ids:
        return str(ids[0])
    return None


def _ensure_candidate(batch: Any, *, asset_id: str, queue_job_id: str, execution_snapshot_id: str | None) -> str | None:
    """Bind durable asset onto batch if missing. Returns candidate id."""
    from uuid import uuid4
    from ..contracts import CandidateVersion

    for cand in (getattr(batch, "candidateVersions", None) or []):
        if str(getattr(cand, "assetId", None) or "") == asset_id:
            batch.currentTakeAssetId = asset_id
            if getattr(cand, "takeId", None):
                batch.currentTakeId = cand.takeId
                batch.activeTakeId = cand.takeId
            return str(getattr(cand, "id", None) or "")
    take_id = f"take_{uuid4().hex[:12]}"
    cand_id = f"cand_{uuid4().hex[:12]}"
    cand = CandidateVersion(
        id=cand_id,
        executionSnapshotId=execution_snapshot_id or f"snap_{uuid4().hex[:12]}",
        assetId=asset_id,
        label="Reconciled",
        generatedDuration=float(getattr(getattr(batch, "duration", None), "plannedDuration", None) or 15.0),
        takeId=take_id,
        parentTakeId=None,
        incomingBridgeId=getattr(batch, "incomingBridgeId", None),
        continuityAware=True,
    )
    batch.candidateVersions = list(getattr(batch, "candidateVersions", None) or []) + [cand]
    batch.currentTakeId = take_id
    batch.activeTakeId = take_id
    batch.currentTakeAssetId = asset_id
    return cand_id


def reconcile_batch_from_job(
    db: Any,
    *,
    project_id: str,
    scene_id: str,
    batch_id: str,
    queue_job_id: str,
) -> dict[str, Any]:
    from .. import store

    job = _job_row(db, queue_job_id)
    if job is None:
        return {"ok": False, "error": "JOB_NOT_FOUND", "queueJobId": queue_job_id}
    status = str(getattr(job, "status", "") or "").lower()
    params = _params(job)
    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return {"ok": False, "error": "MASTER_LOAD_FAILED"}
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = next((b for b in master.batchBlocks if b.id == batch_id), None)
    if batch is None:
        return {"ok": False, "error": "BATCH_NOT_FOUND", "batchId": batch_id, "note": "master missing batch — refuse invent"}

    if batch.status in _TERMINAL_BATCH and status in _JOB_DONE:
        # Already terminal — still sync job ref if stuck running
        changed = False
        for jref in batch.generationJobs or []:
            if str(getattr(jref, "queueJobId", None) or "") == queue_job_id:
                if str(jref.status or "").lower() in {"running", "queued", "pending"}:
                    jref.status = "completed"
                    jref.progress = 1.0
                    changed = True
        if changed:
            store.save_master(db, project_id, scene_id, master, touch_batches=False)
        return {"ok": True, "skipped": True, "reason": "already_terminal", "batchStatus": batch.status}

    if batch.status not in _IN_FLIGHT_BATCH and status in _JOB_DONE:
        return {"ok": True, "skipped": True, "reason": "batch_not_in_flight", "batchStatus": batch.status}

    # Fail / cancel
    if status in _JOB_FAIL:
        for jref in batch.generationJobs or []:
            if str(getattr(jref, "queueJobId", None) or "") == queue_job_id:
                jref.status = "failed"
        if batch.status not in _TERMINAL_BATCH:
            batch.status = "Failed"
        store.save_master(db, project_id, scene_id, master)
        return {"ok": True, "batchStatus": batch.status, "mapped": "FAILED_GENERATION"}

    if status in _JOB_CANCEL:
        for jref in batch.generationJobs or []:
            if str(getattr(jref, "queueJobId", None) or "") == queue_job_id:
                jref.status = "cancelled"
        if batch.status not in _TERMINAL_BATCH:
            keep = bool(getattr(getattr(batch, "approvedClip", None), "assetId", None))
            batch.status = "Approved" if keep else "Cancelled"
        store.save_master(db, project_id, scene_id, master)
        return {"ok": True, "batchStatus": batch.status, "mapped": "CANCELLED"}

    if status not in _JOB_DONE:
        return {"ok": True, "skipped": True, "reason": "job_not_terminal", "jobStatus": status}

    # Media complete. The job row flips to done before the Library asset id
    # is written. Closing the batch in that gap makes the open take look
    # empty ("has no finished scene yet") even though the picture is about
    # to be saved. Stay in flight until the asset id exists.
    asset_id = _output_asset_id(job, params)
    if not asset_id:
        return {
            "ok": True,
            "skipped": True,
            "reason": "awaiting_library_asset",
            "queueJobId": queue_job_id,
        }

    snap_id = None
    for jref in batch.generationJobs or []:
        if str(getattr(jref, "queueJobId", None) or "") == queue_job_id:
            jref.status = "completed"
            jref.progress = 1.0
            snap_id = getattr(jref, "executionSnapshotId", None)

    if asset_id:
        _ensure_candidate(batch, asset_id=asset_id, queue_job_id=queue_job_id, execution_snapshot_id=snap_id)

    # Do not invent CandidateReady — QC pending until Omni/retry.
    batch.status = "QC_Pending"
    store.save_master(db, project_id, scene_id, master)
    return {
        "ok": True,
        "batchStatus": "QC_Pending",
        "mapped": "MEDIA_COMPLETE_QC_PENDING",
        "assetId": asset_id,
        "queueJobId": queue_job_id,
        "autoRegen": False,
    }


def queue_job_id_for_reconcile(batch: Any) -> str | None:
    """Which queue job may close this batch.

    A later window staged for the sequential chain is Queued with a new
    pending snapshot before its job exists. The newest generationJobs row is
    often the previous take's completed job. Closing on that row marks the
    window QC_Pending, drops it from the chain, and the Preview Monitor goes
    idle while the scene still owes windows.
    """
    pending = str(getattr(batch, "pendingSnapshotId", None) or "").strip()
    jobs = list(getattr(batch, "generationJobs", None) or [])
    if str(getattr(batch, "status", "") or "") == "Queued" and pending:
        for jref in reversed(jobs):
            if str(getattr(jref, "executionSnapshotId", None) or "") != pending:
                continue
            qid = str(getattr(jref, "queueJobId", None) or "")
            if qid:
                return qid
        return None
    for jref in reversed(jobs):
        qid = str(getattr(jref, "queueJobId", None) or "")
        if qid:
            return qid
    return None


def reconcile_scene(db: Any, project_id: str, scene_id: str) -> dict[str, Any]:
    from .. import store

    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return {"ok": False, "error": "MASTER_LOAD_FAILED"}
    master = SceneTimelineMaster.model_validate(payload["master"])
    results = []
    for batch in master.batchBlocks or []:
        if batch.status not in _IN_FLIGHT_BATCH:
            continue
        qid = queue_job_id_for_reconcile(batch)
        if not qid:
            continue
        r = reconcile_batch_from_job(
            db, project_id=project_id, scene_id=scene_id, batch_id=batch.id, queue_job_id=qid
        )
        results.append({"batchId": batch.id, **r})
    return {"ok": True, "reconciled": results}


def reconcile_all_open_timeline_jobs(db: Any | None = None) -> dict[str, Any]:
    """Startup / bounce recovery: scan done Jobs with timelineGeneration still open on master."""
    owns = db is None
    if owns:
        db = SessionLocal()
    try:
        from ...db import Job
        import json
        rows = (
            db.query(Job)
            .filter(Job.status.in_(["done", "completed", "failed", "cancelled"]))
            .order_by(Job.updated_at.desc())
            .limit(200)
            .all()
        )
        out = []
        seen = set()
        for job in rows:
            params = _params(job)
            if not params.get("timelineGeneration"):
                continue
            project_id = str(getattr(job, "project_id", None) or params.get("projectId") or "")
            scene_id = str(getattr(job, "scene_id", None) or params.get("sceneId") or "")
            batch_id = str(params.get("batchBlockId") or params.get("batchId") or "")
            key = (project_id, scene_id, batch_id, job.id)
            if not project_id or not scene_id or not batch_id or key in seen:
                continue
            seen.add(key)
            try:
                r = reconcile_batch_from_job(
                    db,
                    project_id=project_id,
                    scene_id=scene_id,
                    batch_id=batch_id,
                    queue_job_id=str(job.id),
                )
                out.append(r)
            except Exception as exc:
                logger.exception("timeline reconcile failed job=%s", job.id)
                out.append({"ok": False, "error": str(exc), "queueJobId": job.id})
        return {"ok": True, "count": len(out), "results": out}
    finally:
        if owns:
            db.close()


def refuse_master_structure_collapse(
    *,
    previous: dict[str, Any] | None,
    incoming: dict[str, Any] | SceneTimelineMaster | None,
) -> dict[str, Any] | None:
    """Return error dict if incoming would wipe multi-batch master to a foreign single Draft."""
    if not previous or incoming is None:
        return None
    prev_blocks = list(previous.get("batchBlocks") or [])
    prev_ids = [str(b.get("id") or "") for b in prev_blocks if str(b.get("id") or "")]
    if len(prev_ids) < 2:
        return None
    if isinstance(incoming, SceneTimelineMaster):
        next_blocks = list(incoming.batchBlocks or [])
        next_ids = [str(b.id) for b in next_blocks]
        next_status0 = str(next_blocks[0].status) if next_blocks else ""
    else:
        next_blocks = list((incoming or {}).get("batchBlocks") or [])
        next_ids = [str(b.get("id") or "") for b in next_blocks if str(b.get("id") or "")]
        next_status0 = str((next_blocks[0] or {}).get("status") or "") if next_blocks else ""
    if len(next_ids) >= 2:
        return None
    # Collapse to 0/1 batch
    if not next_ids:
        return {
            "ok": False,
            "error": "MASTER_STRUCTURE_COLLAPSE_REFUSED",
            "message": "Refusing to clear multi-batch Timeline master.",
            "previousBatchIds": prev_ids,
            "incomingBatchIds": next_ids,
            "mock": False,
        }
    if next_ids[0] not in prev_ids:
        return {
            "ok": False,
            "error": "MASTER_STRUCTURE_COLLAPSE_REFUSED",
            "message": "Refusing to replace multi-batch master with a different single batch (bounce wipe guard).",
            "previousBatchIds": prev_ids,
            "incomingBatchIds": next_ids,
            "mock": False,
        }
    # Same id kept but siblings dropped — still refuse
    return {
        "ok": False,
        "error": "MASTER_STRUCTURE_COLLAPSE_REFUSED",
        "message": "Refusing to drop sibling execution windows from Timeline master.",
        "previousBatchIds": prev_ids,
        "incomingBatchIds": next_ids,
        "mock": False,
    }
