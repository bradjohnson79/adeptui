"""Explicit Timeline Publish — Video Published Master + MAGI full-stitch gate.

Consumes Final Check lifecycle; never forks QC. Never auto-called from stitch/pass.
Publish is creator-explicit only.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from sqlalchemy.orm import Session

from ..generation_tools.lineage import register_derived_asset
from . import store
from .contracts import ScenePublishState, SceneTimelineMaster, _now
from .scene_stitch import resolve_asset_file

PUBLISH_READY_LIFECYCLES = frozenset(
    {
        "SCENE_FINISHED",
        "SCENE_FINISHED_WITH_ACCEPTED_ISSUES",
    }
)

TAG_VIDEO_PUBLISHED_MASTER = "video_published_master"
OP_VIDEO_PUBLISH = "video_publish"

CREATOR_ERRORS = {
    "SCENE_NOT_FOUND": "This scene could not be found.",
    "NOT_PUBLISH_READY": (
        "Publish is available only after Final Check PASS or accepted issues."
    ),
    "STITCH_REQUIRED": "Finish the scene stitch before publishing a Video Published Master.",
    "STITCH_ASSET_MISSING": "The stitched master video file is missing, so Adept cannot publish yet.",
    "NOTHING_PUBLISHED": "Nothing is published yet — use Publish first.",
    "NO_CHANGES_PENDING": "Published master already matches the current stitch — nothing to update.",
    "VERSION_CONFLICT": (
        "Published master changed elsewhere. Reload the Timeline, then try Update Published again."
    ),
    "MAGI_NOT_READY": "Upscale with MAGI is available only after Final Check PASS or accepted issues.",
    "MAGI_FULL_STITCH_ONLY": (
        "Upscale with MAGI from Timeline uses only the full stitched (or published) master — not a single batch."
    ),
    "MAGI_ASSET_MISSING": "The full stitch / published master file is missing, so Adept cannot upscale yet.",
    "MAGI_UPSCALE_FAILED": "MAGI could not save the enhanced master on Timeline. The original scene file is unchanged.",
    "PUBLISH_FAILED": "Adept could not register the Video Published Master. Timeline batches are unchanged.",
    "TARGET_NOT_ABOVE_SOURCE": (
        "MAGI only upscales to a size above the current master. "
        "Choose a higher target — same or lower resolution is not an upscale."
    ),
    "SOURCE_RESOLUTION_UNKNOWN": "Adept could not read the master resolution, so MAGI cannot upscale yet.",
    "NO_HIGHER_TARGET": (
        "This master is already at or above the highest MAGI target. "
        "There is nothing higher to upscale to."
    ),
}


def is_publish_ready(master: SceneTimelineMaster | None) -> bool:
    """True only when Final Check closed PASS or accepted-issues AND stitch exists."""
    if master is None:
        return False
    fc = master.sceneFinalCheck
    stitch = master.sceneStitch
    if not fc or not stitch or not str(stitch.assetId or "").strip():
        return False
    return str(fc.lifecycleStatus or "") in PUBLISH_READY_LIFECYCLES


def content_fingerprint(master: SceneTimelineMaster) -> str:
    """Stable hash of current stitch identity for Changes Pending detection."""
    stitch = master.sceneStitch
    if not stitch or not str(stitch.assetId or "").strip():
        return ""
    parts = [
        str(stitch.assetId).strip(),
        ",".join(str(x).strip() for x in (stitch.sourceAssetIds or []) if str(x).strip()),
        ",".join(str(x).strip() for x in (stitch.sourceBatchIds or []) if str(x).strip()),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]


def changes_pending(master: SceneTimelineMaster) -> bool:
    pub = master.scenePublish
    if not pub or not str(pub.publishedAssetId or "").strip():
        return False
    current = content_fingerprint(master)
    if not current:
        return False
    return current != str(pub.contentFingerprint or "")


def _fail(code: str, *, detail: str | None = None) -> dict[str, Any]:
    msg = CREATOR_ERRORS.get(code, code)
    out: dict[str, Any] = {
        "ok": False,
        "error": code,
        "creatorMessage": msg,
        "mock": False,
    }
    if detail:
        out["detail"] = detail[:400]
    return out


def _provenance_snapshot(master: SceneTimelineMaster) -> dict[str, Any]:
    fc = master.sceneFinalCheck
    life = str(fc.lifecycleStatus or "") if fc else ""
    verdict = str(fc.creatorVerdict or "").strip() if fc else ""
    accepted = life == "SCENE_FINISHED_WITH_ACCEPTED_ISSUES"
    # Honest accepted-issues: never rewrite verdict to a clean PASS.
    return {
        "lifecycleStatusSnapshot": life,
        "creatorVerdictSnapshot": verdict or None,
        "acceptedIssues": accepted,
    }


def _allowed_magi_asset_ids(master: SceneTimelineMaster) -> set[str]:
    """MAGI may ingest the published master only — never unpublished Takes."""
    allowed: set[str] = set()
    pub = master.scenePublish
    if pub and str(pub.publishedAssetId or "").strip():
        allowed.add(str(pub.publishedAssetId).strip())
        if pub.upscaledAssetId:
            allowed.add(str(pub.upscaledAssetId).strip())
        if pub.sourceSceneStitchAssetId:
            allowed.add(str(pub.sourceSceneStitchAssetId).strip())
        return {a for a in allowed if a}
    if master.sceneStitch and master.sceneStitch.assetId:
        allowed.add(str(master.sceneStitch.assetId).strip())
    return {a for a in allowed if a}


def publish_scene(
    db: Session,
    project_id: str,
    scene_id: str,
    *,
    update: bool = False,
    expected_version: int | None = None,
    source: str = "stitch",
) -> dict[str, Any]:
    """Atomic register Library Video Published Master from stitch + FC provenance.

    Never auto-called from stitch/pass. Refuses unless publish-ready.
    """
    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return _fail("SCENE_NOT_FOUND")
    master = SceneTimelineMaster.model_validate(payload["master"])

    if not is_publish_ready(master):
        return _fail("NOT_PUBLISH_READY")

    stitch = master.sceneStitch
    assert stitch is not None
    stitch_asset_id = str(stitch.assetId).strip()
    if not stitch_asset_id:
        return _fail("STITCH_REQUIRED")

    existing = master.scenePublish
    if update:
        if not existing or not str(existing.publishedAssetId or "").strip():
            return _fail("NOTHING_PUBLISHED")
        if expected_version is not None and int(existing.version) != int(expected_version):
            return _fail("VERSION_CONFLICT")
        if source == "stitch" and not changes_pending(master):
            return _fail("NO_CHANGES_PENDING")
        if source == "upscaled":
            if not existing.upscaledAssetId:
                return _fail(
                    "STITCH_ASSET_MISSING",
                    detail="No upscaled derivative to publish yet.",
                )

    # Source file: stitch master, or prior upscaled derivative when publishing upscaled.
    source_asset_id = stitch_asset_id
    if source == "upscaled" and existing and existing.upscaledAssetId:
        source_asset_id = str(existing.upscaledAssetId).strip()
    elif source == "published" and existing and existing.publishedAssetId:
        source_asset_id = str(existing.publishedAssetId).strip()

    src_path = resolve_asset_file(db, project_id, source_asset_id)
    if src_path is None:
        return _fail("STITCH_ASSET_MISSING")

    snap = _provenance_snapshot(master)
    fp = content_fingerprint(master)
    next_version = int(existing.version) + 1 if (update and existing) else 1
    from .scene_takes import current_scene_take, ensure_scene_takes, scene_take_display

    ensure_scene_takes(master)
    pre_take = current_scene_take(master)

    try:
        asset = register_derived_asset(
            db,
            project_id=project_id,
            source_path=src_path,
            kind="video",
            tag=TAG_VIDEO_PUBLISHED_MASTER,
            parent_asset_id=source_asset_id,
            op=OP_VIDEO_PUBLISH,
            model=OP_VIDEO_PUBLISH,
            prompt_meta={
                "sceneId": scene_id,
                "libraryKind": "Video Published Master",
                "sourceSceneStitchAssetId": stitch_asset_id,
                "sourceAssetId": source_asset_id,
                "publishSource": source,
                "contentFingerprint": fp,
                "version": next_version,
                "takeId": pre_take.id if pre_take else None,
                "takeLabel": scene_take_display(pre_take.label) if pre_take else None,
                "batchIds": [m.batchId for m in (pre_take.batches if pre_take else [])]
                or [b.id for b in (master.batchBlocks or [])],
                **snap,
            },
            filename=f"video_published_master_{scene_id[:8]}_{uuid.uuid4().hex[:8]}.mp4",
        )
    except Exception as exc:
        return _fail("PUBLISH_FAILED", detail=str(exc))

    # Re-load after register commits.
    payload2 = store.load_master(db, project_id, scene_id)
    if not payload2.get("ok"):
        return _fail("SCENE_NOT_FOUND")
    master = SceneTimelineMaster.model_validate(payload2["master"])
    preserved = [b.id for b in master.batchBlocks]

    prior_upscaled = existing.upscaledAssetId if existing else None
    from .scene_takes import current_scene_take, scene_take_display, ensure_scene_takes

    ensure_scene_takes(master)
    cur_take = current_scene_take(master)
    take_id = cur_take.id if cur_take else None
    take_label = scene_take_display(cur_take.label) if cur_take else None
    take_batch_ids = [m.batchId for m in (cur_take.batches if cur_take else [])] or [
        b.id for b in (master.batchBlocks or [])
    ]
    master.scenePublish = ScenePublishState(
        publishedAssetId=asset.id,
        publishedAt=_now(),
        sourceSceneStitchAssetId=stitch_asset_id,
        lifecycleStatusSnapshot=snap["lifecycleStatusSnapshot"],
        creatorVerdictSnapshot=snap["creatorVerdictSnapshot"],
        acceptedIssues=bool(snap["acceptedIssues"]),
        contentFingerprint=fp,
        version=next_version,
        upscaledAssetId=prior_upscaled if source != "upscaled" else str(source_asset_id),
        publishSource=source,
        upscalePendingPublish=False if source == "upscaled" else bool(existing.upscalePendingPublish) if existing else False,
        takeId=take_id,
        takeLabel=take_label,
        batchIds=take_batch_ids,
    )
    if cur_take is not None:
        cur_take.publishedAssetId = asset.id
    store.save_master(db, project_id, scene_id, master, touch_batches=False)

    after = [b.id for b in master.batchBlocks]
    if after != preserved:
        return _fail("PUBLISH_FAILED", detail="Batch identity changed unexpectedly.")

    return {
        "ok": True,
        "updated": bool(update),
        "scenePublish": master.scenePublish.model_dump(),
        "master": master.model_dump(),
        "publishedAssetId": asset.id,
        "contentFingerprint": fp,
        "changesPending": False,
        "mock": False,
    }


def _choose_magi_source(master: SceneTimelineMaster, asset_id: str | None) -> tuple[str | None, dict[str, Any] | None]:
    allowed = _allowed_magi_asset_ids(master)
    if not allowed:
        return None, _fail("MAGI_FULL_STITCH_ONLY")
    chosen = str(asset_id or "").strip()
    if chosen:
        if chosen not in allowed:
            return None, _fail("MAGI_FULL_STITCH_ONLY")
        return chosen, None
    pub = master.scenePublish
    if pub and str(pub.publishedAssetId or "").strip():
        return str(pub.publishedAssetId).strip(), None
    if master.sceneStitch and master.sceneStitch.assetId:
        return str(master.sceneStitch.assetId).strip(), None
    return None, _fail("MAGI_FULL_STITCH_ONLY")


def persist_scene_upscaled_asset(
    db: Session,
    project_id: str,
    scene_id: str,
    asset_id: str,
) -> dict[str, Any]:
    """Write scenePublish.upscaledAssetId after the MAGI job finishes. Never auto-publish."""
    aid = str(asset_id or "").strip()
    if not aid:
        return _fail("MAGI_UPSCALE_FAILED", detail="Missing derived asset id.")
    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return _fail("SCENE_NOT_FOUND")
    master = SceneTimelineMaster.model_validate(payload["master"])
    if not is_publish_ready(master):
        return _fail("MAGI_NOT_READY")
    stitch_id = str(master.sceneStitch.assetId).strip() if master.sceneStitch else ""
    pub = master.scenePublish
    if pub is None:
        master.scenePublish = ScenePublishState(
            publishedAssetId="",
            publishedAt="",
            sourceSceneStitchAssetId=stitch_id,
            upscaledAssetId=aid,
            upscalePendingPublish=True,
            version=0,
            publishSource="stitch",
        )
    else:
        pub.upscaledAssetId = aid
        pub.upscalePendingPublish = True
    store.save_master(db, project_id, scene_id, master, touch_batches=False)
    return {
        "ok": True,
        "upscaledAssetId": aid,
        "autoPublished": False,
        "scenePublish": master.scenePublish.model_dump() if master.scenePublish else None,
        "mock": False,
    }


def magi_upscale_options(
    db: Session,
    project_id: str,
    scene_id: str,
    *,
    asset_id: str | None = None,
) -> dict[str, Any]:
    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return _fail("SCENE_NOT_FOUND")
    master = SceneTimelineMaster.model_validate(payload["master"])
    if not is_publish_ready(master):
        return _fail("MAGI_NOT_READY")
    chosen, err = _choose_magi_source(master, asset_id)
    if err:
        return err
    src_path = resolve_asset_file(db, project_id, chosen or "")
    if src_path is None:
        return _fail("MAGI_ASSET_MISSING")
    from ..magi.media import probe_media
    from ..magi.upscale_targets import default_target, meaningful_targets
    from ..magi.upscaling import ENGINE_FFMPEG, ENGINE_GPU, capabilities, preferred_gpu_model

    probe = probe_media(src_path)
    src_w = int(probe.get("width") or 0)
    src_h = int(probe.get("height") or 0)
    caps = capabilities()
    gpu_ready = bool(caps.get("realesrganReady"))
    first = default_target(src_w, src_h)
    return {
        "ok": True,
        "sourceAssetId": chosen,
        "sourceWidth": src_w,
        "sourceHeight": src_h,
        "sourceResolution": f"{src_w}x{src_h}" if src_w and src_h else "",
        "targets": meaningful_targets(src_w, src_h),
        "defaultTarget": (first or {}).get("id") or "",
        "defaultEngine": ENGINE_GPU if gpu_ready else ENGINE_FFMPEG,
        "defaultModel": preferred_gpu_model() if gpu_ready else "lanczos",
        "realesrganReady": gpu_ready,
        "spatialEnhancementOnly": True,
        "temporalConsistency": False,
        "honesty": caps.get("honesty"),
        "engines": caps.get("engines"),
        "previewIsNotApply": True,
        "mock": False,
    }


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
    """Queue MAGI apply on the full stitched / published master. Persist happens on job done."""
    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return _fail("SCENE_NOT_FOUND")
    master = SceneTimelineMaster.model_validate(payload["master"])

    if not is_publish_ready(master):
        return _fail("MAGI_NOT_READY")

    chosen, err = _choose_magi_source(master, asset_id)
    if err:
        return err
    if chosen and chosen not in _allowed_magi_asset_ids(master):
        return _fail("MAGI_FULL_STITCH_ONLY")

    src_path = resolve_asset_file(db, project_id, chosen or "")
    if src_path is None:
        return _fail("MAGI_ASSET_MISSING")

    from ..magi.upscale_targets import UpscaleTargetError
    from ..magi.upscaling import apply_upscale

    try:
        result = apply_upscale(
            db,
            project_id,
            chosen or "",
            engine,
            model,
            target_resolution,
            scene_id=scene_id,
            persist_scene_publish=True,
        )
    except UpscaleTargetError as exc:
        return _fail(exc.code, detail=str(exc)[:400])
    except Exception as exc:
        return {
            "ok": False,
            "error": "MAGI_UPSCALE_FAILED",
            "creatorMessage": "Adept could not start MAGI upscale on the full stitch master.",
            "detail": str(exc)[:400],
            "mock": False,
        }

    payload3 = store.load_master(db, project_id, scene_id)
    if payload3.get("ok"):
        master = SceneTimelineMaster.model_validate(payload3["master"])

    job_id = None
    if isinstance(result, dict):
        job_id = result.get("jobId")

    ok = True
    if isinstance(result, dict) and result.get("ok") is False:
        ok = False

    return {
        "ok": ok,
        "queued": bool(isinstance(result, dict) and result.get("queued")),
        "jobId": job_id,
        "magi": result,
        "sourceAssetId": chosen,
        "upscaledAssetId": None,
        "autoPublished": False,
        "scenePublish": master.scenePublish.model_dump() if master.scenePublish else None,
        "master": master.model_dump(),
        "preview": False,
        "mock": False,
    }


def publish_status(master: SceneTimelineMaster | None) -> dict[str, Any]:
    """FE chrome helper payload (also used by unit tests)."""
    if master is None:
        return {
            "publishReady": False,
            "changesPending": False,
            "hasPublished": False,
            "showPublish": False,
            "showUpdatePublished": False,
            "showUpscaleWithMagi": False,
        }
    ready = is_publish_ready(master)
    pending = changes_pending(master) if ready else False
    has_pub = bool(master.scenePublish and str(master.scenePublish.publishedAssetId or "").strip())
    upscale_pending = bool(
        has_pub and master.scenePublish and master.scenePublish.upscalePendingPublish
    )
    return {
        "publishReady": ready,
        "changesPending": pending or upscale_pending,
        "hasPublished": has_pub,
        "showPublish": ready and not has_pub,
        "showUpdatePublished": ready and has_pub and (pending or upscale_pending),
        "showUpscaleWithMagi": ready,
        "scenePublish": master.scenePublish.model_dump() if master.scenePublish else None,
        "contentFingerprint": content_fingerprint(master) if master.sceneStitch else "",
    }
