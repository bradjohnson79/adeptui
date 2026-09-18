"""Current generated take + scene generation progress for Timeline multi-batch.

Retake/range/inpaint must use the CURRENT GENERATED take (latest candidate with
assetId), never an approval-only gate. approvedClip is legacy fallback only.
"""

from __future__ import annotations

from typing import Any


def _cand_asset(cand: Any) -> str:
    return str(getattr(cand, "assetId", None) or "").strip()


def _latest_candidate_with_asset(batch: Any) -> Any | None:
    cands = [c for c in (getattr(batch, "candidateVersions", None) or []) if _cand_asset(c)]
    if not cands:
        return None
    return max(
        cands,
        key=lambda c: (str(getattr(c, "createdAt", None) or ""), str(getattr(c, "id", None) or "")),
    )


def resolve_current_take(batch: Any, master: Any | None = None) -> dict[str, Any] | None:
    """Return {takeId, assetId, candidateId, source} for the current generated take.

    Priority (GENERATED first — not approval):
      0. current whole-scene Take membership when master is provided
      1. latest candidateVersions entry with assetId
      2. activeTakeId matching a candidate with assetId
      3. approvedClip.assetId (legacy fallback only)

    REBUILD LAW: identity must be explicit. There is no priority-4 "scan the
    batch's visualClips and return any clip" fallback — a generic asset
    lookup could surface a manual/foreign clip as the take's identity, and
    downstream gates (require_current_take, inpaint source) would then derive
    provenance from an unowned asset. No asset → None → callers fail closed.
    """
    if batch is None:
        return None
    if master is not None:
        try:
            from .scene_takes import current_scene_take

            scene_take = current_scene_take(master)
            batch_id = str(getattr(batch, "id", "") or "")
            if scene_take and scene_take.status != "rendering":
                member = next(
                    (
                        m
                        for m in (scene_take.batches or [])
                        if str(m.batchId) == batch_id and str(m.assetId or "").strip()
                    ),
                    None,
                )
                if member is not None:
                    return {
                        "takeId": member.batchTakeId,
                        "assetId": str(member.assetId).strip(),
                        "candidateId": member.candidateId,
                        "source": "scene_take",
                        "candidate": None,
                        "sceneTakeId": scene_take.id,
                    }
        except Exception:
            pass

    candidates = list(getattr(batch, "candidateVersions", None) or [])

    latest = _latest_candidate_with_asset(batch)
    if latest is not None:
        return {
            "takeId": str(getattr(latest, "takeId", None) or "") or None,
            "assetId": _cand_asset(latest),
            "candidateId": str(getattr(latest, "id", None) or "") or None,
            "source": "latest_candidate",
            "candidate": latest,
        }

    active_id = str(getattr(batch, "activeTakeId", None) or "").strip()
    if active_id:
        for cand in candidates:
            if str(getattr(cand, "takeId", None) or "") == active_id and _cand_asset(cand):
                return {
                    "takeId": active_id,
                    "assetId": _cand_asset(cand),
                    "candidateId": str(getattr(cand, "id", None) or "") or None,
                    "source": "active",
                    "candidate": cand,
                }

    approved = getattr(batch, "approvedClip", None)
    approved_asset = str(getattr(approved, "assetId", None) or "").strip() if approved else ""
    if approved_asset:
        cand_id = str(getattr(approved, "candidateId", None) or "").strip() or None
        matched = None
        if cand_id:
            matched = next((c for c in candidates if str(getattr(c, "id", None) or "") == cand_id), None)
        if matched is None:
            matched = next((c for c in candidates if _cand_asset(c) == approved_asset), None)
        take_id = None
        if matched is not None:
            take_id = str(getattr(matched, "takeId", None) or "") or None
            cand_id = str(getattr(matched, "id", None) or "") or cand_id
        return {
            "takeId": take_id or active_id or None,
            "assetId": approved_asset,
            "candidateId": cand_id,
            "source": "approved",
            "candidate": matched,
        }

    return None


