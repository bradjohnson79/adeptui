"""Timeline Master service façade."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..director_timeline import parse_director_timeline
from . import orchestrator, store
from .camera_catalog import camera_catalog_payload
from .capabilities import list_generators, registry_snapshot, validate_duration
from .contracts import BatchBlock, CancelRequest, DurationState, SceneTimelineMaster, TimelinePromptSegment, _now
from .migration import compute_config_fingerprint, load_or_migrate_scene_master


def workspace(db: Session, project_id: str, scene_id: str) -> dict[str, Any]:
    return store.load_master(db, project_id, scene_id)


def load_timeline_bundle(db: Session, project_id: str, scene_id: str) -> dict[str, Any]:
    scene = store.get_scene(db, project_id, scene_id)
    if not scene:
        return {"ok": False, "error": "SCENE_NOT_FOUND", "mock": False}
    master, director_tl, _data = load_or_migrate_scene_master(
        scene.director_json,
        scene_id=scene_id,
        fallback_duration=float(scene.duration_sec or 5.0),
        fallback_prompt=scene.prompt or "",
    )
    workspace_state = store.extract_timeline_workspace(scene.director_json)
    return {
        "ok": True,
        "projectId": project_id,
        "sceneId": scene_id,
        "master": master,
        "directorTimeline": director_tl,
        "workspace": workspace_state,
        "playhead": float(director_tl.playhead or 0.0),
        "mock": False,
    }


def put_master(db: Session, project_id: str, scene_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return store.replace_master(db, project_id, scene_id, payload)


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
    planned_duration: float = 5.0,
    generator_id: str | None = None,
    at_order: int | None = None,
) -> dict[str, Any]:
    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return payload
    master = SceneTimelineMaster.model_validate(payload["master"])
    order = at_order if at_order is not None else (max((b.order for b in master.batchBlocks), default=-1) + 1)
    batch = BatchBlock(
        sceneId=scene_id,
        order=order,
        label=label or f"Batch {order + 1}",
        generatorId=generator_id or master.sceneGeneratorId,
        duration=DurationState(plannedDuration=planned_duration, timelineVisibleDuration=planned_duration),
        promptSegments=[TimelinePromptSegment(start=0.0, length=planned_duration, text="")],
        status="Draft",
    )
    batch.configFingerprint = compute_config_fingerprint(batch)
    # Shift orders if inserting
    if at_order is not None:
        for b in master.batchBlocks:
            if b.order >= order:
                b.order += 1
    master.batchBlocks.append(batch)
    master.batchBlocks.sort(key=lambda b: b.order)
    store.save_master(db, project_id, scene_id, master)
    return {"ok": True, "batch": batch.model_dump(), "master": master.model_dump(), "mock": False}


def duplicate_batch(db: Session, project_id: str, scene_id: str, batch_id: str) -> dict[str, Any]:
    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return payload
    master = SceneTimelineMaster.model_validate(payload["master"])
    src = next((b for b in master.batchBlocks if b.id == batch_id), None)
    if not src:
        return {"ok": False, "error": "BATCH_NOT_FOUND", "mock": False}
    clone = src.model_copy(
        deep=True,
        update={
            "id": BatchBlock().id,
            "label": f"{src.label} copy",
            "order": src.order + 1,
            "status": "Draft",
            "generationJobs": [],
            "candidateVersions": [],
            "approvedClip": None,
            "repairRanges": [],
            "createdAt": _now(),
            "updatedAt": _now(),
        },
    )
    for b in master.batchBlocks:
        if b.order >= clone.order:
            b.order += 1
    clone.configFingerprint = compute_config_fingerprint(clone)
    master.batchBlocks.append(clone)
    master.batchBlocks.sort(key=lambda b: b.order)
    store.save_master(db, project_id, scene_id, master)
    return {"ok": True, "batch": clone.model_dump(), "mock": False}


def delete_batch(db: Session, project_id: str, scene_id: str, batch_id: str) -> dict[str, Any]:
    """Remove a Batch Block (UI − / Delete) — stashes for Co-Director restore parity."""
    bundle = load_timeline_bundle(db, project_id, scene_id)
    if not bundle.get("ok"):
        return {"ok": False, "error": bundle.get("error") or "NOT_FOUND", "mock": False}
    master: SceneTimelineMaster = bundle["master"]
    workspace = bundle["workspace"]
    batch = next((b for b in master.batchBlocks if b.id == batch_id), None)
    if not batch:
        return {"ok": False, "error": "BATCH_NOT_FOUND", "mock": False}
    master.batchBlocks = [b for b in master.batchBlocks if b.id != batch_id]
    for i, b in enumerate(sorted(master.batchBlocks, key=lambda x: x.order)):
        b.order = i
    master.batchBlocks.sort(key=lambda b: b.order)
    workspace = store.stash_removed_item(
        workspace,
        kind="batchBlock",
        item_id=batch_id,
        payload=batch.model_dump(),
    )
    store.save_master(
        db,
        project_id,
        scene_id,
        master,
        director_tl=bundle.get("directorTimeline"),
        workspace=workspace,
        bump_revision=True,
    )
    return {"ok": True, "deleted": batch_id, "stashed": True, "mock": False}


def patch_batch(db: Session, project_id: str, scene_id: str, batch_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    return orchestrator.touch_batch_config(db, project_id, scene_id, batch_id, patch)


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
