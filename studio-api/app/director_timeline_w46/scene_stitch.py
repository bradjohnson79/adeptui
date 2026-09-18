"""Additive scene-level stitch of approved Timeline batch takes.

Never deletes, flattens, or rewrites Batch Blocks. A new derived Library
asset is the only write besides master.sceneStitch provenance.
"""

from __future__ import annotations

import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..config import settings
from ..db import Asset, Project
from ..generation_tools.lineage import register_derived_asset
from ..media_ops import stitch_videos
from . import store
from .contracts import SceneStitch, SceneTimelineMaster, _now

COMPLETED_STATUSES = frozenset(
    {
        "Approved",
        "ApprovedConfigurationChanged",
        "RegenerationRecommended",
    }
)

CREATOR_ERRORS = {
    "SCENE_NOT_FOUND": "This scene could not be found.",
    "NEED_TWO_COMPLETED_BATCHES": "Finish and approve at least two batches before stitching.",
    "SOURCE_ASSET_MISSING": "A finished batch is missing its video file, so Adept cannot stitch yet.",
    "PRIOR_STITCH_MISSING": "The earlier stitched clip is missing, so Adept will rebuild the full sequence.",
    "FFMPEG_UNAVAILABLE": "Adept cannot join clips because the video tool is not available.",
    "STITCH_FAILED": "Adept could not join the finished batches. The original batches are unchanged.",
}


def collect_completed_sources(master: SceneTimelineMaster) -> list[tuple[str, str]]:
    """Current-take member assets in Timeline order; Approved-like batches only.

    REBUILD LAW (Take/asset ownership): the scene result is the stitched
    continuity of the CURRENT whole-scene Take. Sources resolve through the
    current Take's batch membership first — the same precedence as Visual
    placement (``place_approved_batches_on_timeline``) and
    ``_playable_take_for_batch`` — with ``approvedClip`` as the fallback for
    pre-take masters. Gating on approvedClip alone is the Take O silent gate
    bypass shape: after a pointer heal, approvedClip can lag the current take
    and bake a stale Take A asset into the scene result.
    """
    current_take = next(
        (
            take
            for take in (master.sceneTakes or [])
            if take.id == getattr(master, "currentSceneTakeId", None)
        ),
        None,
    )
    preferred = {
        str(member.batchId): str(member.assetId or "").strip()
        for member in (current_take.batches if current_take else [])
        if getattr(member, "assetId", None)
    }
    batches = sorted(master.batchBlocks, key=lambda batch: (int(batch.order), batch.createdAt or ""))
    sources: list[tuple[str, str]] = []
    for batch in batches:
        asset_id = preferred.get(str(batch.id), "")
        if not asset_id and batch.approvedClip and batch.approvedClip.assetId:
            asset_id = str(batch.approvedClip.assetId).strip()
        if not asset_id:
            continue
        if batch.status not in COMPLETED_STATUSES:
            continue
        sources.append((batch.id, asset_id))
    return sources


def plan_stitch(
    existing_source_asset_ids: list[str] | None,
    current_source_asset_ids: list[str],
) -> dict[str, Any]:
    """Decide whether the current approved takes are current, an append, or a rebuild."""
    current = [str(item).strip() for item in current_source_asset_ids if str(item).strip()]
    existing = [str(item).strip() for item in (existing_source_asset_ids or []) if str(item).strip()]
    if existing and existing == current:
        return {"mode": "already_current", "appendAssetIds": [], "rebuildAll": False}
    if existing and len(existing) < len(current) and current[: len(existing)] == existing:
        return {
            "mode": "incremental",
            "appendAssetIds": current[len(existing) :],
            "rebuildAll": False,
        }
    return {"mode": "full", "appendAssetIds": current, "rebuildAll": True}


def covered_duration_sec(master: SceneTimelineMaster, batch_ids: list[str]) -> float:
    wanted = set(batch_ids)
    total = 0.0
    for batch in master.batchBlocks:
        if batch.id in wanted:
            total += max(0.0, float(batch.duration.plannedDuration or 0.0))
    return total


def resolve_asset_file(db: Session, project_id: str, asset_id: str) -> Path | None:
    try:
        from ..creator_scope.service import asset_file_path

        scoped = asset_file_path(db, project_id, asset_id)
        if scoped is not None:
            return scoped
    except Exception:
        pass
    asset = db.get(Asset, asset_id)
    if not asset or asset.project_id != project_id:
        return None
    raw = str(getattr(asset, "path", "") or "").strip()
    if not raw:
        return None
    path = Path(raw)
    if path.is_file():
        return path
    alt = Path(settings.data_dir) / raw
    if alt.is_file():
        return alt
    return None