def current_take_asset_id(batch: Any) -> str | None:
    resolved = resolve_current_take(batch)
    if not resolved:
        return None
    asset = str(resolved.get("assetId") or "").strip()
    return asset or None


def require_current_take(batch: Any, *, action: str = "Re-Take", master: Any | None = None) -> dict[str, Any]:
    """Gate helper: ok + resolved take, or structured error (no approval required)."""
    resolved = resolve_current_take(batch, master)
    if resolved and resolved.get("assetId"):
        return {"ok": True, "take": resolved}
    return {
        "ok": False,
        "error": "GENERATED_TAKE_REQUIRED",
        "message": (
            f"Generate a take first. {action} replaces a marked part of the current take."
        ),
        "mock": False,
    }


def stamp_current_take_fields(batch: Any, master: Any | None = None) -> None:
    """Keep BatchBlock.currentTakeId / currentTakeAssetId in sync with resolve."""
    resolved = resolve_current_take(batch, master)
    if not resolved:
        if hasattr(batch, "currentTakeId"):
            batch.currentTakeId = None
        if hasattr(batch, "currentTakeAssetId"):
            batch.currentTakeAssetId = None
        return
    if hasattr(batch, "currentTakeId"):
        batch.currentTakeId = resolved.get("takeId")
    if hasattr(batch, "currentTakeAssetId"):
        batch.currentTakeAssetId = resolved.get("assetId")


def _job_progress(batch: Any) -> float:
    jobs = list(getattr(batch, "generationJobs", None) or [])
    if not jobs:
        return 0.0
    live = [
        j
        for j in jobs
        if str(getattr(j, "status", "") or "").lower() in {"queued", "running", "pending"}
    ]
    pick = live[-1] if live else jobs[-1]
    try:
        return max(0.0, min(1.0, float(getattr(pick, "progress", 0.0) or 0.0)))
    except (TypeError, ValueError):
        return 0.0


def _batch_qc_ref(batch: Any) -> dict[str, Any] | None:
    for ref in getattr(batch, "references", None) or []:
        if isinstance(ref, dict) and ref.get("kind") == "dialogueQcDiagnostics":
            return ref
    return None


def _dialogue_qc_status_lines(batches: list[Any], *, completed: int, total: int, queue_active: bool) -> list[str]:
    """Creator-facing Dialogue QC / Scene Finished lines.

    N/N batches complete != Scene Finished. Scene Finished only after dialogue
    QC PASS (or no locked-script QC gate). Never invent Finished from N/N alone.
    """
    if total <= 0:
        return []
    lines: list[str] = []
    retake_idxs: list[int] = []
    qc_pass = 0
    qc_fail = 0
    qc_present = 0
    locked_script_batches = 0
    for i, batch in enumerate(batches):
        status = str(getattr(batch, "status", "") or "")
        qc = _batch_qc_ref(batch)
        if qc is not None:
            qc_present += 1
            verdict = str(qc.get("verdict") or "").upper()
            if verdict == "PASS" and qc.get("sceneFinishedEligible", True):
                qc_pass += 1
            elif verdict in {"FAIL", "UNCERTAIN"} or not qc.get("sceneFinishedEligible", True):
                qc_fail += 1
        if status == "NeedsDialogueRetake":
            retake_idxs.append(i + 1)
            if qc is None:
                qc_fail += 1
        # Locked-script signal: QC ref present OR NeedsDialogueRetake OR explicit manifest ref
        if qc is not None or status == "NeedsDialogueRetake":
            locked_script_batches += 1
        else:
            for ref in getattr(batch, "references", None) or []:
                if isinstance(ref, dict) and ref.get("kind") in {
                    "dialogueAuthorityManifest",
                    "dialogueRetakeRepair",
                }:
                    locked_script_batches += 1
                    break

    # Generation wave done when every batch is terminal for the sequential job
    # (complete, dialogue-retake, or failed) — not only COMPLETE_STATUSES.
    terminal = 0
    for batch in batches:
        status = str(getattr(batch, "status", "") or "")
        if status in {
            "Approved",
            "CandidateReady",
            "ApprovedConfigurationChanged",
            "RegenerationRecommended",
            "NeedsDialogueRetake",
            "Failed",
            "Cancelled",
        }:
            terminal += 1
    all_gen_done = terminal >= total and not queue_active
    if not all_gen_done:
        return lines

    # All generation batches reached successful completion statuses.
    if retake_idxs or qc_fail > 0:
        lines.append("Dialogue QC — Failed")
        lines.append("Scene Not Finished")
        # Do NOT append "Repairing Batch K…" here — that implies an active
        # repair cycle. attach_lifecycle_to_progress adds it when REPAIRING.
        return lines

    if locked_script_batches > 0 and qc_present < locked_script_batches and qc_fail == 0 and qc_pass < locked_script_batches:
        lines.append("Dialogue QC — Checking…")
        return lines

    if locked_script_batches > 0 and qc_pass >= locked_script_batches and qc_fail == 0:
        lines.append("Dialogue QC — Passed")
        lines.append("Scene Finished")
        return lines

    # No dialogue-authority gate observed: render complete is not auto Scene Finished.
    # Still surface N/N only (caller adds overall). Omit inventing Scene Finished.
    return lines


