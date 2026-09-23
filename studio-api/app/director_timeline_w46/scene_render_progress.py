"""Scene-level multi-batch render progress for Timeline UI chrome.

Pure derivation from batchBlocks — no side effects. Status strings match
creator-facing copy like:
  Render Batch 1/3 — In Progress — 42%
  Scene Render Complete
"""

from __future__ import annotations

from typing import Any


COMPLETE_STATUSES = frozenset(
    {
        "Approved",
        "CandidateReady",
        "ApprovedConfigurationChanged",
        "RegenerationRecommended",
    }
)
# RENDER != SCENE_FINISHED: dialogue QC fail keeps the batch incomplete.
INCOMPLETE_DIALOGUE_STATUSES = frozenset({"NeedsDialogueRetake"})
# Omni infra miss: media may exist, but SCENE_FINISHED blocked — not a dialogue retake.
INCOMPLETE_QC_INFRA_STATUSES = frozenset({"QC_Pending", "QC_RetryRequired"})
INCOMPLETE_QC_STATUSES = INCOMPLETE_DIALOGUE_STATUSES | INCOMPLETE_QC_INFRA_STATUSES
ACTIVE_STATUSES = frozenset({"Generating", "Queued", "Waiting"})
FAILED_STATUSES = frozenset({"Failed", "Cancelled"})
_PROVIDER_LIVE_JOB = frozenset({"running", "submitted", "pending"})


def _batch_has_provider_live_job(batch: Any) -> bool:
    if getattr(batch, "activeJobId", None):
        return True
    for job in getattr(batch, "generationJobs", None) or []:
        if str(getattr(job, "status", "") or "").lower() in _PROVIDER_LIVE_JOB:
            return True
    return False


def _batch_awaiting_sequential_slot(batch: Any) -> bool:
    """Staged for Generate Scene; waiting on Omni / last-frame / the next slot."""
    if str(getattr(batch, "status", "") or "") != "Queued":
        return False
    if _batch_has_provider_live_job(batch):
        return False
    return bool(str(getattr(batch, "pendingSnapshotId", None) or "").strip())


def _scene_queue_is_live(batches: list[Any]) -> bool:
    """Queued-only without Generating, a provider job, or a staged snapshot is leftover."""
    generating = False
    queued_live = False
    for batch in batches:
        status = str(getattr(batch, "status", "") or "")
        if status in {"Generating", "Waiting"}:
            generating = True
        if status == "Queued" and (
            _batch_has_provider_live_job(batch) or _batch_awaiting_sequential_slot(batch)
        ):
            queued_live = True
    return generating or queued_live


def _batch_progress(batch: Any) -> float | None:
    jobs = list(getattr(batch, "generationJobs", None) or [])
    active = [
        j
        for j in jobs
        if str(getattr(j, "status", "") or "") in ("queued", "running", "pending")
    ]
    pool = active or jobs
    if not pool:
        return None
    vals: list[float] = []
    for job in pool:
        try:
            vals.append(max(0.0, min(1.0, float(getattr(job, "progress", 0.0) or 0.0))))
        except (TypeError, ValueError):
            continue
    if not vals:
        return None
    return sum(vals) / len(vals)