def _probe_duration_sec(path: Path) -> float | None:
    ffprobe = shutil.which("ffprobe") or shutil.which("ffprobe.exe")
    if not ffprobe:
        return None
    try:
        proc = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return float(proc.stdout.strip())
    except Exception:
        return None
    return None


def _fail(code: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "error": code,
        "message": CREATOR_ERRORS.get(code, code),
        "mock": False,
    }
    payload.update(extra)
    return payload


def stitch_scene(db: Session, project_id: str, scene_id: str) -> dict[str, Any]:
    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return _fail(str(payload.get("error") or "SCENE_NOT_FOUND"))

    master = SceneTimelineMaster.model_validate(payload["master"])
    sources = collect_completed_sources(master)
    if len(sources) < 2:
        return _fail("NEED_TWO_COMPLETED_BATCHES", completedCount=len(sources))

    source_batch_ids = [item[0] for item in sources]
    source_asset_ids = [item[1] for item in sources]
    existing = master.sceneStitch
    existing_ids = list(existing.sourceAssetIds) if existing else []
    plan = plan_stitch(existing_ids, source_asset_ids)

    if plan["mode"] == "already_current" and existing and existing.assetId:
        if resolve_asset_file(db, project_id, existing.assetId):
            # Ensure Final Check exists when stitch already current.
            auto_retakes_ac = None
            try:
                from .scene_final_check import (
                    apply_planned_local_auto_repair_to_final_check,
                    execute_local_auto_retakes,
                    open_final_check_after_stitch,
                    plan_local_auto_repair_from_final_check,
                )
                from .contracts import SceneFinalCheck

                if master.sceneFinalCheck is None:
                    fc_state = open_final_check_after_stitch(
                        master,
                        generator_id=getattr(master, "sceneGeneratorId", None),
                    )
                    master.sceneFinalCheck = SceneFinalCheck.model_validate(fc_state)
                plan_ac = plan_local_auto_repair_from_final_check(master)
                if plan_ac.get("cleanupFailed"):
                    apply_planned_local_auto_repair_to_final_check(master, plan_ac)
                elif plan_ac.get("shouldAutoRetake"):
                    apply_planned_local_auto_repair_to_final_check(master, plan_ac)
                    store.save_master(db, project_id, scene_id, master, touch_batches=False)
                    auto_retakes_ac = execute_local_auto_retakes(
                        db, project_id, scene_id, master, plan=plan_ac
                    )
                store.save_master(db, project_id, scene_id, master, touch_batches=False)
            except Exception:
                pass
            return {
                "ok": True,
                "alreadyCurrent": True,
                "incremental": False,
                "sceneStitch": existing.model_dump(),
                "sceneFinalCheck": master.sceneFinalCheck.model_dump() if master.sceneFinalCheck else None,
                "master": master.model_dump(),
                "sourceBatchIds": source_batch_ids,
                "autoRetakes": auto_retakes_ac,
                "mock": False,
            }

    if not (shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")):
        return _fail("FFMPEG_UNAVAILABLE")

    input_paths: list[Path] = []
    incremental = plan["mode"] == "incremental" and existing is not None
    if incremental and existing:
        prior = resolve_asset_file(db, project_id, existing.assetId)
        if not prior:
            incremental = False
            plan = {"mode": "full", "appendAssetIds": source_asset_ids, "rebuildAll": True}
        else:
            input_paths.append(prior)
            for asset_id in plan["appendAssetIds"]:
                path = resolve_asset_file(db, project_id, asset_id)
                if not path:
                    return _fail("SOURCE_ASSET_MISSING", assetId=asset_id)
                input_paths.append(path)

    if not incremental:
        input_paths = []
        for _batch_id, asset_id in sources:
            path = resolve_asset_file(db, project_id, asset_id)
            if not path:
                return _fail("SOURCE_ASSET_MISSING", assetId=asset_id)
            input_paths.append(path)

    scene = store.get_scene(db, project_id, scene_id)
    if not scene:
        return _fail("SCENE_NOT_FOUND")
    fps = 24
    project = db.get(Project, project_id)
    if project and getattr(project, "fps", None):
        try:
            fps = max(1, int(project.fps))
        except (TypeError, ValueError):
            fps = 24
    if getattr(scene, "fps", None):
        try:
            fps = max(1, int(scene.fps))
        except (TypeError, ValueError):
            pass

    tmp_dir = settings.data_dir / "projects" / project_id / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_out = tmp_dir / f"scene_stitch_{uuid.uuid4().hex[:12]}.mp4"
    try:
        stitch_videos(input_paths, tmp_out, fps=fps)
        if not tmp_out.is_file() or tmp_out.stat().st_size <= 0:
            return _fail("STITCH_FAILED")
        parent_id = source_asset_ids[0]
        asset = register_derived_asset(
            db,
            project_id=project_id,
            source_path=tmp_out,
            kind="video",
            tag="scene_stitch",
            parent_asset_id=parent_id,
            op="scene_stitch",
            model="scene_stitch",
            prompt_meta={
                "sceneId": scene_id,
                "sourceBatchIds": source_batch_ids,
                "sourceAssetIds": source_asset_ids,
                "incremental": incremental,
            },
            filename=f"scene_stitch_{scene_id[:8]}_{uuid.uuid4().hex[:8]}.mp4",
        )
    except Exception as exc:
        return _fail("STITCH_FAILED", detail=str(exc)[:400])
    finally:
        try:
            tmp_out.unlink(missing_ok=True)
        except Exception:
            pass

    probed = _probe_duration_sec(Path(asset.path))
    duration_sec = probed if probed and probed > 0 else covered_duration_sec(master, source_batch_ids)
    stitch = SceneStitch(
        assetId=asset.id,
        sourceBatchIds=source_batch_ids,
        sourceAssetIds=source_asset_ids,
        incremental=incremental,
        durationSec=duration_sec,
        createdAt=_now(),
    )
    # Re-load after register_derived_asset commits so we do not clobber concurrent writes.
    payload = store.load_master(db, project_id, scene_id)
    if not payload.get("ok"):
        return _fail(str(payload.get("error") or "SCENE_NOT_FOUND"))
    master = SceneTimelineMaster.model_validate(payload["master"])
    preserved_ids = [batch.id for batch in master.batchBlocks]
    master.sceneStitch = stitch
    # Open Final Check after stitch (manual or auto). Additive lifecycle authority.
    try:
        from .scene_final_check import open_final_check_after_stitch
        from .contracts import SceneFinalCheck

        fc_state = open_final_check_after_stitch(
            master,
            generator_id=getattr(master, "sceneGeneratorId", None),
        )
        # Mark STITCHING briefly then FINAL_CHECK / FINISHED from open helper.
        if fc_state.get("lifecycleStatus") == "SCENE_FINISHED":
            pass
        else:
            fc_state["lifecycleStatus"] = fc_state.get("lifecycleStatus") or "FINAL_CHECK"
        master.sceneFinalCheck = SceneFinalCheck.model_validate(fc_state)
        # Local HIGH-CONF Hard → enter REPAIRING + attach PRESERVE pack (retake_range consumes).
        # API still ask-once (planner returns needsApiAsk). Does not invent Omni packets.
        try:
            from .scene_final_check import (
                apply_planned_local_auto_repair_to_final_check,
                plan_local_auto_repair_from_final_check,
            )

            plan = plan_local_auto_repair_from_final_check(master)
            auto_retakes = None
            if plan.get("cleanupFailed"):
                apply_planned_local_auto_repair_to_final_check(master, plan)
            elif plan.get("shouldAutoRetake"):
                apply_planned_local_auto_repair_to_final_check(master, plan)
                from .scene_final_check import execute_local_auto_retakes

                # Persist pack attach before retake_range reads master.
                store.save_master(db, project_id, scene_id, master, touch_batches=False)
                auto_retakes = execute_local_auto_retakes(
                    db, project_id, scene_id, master, plan=plan
                )
            # needsApiAsk: leave FINAL_CHECK + permission=required for creator.
            if auto_retakes is not None:
                # Stash for return payload via master extras-style attribute (ephemeral).
                try:
                    master._finalCheckAutoRetakes = auto_retakes  # type: ignore[attr-defined]
                except Exception:
                    pass
        except Exception:
            pass
    except Exception:
        # Never fail stitch because Final Check open failed — stitch asset already registered.
        pass
    store.save_master(db, project_id, scene_id, master, touch_batches=False)

    scene = store.get_scene(db, project_id, scene_id)
    if scene:
        scene.output_path = str(asset.path)
        db.add(scene)
        db.commit()

    after_ids = [batch.id for batch in master.batchBlocks]
    if after_ids != preserved_ids:
        return _fail("STITCH_FAILED", detail="Batch identity changed unexpectedly.")

    auto_retakes_out = getattr(master, "_finalCheckAutoRetakes", None)
    return {
        "ok": True,
        "alreadyCurrent": False,
        "incremental": incremental,
        "sceneStitch": stitch.model_dump(),
        "sceneFinalCheck": master.sceneFinalCheck.model_dump() if master.sceneFinalCheck else None,
        "master": master.model_dump(),
        "assetId": asset.id,
        "sourceBatchIds": source_batch_ids,
        "sourceAssetIds": source_asset_ids,
        "autoRetakes": auto_retakes_out,
        "mock": False,
    }