def compute_generation_progress(master: Any) -> dict[str, Any]:
    """FE-facing multi-batch progress derived from batchBlocks + job.progress.

    One authority for creator chrome: current batch line + overall completedBatches
    counter from canonical batch status (not clip presence / guessed duration).
    """
    from .scene_render_progress import derive_scene_render_progress

    batches = sorted(
        list(getattr(master, "batchBlocks", None) or []),
        key=lambda b: (int(getattr(b, "order", 0) or 0), str(getattr(b, "createdAt", "") or "")),
    )
    empty = {
        "currentBatchIndex": 0,
        "totalBatches": 0,
        "completedBatches": 0,
        "renderCompletedBatches": 0,
        "batchStatus": "Draft",
        "batchProgress": 0.0,
        "sceneStatus": "idle",
        "currentBatchId": None,
        "message": "",
        "overallBatchesLabel": "",
        "statusLines": [],
        "phase": "idle",
        "sceneFinished": False,
        "dialogueNeedsRetake": 0,
        "dialogueQcLabel": None,
    }
    if not batches:
        return empty

    derived = derive_scene_render_progress(master)
    # completedBatches from derive = QC-eligible complete (excludes NeedsDialogueRetake).
    # overallBatchesLabel counts RENDER completion (includes NeedsDialogueRetake):
    # "N/N batches complete" means rendering finished — NOT Scene Finished.
    completed = int(derived.get("completedBatches") or 0)
    total = int(derived.get("totalBatches") or len(batches))
    queue_active = bool(derived.get("queueActive"))
    render_complete_statuses = {
        "Approved",
        "CandidateReady",
        "ApprovedConfigurationChanged",
        "RegenerationRecommended",
        "NeedsDialogueRetake",
    }
    render_completed = sum(
        1 for b in batches if str(getattr(b, "status", "") or "") in render_complete_statuses
    )
    overall = f"{render_completed}/{total} batches complete" if total else ""

    approved_like = {"Approved", "ApprovedConfigurationChanged", "RegenerationRecommended"}
    generating = [(i, b) for i, b in enumerate(batches) if b.status == "Generating"]
    queued = [(i, b) for i, b in enumerate(batches) if b.status == "Queued"]
    failed = [(i, b) for i, b in enumerate(batches) if b.status == "Failed"]
    review = [(i, b) for i, b in enumerate(batches) if b.status == "CandidateReady"]
    cancelled = [(i, b) for i, b in enumerate(batches) if b.status == "Cancelled"]
    waiting = [(i, b) for i, b in enumerate(batches) if str(getattr(b, "status", "") or "") == "Waiting"]

    if generating:
        index, batch = generating[0]
        scene_status = "generating"
        progress = _job_progress(batch)
    elif queued:
        index, batch = queued[0]
        scene_status = "queued"
        progress = _job_progress(batch)
    elif waiting:
        index, batch = waiting[0]
        scene_status = "waiting"
        progress = _job_progress(batch)
    elif failed:
        index, batch = failed[0]
        scene_status = "partial_failed"
        progress = 0.0
    elif review and all(b.status in (approved_like | {"CandidateReady"}) for b in batches):
        index, batch = len(batches) - 1, batches[-1]
        scene_status = "complete"
        progress = 1.0
    elif all(b.status in approved_like for b in batches):
        index, batch = len(batches) - 1, batches[-1]
        scene_status = "complete"
        progress = 1.0
    elif cancelled and not any(b.status in ("Draft", "Ready", "Queued", "Generating", "Waiting") for b in batches):
        index, batch = cancelled[0]
        scene_status = "cancelled"
        progress = 0.0
    else:
        index, batch = 0, batches[0]
        for i, item in enumerate(batches):
            if item.status not in approved_like:
                index, batch = i, item
                break
        scene_status = "idle" if batch.status in ("Ready", "Draft") else str(batch.status).lower()
        progress = _job_progress(batch)

    n = int(index) + 1
    m = len(batches)
    take_label = None
    try:
        from .scene_takes import active_scene_take, scene_take_display

        active_take = active_scene_take(master)
        if active_take is not None:
            take_label = scene_take_display(active_take.label)
    except Exception:
        take_label = None
    from ..video_runtime.progress_telemetry import format_render_status_line

    grounded = float(progress or 0.0) > 0 and scene_status in ("generating", "queued", "waiting")
    if scene_status in ("generating", "queued", "waiting"):
        message = format_render_status_line(
            batch_index=n,
            total_batches=m,
            take_label=take_label,
            scene_status=scene_status,
            progress=float(progress or 0.0),
            progress_grounded=grounded,
            phase="queued" if scene_status == "queued" else ("preparing_model" if float(progress or 0) <= 0 else "sampling"),
        )
    elif scene_status in ("idle", "draft", "ready"):
        # Idle / Draft / Ready: no creator chrome message (statusLines stay empty below).
        message = ""
    else:
        message = f"Render Batch {n}/{m} — {scene_status}"

    qc_lines = _dialogue_qc_status_lines(
        batches, completed=completed, total=total, queue_active=queue_active
    )
    status_lines: list[str] = []
    if scene_status in ("generating", "queued", "waiting"):
        status_lines.append(message)
        if total > 1:
            status_lines.append(overall)
    elif total > 1 or completed > 0:
        # Multi-batch complete / QC lines only — never idle draft chrome.
        if overall:
            status_lines.append(overall)
        status_lines.extend(qc_lines)
    else:
        # Single Draft/Ready idle with no completed work: statusLines must be [].
        pass

    dialogue_qc_label = next((ln for ln in qc_lines if ln.startswith("Dialogue QC")), None)
    scene_finished = bool(derived.get("sceneFinished")) and any(
        ln == "Scene Finished" for ln in qc_lines
    )
    # If no dialogue gate, do NOT mark sceneFinished from N/N alone.
    if not qc_lines and scene_status == "complete":
        scene_finished = False

    payload = {
        "currentBatchIndex": n,
        "totalBatches": m,
        "completedBatches": completed,
        "renderCompletedBatches": render_completed,
        "batchStatus": str(batch.status),
        "batchProgress": float(progress or 0.0),
        "sceneStatus": scene_status,
        "currentBatchId": getattr(batch, "id", None),
        "message": message,
        "overallBatchesLabel": overall,
        "statusLines": status_lines,
        "phase": derived.get("phase"),
        "progressGrounded": bool(grounded),
        "sceneFinished": scene_finished,
        "dialogueNeedsRetake": int(derived.get("dialogueNeedsRetake") or 0),
        "dialogueQcLabel": dialogue_qc_label,
        "renderingTakeLabel": take_label,
    }
    try:
        from .scene_final_check import attach_lifecycle_to_progress

        payload = attach_lifecycle_to_progress(payload, master)
    except Exception:
        pass
    return payload