def derive_scene_render_progress(master: Any) -> dict[str, Any]:
    batches = sorted(
        list(getattr(master, "batchBlocks", None) or []),
        key=lambda b: (int(getattr(b, "order", 0) or 0), str(getattr(b, "createdAt", "") or "")),
    )
    total = len(batches)
    if total == 0:
        return {
            "totalBatches": 0,
            "completedBatches": 0,
            "dialogueNeedsRetake": 0,
            "qcInfraPending": 0,
            "qcInfraBlocking": False,
            "failedBatches": 0,
            "activeBatchIndex": None,
            "activeBatchId": None,
            "activeBatchLabel": None,
            "activeStatus": None,
            "progressPercent": None,
            "phase": "idle",
            "statusLabel": "No batches",
            "stitchReady": False,
            "queueActive": False,
            "haltedOnFailure": False,
        }

    completed = 0
    failed = 0
    dialogue_needs_retake = 0
    qc_infra_pending = 0
    active_idx = None
    active_batch = None
    for i, batch in enumerate(batches):
        status = str(getattr(batch, "status", "") or "")
        if status in COMPLETE_STATUSES:
            completed += 1
        elif status in INCOMPLETE_DIALOGUE_STATUSES:
            # Content speech/lang fail — retake path (NOT Omni infra).
            dialogue_needs_retake += 1
        elif status in INCOMPLETE_QC_INFRA_STATUSES:
            # Omni infra miss — keep asset; retry QC only; never NeedsDialogueRetake.
            qc_infra_pending += 1
        elif status in FAILED_STATUSES:
            failed += 1
        if status == "Generating" and active_batch is None:
            active_idx = i + 1
            active_batch = batch
        elif status == "Queued" and active_batch is None:
            # Prefer Generating; else first live or staged-Queued is the waiting slot.
            if active_idx is None and (
                _batch_has_provider_live_job(batch) or _batch_awaiting_sequential_slot(batch)
            ):
                active_idx = i + 1
                active_batch = batch

    # If Generating exists, prefer it over Queued chosen above.
    for i, batch in enumerate(batches):
        if str(getattr(batch, "status", "") or "") == "Generating":
            active_idx = i + 1
            active_batch = batch
            break

    queue_active = _scene_queue_is_live(batches)
    halted = failed > 0 and any(str(getattr(b, "status", "") or "") == "Failed" for b in batches) and not queue_active
    all_complete = completed == total and total > 0
    dialogue_blocking = dialogue_needs_retake > 0 and not queue_active and (completed + dialogue_needs_retake + qc_infra_pending + failed) == total
    qc_infra_blocking = qc_infra_pending > 0 and not queue_active and (completed + dialogue_needs_retake + qc_infra_pending + failed) == total
    # Stitch still requires Approved takes for every batch (Scene 12 HOLD).
    stitch_ready = all(
        str(getattr(b, "status", "") or "") in ("Approved", "ApprovedConfigurationChanged", "RegenerationRecommended")
        and bool(getattr(getattr(b, "approvedClip", None), "assetId", None))
        for b in batches
    )

    progress_frac = _batch_progress(active_batch) if active_batch is not None else None
    # Generating with no grounded job fraction is phase-only — do not invent 0%.
    if progress_frac is not None and float(progress_frac) <= 0:
        progress_frac = None
    progress_pct = None if progress_frac is None else int(round(progress_frac * 100))

    if dialogue_blocking:
        phase = "dialogue_retake_required"
        status_label = "Scene NOT FINISHED ? Dialogue Re-Take Required"
    elif all_complete and not queue_active:
        phase = "complete"
        status_label = "Scene Render Complete"
    elif halted:
        phase = "failed"
        failed_batch = next(
            (b for b in batches if str(getattr(b, "status", "") or "") == "Failed"),
            None,
        )
        label = getattr(failed_batch, "label", None) or "Batch"
        status_label = f"Scene Render Halted — {label} Failed"
    elif active_batch is not None and str(getattr(active_batch, "status", "") or "") == "Generating":
        phase = "rendering"
        pct_bit = f" — {progress_pct}%" if progress_pct is not None else ""
        status_label = f"Render Batch {active_idx}/{total} — In Progress{pct_bit}"
    elif active_batch is not None and str(getattr(active_batch, "status", "") or "") == "Queued":
        if _batch_awaiting_sequential_slot(active_batch):
            phase = "preparing"
            status_label = f"Render Batch {active_idx}/{total} — Preparing"
        else:
            phase = "queued"
            status_label = f"Render Batch {active_idx}/{total} — Queued"
    elif queue_active:
        phase = "rendering"
        status_label = f"Render Batch {completed + 1}/{total} — In Progress"
    else:
        phase = "idle"
        status_label = f"{completed}/{total} batches complete" if completed else "Ready to generate"

    return {
        "totalBatches": total,
        "completedBatches": completed,
        "dialogueNeedsRetake": dialogue_needs_retake,
        "qcInfraPending": qc_infra_pending,
        "qcInfraBlocking": qc_infra_blocking,
        "sceneFinished": bool(total and completed == total and dialogue_needs_retake == 0 and qc_infra_pending == 0 and failed == 0),
        "failedBatches": failed,
        "activeBatchIndex": active_idx,
        "activeBatchId": getattr(active_batch, "id", None) if active_batch else None,
        "activeBatchLabel": getattr(active_batch, "label", None) if active_batch else None,
        "activeStatus": str(getattr(active_batch, "status", "") or "") if active_batch else None,
        "progressPercent": progress_pct,
        "phase": phase,
        "statusLabel": status_label,
        "stitchReady": bool(stitch_ready),
        "queueActive": bool(queue_active),
        "haltedOnFailure": bool(halted),
    }
