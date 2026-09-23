"""MAGI Co-Director tools.

Read tools inspect authoritative sequence state and assemble the
PostProductionContextPackage (CONTRACT_FREEZE). Mutation tools write finishing
state or queue jobs, attach MagiActionReceipt, and VERIFY by re-read — never
overwrite source media. CD must refuse NOT_SUPPORTED ops (trim/overlay/Publish/FC).
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from ...errors import CoDirectorError, TOOL_TARGET_NOT_FOUND
from ..definitions import ToolContext
from .magi_action_receipt import (
    build_receipt,
    new_action_id,
    utc_now,
    verify_magi_action,
    wrap_apply_result,
)
from .magi_post_context import assemble_post_production_context


async def inspect_sequence(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Read the authoritative MAGI sequence for a project (projectId-scoped)."""
    from ....magi.sequence.store import get_sequence

    include_clips = bool(args.get("includeClips", True))
    seq = get_sequence(ctx.project_id)
    if not include_clips:
        seq = {**seq, "clips": []}
    return {
        "projectId": ctx.project_id,
        "sequence": seq,
        "_evidence": {"source": "magi.sequence.store.get_sequence"},
    }


async def inspect_clip(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Read a single MAGI clip by immutable clipId (projectId-scoped)."""
    from ....magi.sequence.store import get_sequence

    clip_id = str(args.get("clipId") or "").strip()
    if not clip_id:
        raise CoDirectorError(TOOL_TARGET_NOT_FOUND, "clipId is required")
    seq = get_sequence(ctx.project_id)
    clip = next((c for c in seq.get("clips") or [] if c.get("id") == clip_id), None)
    if clip is None:
        raise CoDirectorError(
            TOOL_TARGET_NOT_FOUND,
            f"Clip '{clip_id}' not found in project '{ctx.project_id}'.",
        )
    track = next((t for t in seq.get("tracks") or [] if t.get("id") == clip.get("trackId")), None)
    return {
        "projectId": ctx.project_id,
        "clip": clip,
        "track": track,
        "_evidence": {"source": "magi.sequence.store.get_sequence"},
    }


async def inspect_tracks(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Read the authoritative MAGI sequence tracks (projectId-scoped)."""
    from ....magi.sequence.store import get_sequence

    seq = get_sequence(ctx.project_id)
    return {
        "projectId": ctx.project_id,
        "tracks": seq.get("tracks") or [],
        "_evidence": {"source": "magi.sequence.store.get_sequence"},
    }


async def inspect_selection(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Surface the authoritative persisted playhead position.

    Clip *selection* is ephemeral in-editor UI state and is never persisted, so
    this tool reports the server-owned ``playheadFrame`` only and states that
    explicitly rather than fabricating a selection (Tool Law: READ authoritative
    state; no frontend-derived state).
    """
    from ....magi.sequence.store import get_sequence

    seq = get_sequence(ctx.project_id)
    return {
        "projectId": ctx.project_id,
        "selection": {
            "playheadFrame": seq.get("playheadFrame") or 0,
            "source": "sequence.playheadFrame",
        },
        "note": (
            "Clip selection is ephemeral editor UI state and is not persisted; "
            "only the server-owned playhead frame is reported."
        ),
        "_evidence": {"source": "magi.sequence.store.get_sequence"},
    }


async def inspect_timeline_lineage(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Read the m5 timeline-export provenance ledger (projectId-scoped, read-only)."""
    from ....magi.sequence.store import get_sequence

    seq = get_sequence(ctx.project_id)
    ledger = dict(seq.get("exportLedger") or {})
    return {
        "projectId": ctx.project_id,
        "exportLedger": ledger,
        "exportedBatchBlockIds": sorted(ledger.keys()),
        "exportedClipCount": sum(len(entry.get("clips") or []) for entry in ledger.values()),
        "_evidence": {"source": "magi.sequence.store.get_sequence"},
    }


async def readiness(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Surface MAGI editor readiness as a compact structured summary (read-only)."""
    from ....magi.readiness import readiness_payload

    payload = readiness_payload()
    deferred = payload.get("deferredSurfaces") or []
    return {
        "status": "ready" if payload.get("noFakeExecution") else "degraded",
        "phase": payload.get("phase"),
        "productName": payload.get("productName"),
        "noFakeExecution": bool(payload.get("noFakeExecution")),
        "productionSurfaceCount": len(payload.get("productionSurfaces") or []),
        "deferredSurfaceIds": [s.get("id") for s in deferred],
        "honestNonExecutableCount": payload.get("honestNonExecutableCount"),
        "_evidence": {"source": "magi.readiness"},
    }


async def inspect_post_context(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Assemble the freeze PostProductionContextPackage (READ assembler only)."""
    domains = args.get("domains") or args.get("domain") or "all"
    scene_id = str(args.get("sceneId") or ctx.scene_id or "").strip() or None
    package = assemble_post_production_context(
        ctx.db,
        ctx.project_id,
        domains=domains,
        scene_id=scene_id,
        include_timeline_publish=bool(args.get("includeTimelinePublish", False)),
        include_presets=bool(args.get("includePresets", False)),
        include_jobs=bool(args.get("includeJobs", False)),
        include_receipts=bool(args.get("includeReceipts", False)),
    )
    return {
        "projectId": ctx.project_id,
        "postProductionContext": package,
        "_evidence": package.get("_evidence")
        or {"source": "magi.inspect_post_context"},
    }


async def inspect_grade(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Read clip grades + color preset catalog from real MAGI finishing/color APIs."""
    from ....magi.color_grading import list_color_presets
    from ....magi.finishing import clip_grade, finishing_of
    from ....magi.sequence.store import get_sequence

    seq = get_sequence(ctx.project_id)
    finishing = finishing_of(seq)
    grades = dict(finishing.get("clipGrades") or {})
    clip_id = str(args.get("clipId") or "").strip() or None
    focused = clip_grade(seq, clip_id) if clip_id else None
    presets = list_color_presets()
    return {
        "projectId": ctx.project_id,
        "clipId": clip_id,
        "clipGrade": focused,
        "clipGrades": grades,
        "presets": presets,
        "presetCount": len(presets),
        "_evidence": {
            "source": "magi.finishing + magi.color_grading.list_color_presets",
        },
    }


async def inspect_job(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """MAGI job status for VERIFY (JobStore rows with kind magi_* — not PE JobStore)."""
    from ....db import Job
    from ....magi.jobs import ACTIVE, TERMINAL

    job_id = str(args.get("jobId") or "").strip()
    if not job_id:
        raise CoDirectorError(TOOL_TARGET_NOT_FOUND, "jobId is required")
    job = ctx.db.get(Job, job_id)
    if job is None or job.project_id != ctx.project_id:
        raise CoDirectorError(
            TOOL_TARGET_NOT_FOUND,
            f"MAGI job '{job_id}' not found in project '{ctx.project_id}'.",
        )
    if not str(job.kind or "").startswith("magi_"):
        raise CoDirectorError(
            TOOL_TARGET_NOT_FOUND,
            (
                f"Job '{job_id}' kind '{job.kind}' is not a MAGI job. "
                "Use Production Executive inspect_job for non-MAGI jobs."
            ),
        )
    history: dict[str, Any] = {}
    try:
        history = json.loads(job.history_json or "{}")
    except Exception:
        history = {}
    status = str(job.status or "")
    unified = None
    try:
        from ....codirector.unified_jobs import to_unified_dto
        unified = to_unified_dto("studio", job)
    except Exception:
        unified = None
    unified_status = str((unified or {}).get("status") or status)
    terminal_truth = status == "done" or unified_status == "completed" or status in TERMINAL
    return {
        "projectId": ctx.project_id,
        "jobId": job.id,
        "kind": job.kind,
        "status": status,
        "unifiedStatus": unified_status,
        "stage": job.stage,
        "progress": job.progress,
        "message": job.message,
        "outputPath": job.output_path,
        "history": history,
        "isActive": status in ACTIVE and not terminal_truth,
        "isTerminal": bool(terminal_truth),
        "jobDoneTruth": bool(status == "done" or unified_status == "completed"),
        "jobStore": "magi.jobs / db.Job (kind magi_*)",
        "note": "This is MAGI job inspect — not Production Executive JobStore. Poll truth: status=done OR unifiedStatus=completed.",
        "_evidence": {"source": "db.Job", "kind": job.kind},
    }


async def verify_action(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Re-run MagiActionReceipt VERIFY checks (sequence/finishing/job re-read)."""
    tool_id = str(args.get("toolId") or "").strip()
    if not tool_id:
        raise CoDirectorError(TOOL_TARGET_NOT_FOUND, "toolId is required")
    clip_id = str(args.get("clipId") or "").strip() or None
    preset_id = str(args.get("presetId") or "").strip() or None
    job_id = str(args.get("jobId") or "").strip() or None
    asset_ids_in = args.get("assetIdsIn") or []
    asset_ids_out = args.get("assetIdsOut") or []
    if isinstance(asset_ids_in, str):
        asset_ids_in = [asset_ids_in]
    if isinstance(asset_ids_out, str):
        asset_ids_out = [asset_ids_out]
    verify = verify_magi_action(
        ctx.db,
        ctx.project_id,
        tool_id=tool_id,
        clip_id=clip_id,
        asset_ids_in=[str(x) for x in asset_ids_in],
        asset_ids_out=[str(x) for x in asset_ids_out],
        job_id=job_id,
        preset_id=preset_id,
    )
    receipt = build_receipt(
        action_id=str(args.get("actionId") or new_action_id()),
        tool_id=tool_id,
        status=verify["status"],
        asset_ids_in=[str(x) for x in asset_ids_in],
        asset_ids_out=[str(x) for x in asset_ids_out],
        job_id=job_id,
        evidence=verify.get("evidence") or {},
        verify_plan=verify.get("verifyPlan"),
        verified_at=verify.get("verifiedAt"),
        applied_at=str(args.get("appliedAt") or "") or None,
        error=None if verify.get("ok") else "verify_failed",
    )
    return {
        "projectId": ctx.project_id,
        "verify": verify,
        "magiActionReceipt": receipt,
        "_evidence": {"source": "magi.verify_action", "reRead": True},
    }


def _preview(summary: str, *lines: str):
    from ..definitions import ToolPreview

    return ToolPreview(
        summary=summary,
        lines=list(lines) + ["Source media stays intact. Approval required."],
        warnings=["This writes MAGI finishing state or queues a job."],
    )


def preview_color_apply(ctx: ToolContext, args: dict[str, Any]):
    return _preview(
        "Apply MAGI color look",
        f"preset={args.get('presetId') or 'custom'}",
        f"asset={args.get('assetId')}",
    )


def apply_color_apply(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....magi.color_grading import apply_color_grade_to_asset
    from ....magi.finishing import set_clip_grade

    requested_at = utc_now()
    action_id = new_action_id()
    asset_id = str(args.get("assetId") or "")
    preset_id = str(args.get("presetId") or "")
    clip_id = str(args.get("clipId") or "") or None
    try:
        result = apply_color_grade_to_asset(ctx.db, ctx.project_id, asset_id, preset_id, {})
        if clip_id:
            set_clip_grade(ctx.project_id, clip_id, preset_id, {})
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc)[:800],
            "magiActionReceipt": build_receipt(
                action_id=action_id,
                tool_id="magi.color.apply",
                status="failed",
                asset_ids_in=[asset_id] if asset_id else [],
                error=str(exc)[:800],
                requested_at=requested_at,
                domain="color",
            ),
        }
    return wrap_apply_result(
        tool_id="magi.color.apply",
        domain="color",
        apply_result=result,
        asset_ids_in=[asset_id] if asset_id else [],
        db=ctx.db,
        project_id=ctx.project_id,
        clip_id=clip_id,
        preset_id=preset_id or None,
        action_id=action_id,
        requested_at=requested_at,
    )


def _resolve_graphics_source_asset_id(ctx: ToolContext, args: dict[str, Any]) -> str | None:
    """Pick the overlay target asset: explicit arg, published master, or first picture clip."""
    asset_id = str(args.get("assetId") or "").strip() or None
    if asset_id:
        return asset_id
    if ctx.scene_id:
        from ....magi.published_master_ingest import resolve_published_master_id
        published = resolve_published_master_id(ctx.db, ctx.project_id, ctx.scene_id)
        if published.get("ok") and published.get("publishedAssetId"):
            return str(published["publishedAssetId"])
    from ....magi.sequence.store import get_sequence
    seq = get_sequence(ctx.project_id)
    track_kinds = {t.get("id"): t.get("kind") for t in seq.get("tracks") or []}
    for clip in seq.get("clips") or []:
        if track_kinds.get(clip.get("trackId")) in {"video", "image"} and clip.get("assetId"):
            return str(clip["assetId"])
    return None


def _load_or_create_overlay_composition(ctx: ToolContext, source_asset_id: str | None) -> dict[str, Any]:
    from ....magi.overlays import store as overlay_store
    if source_asset_id:
        return overlay_store.get_or_create_for_asset(ctx.project_id, source_asset_id=source_asset_id)
    items = overlay_store.list_compositions(ctx.project_id)
    for item in items:
        full = overlay_store.get_composition(ctx.project_id, item.get("compositionId") or "")
        if full:
            return full
    comp = {
        "schemaVersion": 1,
        "compositionId": str(uuid.uuid4()),
        "projectId": ctx.project_id,
        "sourceAssetId": None,
        "canvasWidth": 1920,
        "canvasHeight": 1080,
        "overlays": [],
        "safeAreaEnabled": True,
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    }
    return overlay_store.save_composition(ctx.project_id, comp)


def _frames_from_seconds(args: dict[str, Any], fps: int) -> tuple[int | None, int | None]:
    start = args.get("startSeconds")
    end = args.get("endSeconds")
    if start is None and end is None:
        return None, None
    sf = round(float(start)) if start is not None else None
    ef = round(float(end)) if end is not None else None
    if sf is not None and fps:
        sf = round(sf * fps)
    if ef is not None and fps:
        ef = round(ef * fps)
    return sf, ef


def _make_text_element(args: dict[str, Any], index: int, start: int | None, end: int | None) -> dict[str, Any]:
    now_ts = utc_now()
    text = str(args.get("text") or "")
    return {
        "id": f"txt-{uuid.uuid4().hex[:8]}",
        "type": "text",
        "name": "Text",
        "visible": True,
        "locked": False,
        "opacity": 1,
        "x": float(args.get("x", 0.1)),
        "y": float(args.get("y", 0.1)),
        "width": float(args.get("width", 0.4)),
        "height": float(args.get("height", 0.08)),
        "rotation": 0,
        "anchorX": 0,
        "anchorY": 0,
        "zIndex": 10 + index,
        "startFrame": start,
        "endFrame": end,
        "createdAt": now_ts,
        "updatedAt": now_ts,
        "text": text,
        "textStyle": {
            "fontFamily": "dejavu-sans",
            "fontSize": int(args.get("fontSize", 48)),
            "fontWeight": 700,
            "fontStyle": "normal",
            "textDecoration": "none",
            "color": "#FFFFFF",
            "alignment": "left",
            "verticalAlignment": "middle",
            "lineHeight": 1.2,
            "letterSpacing": 0,
            "wordSpacing": 0,
            "uppercase": False,
            "maxLines": None,
            "autoFit": False,
            "strokeColor": None,
            "strokeWidth": 0,
            "shadowEnabled": True,
            "shadowColor": "#000000",
            "shadowBlur": 4,
            "shadowOffsetX": 1,
            "shadowOffsetY": 1,
        },
        "backgroundStyle": {
            "enabled": False,
            "fill": "#000000",
            "opacity": 0.55,
            "paddingTop": 8,
            "paddingRight": 14,
            "paddingBottom": 8,
            "paddingLeft": 14,
            "cornerRadius": 4,
            "borderEnabled": False,
            "borderColor": "#FFFFFF",
            "borderWidth": 1,
            "autoSize": True,
            "fixedWidth": None,
        },
        "animationPreset": None,
    }


def _make_vector_element(args: dict[str, Any], index: int, start: int | None, end: int | None) -> dict[str, Any]:
    now_ts = utc_now()
    return {
        "id": f"vec-{uuid.uuid4().hex[:8]}",
        "type": "vector",
        "name": str(args.get("shape") or "rectangle"),
        "visible": True,
        "locked": False,
        "opacity": 1,
        "x": float(args.get("x", 0.1)),
        "y": float(args.get("y", 0.78)),
        "width": float(args.get("width", 0.2)),
        "height": float(args.get("height", 0.2)),
        "rotation": 0,
        "anchorX": 0,
        "anchorY": 0,
        "zIndex": 5 + index,
        "startFrame": start,
        "endFrame": end,
        "createdAt": now_ts,
        "updatedAt": now_ts,
        "shape": str(args.get("shape") or "rectangle"),
        "fill": "#7c3aed",
        "stroke": None,
        "strokeWidth": 0,
        "cornerRadius": 0,
    }


def _make_image_element(args: dict[str, Any], index: int, start: int | None, end: int | None) -> dict[str, Any]:
    now_ts = utc_now()
    return {
        "id": f"img-{uuid.uuid4().hex[:8]}",
        "type": "image",
        "name": "Image",
        "visible": True,
        "locked": False,
        "opacity": 1,
        "x": float(args.get("x", 0.1)),
        "y": float(args.get("y", 0.1)),
        "width": float(args.get("width", 0.3)),
        "height": float(args.get("height", 0.3)),
        "rotation": 0,
        "anchorX": 0,
        "anchorY": 0,
        "zIndex": 10 + index,
        "startFrame": start,
        "endFrame": end,
        "createdAt": now_ts,
        "updatedAt": now_ts,
        "assetId": str(args.get("assetId") or ""),
        "fit": "contain",
    }


def _make_lower_third_group(args: dict[str, Any], index: int, start: int | None, end: int | None) -> dict[str, Any]:
    now_ts = utc_now()
    primary = str(args.get("primary") or "ANADRIYA")
    secondary = str(args.get("secondary") or "Current Adept")
    group_id = f"grp-{uuid.uuid4().hex[:8]}"
    gx = float(args.get("x", 0.06))
    gy = float(args.get("y", 0.78))
    gw = float(args.get("width", 0.46))
    gh = float(args.get("height", 0.11))
    bar = {
        "id": f"vec-{uuid.uuid4().hex[:8]}",
        "type": "vector",
        "name": "bar",
        "visible": True,
        "locked": False,
        "opacity": 0.82,
        "x": gx,
        "y": gy,
        "width": gw,
        "height": gh,
        "rotation": 0,
        "anchorX": 0,
        "anchorY": 0,
        "zIndex": 1,
        "startFrame": None,
        "endFrame": None,
        "createdAt": now_ts,
        "updatedAt": now_ts,
        "shape": "rectangle",
        "fill": "#111827",
        "stroke": None,
        "strokeWidth": 0,
        "cornerRadius": 0,
    }
    accent = {
        "id": f"vec-{uuid.uuid4().hex[:8]}",
        "type": "vector",
        "name": "accent",
        "visible": True,
        "locked": False,
        "opacity": 1,
        "x": gx,
        "y": gy,
        "width": 0.01,
        "height": gh,
        "rotation": 0,
        "anchorX": 0,
        "anchorY": 0,
        "zIndex": 2,
        "startFrame": None,
        "endFrame": None,
        "createdAt": now_ts,
        "updatedAt": now_ts,
        "shape": "rectangle",
        "fill": "#a78bfa",
        "stroke": None,
        "strokeWidth": 0,
        "cornerRadius": 0,
    }
    p_text = {
        "id": f"txt-{uuid.uuid4().hex[:8]}",
        "type": "text",
        "name": "Primary",
        "visible": True,
        "locked": False,
        "opacity": 1,
        "x": gx + 0.03,
        "y": gy + 0.005,
        "width": gw - 0.06,
        "height": gh * 0.45,
        "rotation": 0,
        "anchorX": 0,
        "anchorY": 0,
        "zIndex": 3,
        "startFrame": None,
        "endFrame": None,
        "createdAt": now_ts,
        "updatedAt": now_ts,
        "text": primary,
        "textStyle": {
            "fontFamily": "dejavu-sans",
            "fontSize": 40,
            "fontWeight": 700,
            "fontStyle": "normal",
            "textDecoration": "none",
            "color": "#FFFFFF",
            "alignment": "left",
            "verticalAlignment": "middle",
            "lineHeight": 1.2,
            "letterSpacing": 0,
            "wordSpacing": 0,
            "uppercase": True,
            "maxLines": None,
            "autoFit": False,
            "strokeColor": None,
            "strokeWidth": 0,
            "shadowEnabled": True,
            "shadowColor": "#000000",
            "shadowBlur": 4,
            "shadowOffsetX": 1,
            "shadowOffsetY": 1,
        },
        "backgroundStyle": {
            "enabled": False,
            "fill": "#000000",
            "opacity": 0.55,
            "paddingTop": 8,
            "paddingRight": 14,
            "paddingBottom": 8,
            "paddingLeft": 14,
            "cornerRadius": 4,
            "borderEnabled": False,
            "borderColor": "#FFFFFF",
            "borderWidth": 1,
            "autoSize": True,
            "fixedWidth": None,
        },
        "animationPreset": None,
    }
    s_text = {
        "id": f"txt-{uuid.uuid4().hex[:8]}",
        "type": "text",
        "name": "Secondary",
        "visible": True,
        "locked": False,
        "opacity": 1,
        "x": gx + 0.03,
        "y": gy + gh * 0.55,
        "width": gw - 0.06,
        "height": gh * 0.4,
        "rotation": 0,
        "anchorX": 0,
        "anchorY": 0,
        "zIndex": 4,
        "startFrame": None,
        "endFrame": None,
        "createdAt": now_ts,
        "updatedAt": now_ts,
        "text": secondary,
        "textStyle": {
            "fontFamily": "dejavu-sans",
            "fontSize": 22,
            "fontWeight": 400,
            "fontStyle": "normal",
            "textDecoration": "none",
            "color": "#FFFFFF",
            "alignment": "left",
            "verticalAlignment": "middle",
            "lineHeight": 1.2,
            "letterSpacing": 0,
            "wordSpacing": 0,
            "uppercase": False,
            "maxLines": None,
            "autoFit": False,
            "strokeColor": None,
            "strokeWidth": 0,
            "shadowEnabled": True,
            "shadowColor": "#000000",
            "shadowBlur": 4,
            "shadowOffsetX": 1,
            "shadowOffsetY": 1,
        },
        "backgroundStyle": {
            "enabled": False,
            "fill": "#000000",
            "opacity": 0.55,
            "paddingTop": 8,
            "paddingRight": 14,
            "paddingBottom": 8,
            "paddingLeft": 14,
            "cornerRadius": 4,
            "borderEnabled": False,
            "borderColor": "#FFFFFF",
            "borderWidth": 1,
            "autoSize": True,
            "fixedWidth": None,
        },
        "animationPreset": None,
    }
    return {
        "id": group_id,
        "type": "group",
        "name": "Lower Third",
        "visible": True,
        "locked": False,
        "opacity": 1,
        "x": float(args.get("x", 0.06)),
        "y": float(args.get("y", 0.78)),
        "width": float(args.get("width", 0.46)),
        "height": float(args.get("height", 0.11)),
        "rotation": 0,
        "anchorX": 0,
        "anchorY": 0,
        "zIndex": 20 + index,
        "startFrame": start,
        "endFrame": end,
        "createdAt": now_ts,
        "updatedAt": now_ts,
        "groupKind": "lower_third",
        "animationPreset": "fade",
        "children": [bar, accent, p_text, s_text],
    }


_PERSISTENT_OBJECT_RE = re.compile(r"\b(logo|watermark|bug)\b", re.I)


def _resolve_objects_track(kind: str, args: dict[str, Any]) -> int:
    raw = args.get("objectsTrack")
    if raw in (1, 2, "1", "2"):
        return int(raw)
    blob = " ".join(
        str(args.get(key) or "")
        for key in ("text", "primary", "name", "role", "hint", "intent")
    )
    if kind == "image" and (_PERSISTENT_OBJECT_RE.search(blob) or bool(args.get("persistent"))):
        return 2
    return 1


def preview_graphics_apply(ctx: ToolContext, args: dict[str, Any]):
    kind = str(args.get("kind") or "text")
    slot = _resolve_objects_track(kind, args)
    return _preview(
        f"Add MAGI {kind} on Objects {slot}",
        f"kind={kind}",
        f"objectsTrack={slot}",
        f"text={str(args.get('text') or args.get('primary') or '')[:80]}",
        f"startSeconds={args.get('startSeconds')}, endSeconds={args.get('endSeconds')}",
        "Adds an Objects overlay on the published master. Titles and lower thirds go to Objects 1; persistent logos go to Objects 2.",
    )


def apply_graphics_apply(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....magi.sequence.store import get_sequence
    from ....magi.overlays import store as overlay_store

    requested_at = utc_now()
    action_id = new_action_id()
    kind = str(args.get("kind") or "text")
    objects_track = _resolve_objects_track(kind, args)
    seq = get_sequence(ctx.project_id)
    fps = max(int(seq.get("frameRate") or 24), 1)
    start, end = _frames_from_seconds(args, fps)

    source_asset_id = _resolve_graphics_source_asset_id(ctx, args)
    comp = _load_or_create_overlay_composition(ctx, source_asset_id)
    index = len(comp.get("overlays") or [])

    if kind == "text":
        element = _make_text_element(args, index, start, end)
    elif kind == "lower_third":
        element = _make_lower_third_group(args, index, start, end)
    elif kind == "shape":
        element = _make_vector_element(args, index, start, end)
    elif kind == "image":
        element = _make_image_element(args, index, start, end)
    else:
        return {
            "ok": False,
            "error": f"Unsupported objects kind: {kind}",
            "magiActionReceipt": build_receipt(
                action_id=action_id,
                tool_id="magi.graphics.apply",
                status="refused",
                error=f"Unsupported objects kind: {kind}",
                requested_at=requested_at,
                domain="graphics",
            ),
        }

    element["objectsTrack"] = objects_track
    comp["overlays"] = list(comp.get("overlays") or []) + [element]
    try:
        saved = overlay_store.save_composition(ctx.project_id, comp)
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc)[:800],
            "magiActionReceipt": build_receipt(
                action_id=action_id,
                tool_id="magi.graphics.apply",
                status="failed",
                error=str(exc)[:800],
                requested_at=requested_at,
                domain="graphics",
            ),
        }

    return wrap_apply_result(
        tool_id="magi.graphics.apply",
        domain="graphics",
        apply_result={
            "ok": True,
            "compositionId": saved.get("compositionId"),
            "sourceAssetId": saved.get("sourceAssetId"),
            "overlayCount": len(saved.get("overlays") or []),
            "objectsTrack": objects_track,
            "overlayId": element.get("id"),
        },
        asset_ids_in=[source_asset_id] if source_asset_id else [],
        db=ctx.db,
        project_id=ctx.project_id,
        action_id=action_id,
        requested_at=requested_at,
    )


def preview_upscale(ctx: ToolContext, args: dict[str, Any]):
    return _preview(
        "Queue MAGI upscale",
        f"engine={args.get('engine') or 'ffmpeg-scale'}",
        f"asset={args.get('assetId')}",
        "Does NOT persist Timeline scenePublish (Timeline Publish path is separate).",
    )


def apply_upscale(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....magi.upscaling import enqueue_upscale

    requested_at = utc_now()
    action_id = new_action_id()
    asset_id = str(args.get("assetId") or "")
    try:
        result = enqueue_upscale(
            ctx.db,
            project_id=ctx.project_id,
            asset_id=asset_id,
            engine=str(args.get("engine") or "ffmpeg-scale"),
            model=str(args.get("model") or "lanczos"),
            target_resolution=str(args.get("target") or "1920x1080"),
            preview=False,
        )
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc)[:800],
            "magiActionReceipt": build_receipt(
                action_id=action_id,
                tool_id="magi.upscale",
                status="failed",
                asset_ids_in=[asset_id] if asset_id else [],
                error=str(exc)[:800],
                requested_at=requested_at,
                domain="upscale",
            ),
        }
    return wrap_apply_result(
        tool_id="magi.upscale",
        domain="upscale",
        apply_result=result if isinstance(result, dict) else {"ok": True, "raw": result},
        asset_ids_in=[asset_id] if asset_id else [],
        db=ctx.db,
        project_id=ctx.project_id,
        action_id=action_id,
        requested_at=requested_at,
    )


def preview_audio_generate(ctx: ToolContext, args: dict[str, Any]):
    return _preview(
        "Generate MAGI music or SFX",
        str(args.get("prompt") or "")[:180],
        f"kind={args.get('kind')}",
    )


def apply_audio_generate(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....magi.audio_generate import enqueue_audio

    requested_at = utc_now()
    action_id = new_action_id()
    try:
        result = enqueue_audio(ctx.db, ctx.project_id, dict(args))
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc)[:800],
            "magiActionReceipt": build_receipt(
                action_id=action_id,
                tool_id="magi.audio.generate",
                status="failed",
                error=str(exc)[:800],
                requested_at=requested_at,
                domain="music" if str(args.get("kind")) == "music" else "sound",
            ),
        }
    domain = "music" if str(args.get("kind") or "") == "music" else "sound"
    return wrap_apply_result(
        tool_id="magi.audio.generate",
        domain=domain,
        apply_result=result if isinstance(result, dict) else {"ok": True, "raw": result},
        asset_ids_in=[],
        db=ctx.db,
        project_id=ctx.project_id,
        clip_id=str(args.get("clipId") or "") or None,
        action_id=action_id,
        requested_at=requested_at,
    )


_FINISH_NOT_SUPPORTED = (
    {
        "code": "NOT_SUPPORTED",
        "capability": "eq",
        "message": "EQ, compression, limiter, and de-ess are not MAGI engines.",
    },
    {
        "code": "NOT_SUPPORTED",
        "capability": "surround_5_1",
        "message": "5.1 / spatial surround is not available.",
    },
    {
        "code": "NOT_SUPPORTED",
        "capability": "frame_interpolation",
        "message": "Frame interpolation and fps conversion are not available. Source fps is reported only.",
    },
)


def _finish_intent_text(args: dict[str, Any]) -> str:
    return " ".join(
        str(args.get(key) or "")
        for key in ("intent", "prompt", "command")
    ).strip()


def _finish_plan(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....magi.published_master_ingest import resolve_published_master_id
    from ....magi.sequence.store import get_sequence

    scene_id = str(args.get("sceneId") or ctx.scene_id or "").strip()
    intent = _finish_intent_text(args).lower()
    no_music = bool(args.get("noMusic")) or bool(
        re.search(r"\bno music\b|\bwithout music\b|\bmusic:?\s*none\b", intent)
    )
    keep_audio = bool(args.get("keepOriginalAudio")) or bool(
        re.search(r"keep original audio|audio untouched|do not (change|touch) (the )?audio", intent)
    )
    want_4k = bool(re.search(r"\b4k\b|3840\s*[x×]\s*2160|2160p", intent))
    want_2k = bool(args.get("upscaleTarget")) or bool(
        re.search(r"\b2k\b|2560\s*[x×]\s*1440|1440p", intent)
    )
    wants_unsupported = bool(
        re.search(
            r"\beq\b|equalizer|de-?ess|compressor|limiter|5\.1|surround|spatial audio|interpolat|60\s*fps|change (the )?frame rate",
            intent,
        )
    )
    published = {"ok": False, "publishedAssetId": ""}
    if scene_id:
        published = resolve_published_master_id(ctx.db, ctx.project_id, scene_id)
    asset_id = str(args.get("assetId") or published.get("publishedAssetId") or "").strip()
    seq = get_sequence(ctx.project_id)
    master_clip = next(
        (
            clip
            for clip in (seq.get("clips") or [])
            if clip.get("ingestRole") == "published_master"
            and (not scene_id or str(clip.get("sceneId") or "") == scene_id)
        ),
        None,
    )
    if master_clip and not asset_id:
        asset_id = str(master_clip.get("assetId") or "")
    fps = seq.get("frameRate") or 24
    target = str(
        args.get("upscaleTarget")
        or ("3840x2160" if want_4k else "2560x1440" if want_2k else "")
    )
    preset_id = str(args.get("presetId") or "cinematic_neutral")
    generate_music = (not no_music) and bool(re.search(r"\bmusic\b|\bscore\b|\bsoundtrack\b", intent))
    generate_sfx = (not keep_audio) and bool(re.search(r"\bsfx\b|\bsound effects?\b", intent))
    return {
        "sceneId": scene_id or None,
        "publishedAssetId": str(published.get("publishedAssetId") or "") or None,
        "assetId": asset_id or None,
        "clipId": (master_clip or {}).get("id"),
        "sourceFps": fps,
        "grade": {"enabled": True, "presetId": preset_id},
        "audio": {
            "keepOriginal": keep_audio or not generate_music,
            "generateMusic": bool(generate_music and not keep_audio and not no_music),
            "generateSfx": bool(generate_sfx),
            "music": None if (no_music or keep_audio or not generate_music) else "generate",
        },
        "upscale": {"enabled": bool(target), "target": target or None, "engine": str(args.get("engine") or "ffmpeg-scale")},
        "render": {"enabled": bool(args.get("finalRender", False))},
        "notSupported": list(_FINISH_NOT_SUPPORTED),
        "requestedUnsupported": wants_unsupported,
        "sourcePreserved": True,
        "publishedRequired": not bool(published.get("ok")) and bool(scene_id),
        "publishedError": None if published.get("ok") or not scene_id else published.get("error"),
    }


def preview_propose_finish(ctx: ToolContext, args: dict[str, Any]):
    plan = _finish_plan(ctx, args)
    lines = [
        f"source={plan.get('assetId') or 'unpublished'}",
        f"grade={plan['grade']['presetId']}",
        f"music={plan['audio']['music']}",
        f"keepOriginalAudio={plan['audio']['keepOriginal']}",
        f"upscale={plan['upscale']['target'] or 'none'}",
        f"sourceFps={plan['sourceFps']} (reported only; not changed)",
        "NOT_SUPPORTED: EQ, 5.1/surround, frame interpolation",
    ]
    warnings = ["This writes MAGI finishing state or queues a job."]
    if plan.get("publishedRequired"):
        warnings.append("This scene has no published master. Publish on Timeline first.")
    if plan.get("requestedUnsupported"):
        warnings.append("Requested EQ / 5.1 / fps interpolation will be refused. Supported finishing can still run.")
    from ..definitions import ToolPreview

    return ToolPreview(
        summary="Propose MAGI finish of the published scene master",
        lines=lines + ["Source media stays intact. Approval required."],
        warnings=warnings,
    )


def apply_propose_finish(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    requested_at = utc_now()
    action_id = new_action_id()
    plan = _finish_plan(ctx, args)
    if plan.get("publishedRequired"):
        return {
            "ok": False,
            "error": "PUBLISHED_MASTER_REQUIRED",
            "message": "Publish this scene on Timeline first.",
            "plan": plan,
            "magiActionReceipt": build_receipt(
                action_id=action_id,
                tool_id="magi.propose_finish",
                status="refused",
                error="PUBLISHED_MASTER_REQUIRED",
                requested_at=requested_at,
                domain="finish",
            ),
        }
    if bool(args.get("requireUnsupported")):
        return {
            "ok": False,
            "error": "NOT_SUPPORTED",
            "message": "EQ, 5.1, and frame interpolation are not MAGI engines.",
            "plan": plan,
            "notSupported": plan["notSupported"],
            "magiActionReceipt": build_receipt(
                action_id=action_id,
                tool_id="magi.propose_finish",
                status="refused",
                error="NOT_SUPPORTED",
                requested_at=requested_at,
                domain="finish",
            ),
        }
    asset_id = str(plan.get("assetId") or "")
    if not asset_id:
        return {
            "ok": False,
            "error": "ASSET_REQUIRED",
            "message": "No published master or assetId to finish.",
            "plan": plan,
            "magiActionReceipt": build_receipt(
                action_id=action_id,
                tool_id="magi.propose_finish",
                status="failed",
                error="ASSET_REQUIRED",
                requested_at=requested_at,
                domain="finish",
            ),
        }

    steps: list[dict[str, Any]] = []
    current_asset = asset_id
    if plan["grade"]["enabled"]:
        color_args = {
            "assetId": current_asset,
            "presetId": plan["grade"]["presetId"],
            "clipId": plan.get("clipId") or "",
        }
        color_result = apply_color_apply(ctx, color_args)
        steps.append({"toolId": "magi.color.apply", "result": color_result})
        out = str(color_result.get("output_asset_id") or color_result.get("assetId") or "")
        if out:
            current_asset = out
        if color_result.get("ok") is False:
            return {**color_result, "ok": False, "plan": plan, "steps": steps}

    if plan["audio"]["generateMusic"]:
        music_result = apply_audio_generate(
            ctx,
            {"kind": "music", "prompt": str(args.get("musicPrompt") or args.get("prompt") or "subtle score"), "range": "entire"},
        )
        steps.append({"toolId": "magi.audio.generate", "result": music_result})
    if plan["audio"]["generateSfx"]:
        sfx_result = apply_audio_generate(
            ctx,
            {"kind": "sfx", "prompt": str(args.get("sfxPrompt") or args.get("prompt") or "diegetic accents"), "range": "entire"},
        )
        steps.append({"toolId": "magi.audio.generate", "result": sfx_result})

    if plan["upscale"]["enabled"]:
        up_result = apply_upscale(
            ctx,
            {
                "assetId": current_asset,
                "engine": plan["upscale"]["engine"],
                "model": str(args.get("model") or "lanczos"),
                "target": plan["upscale"]["target"],
            },
        )
        steps.append({"toolId": "magi.upscale", "result": up_result})
        if up_result.get("ok") is False:
            return {**up_result, "ok": False, "plan": plan, "steps": steps}

    if plan["render"]["enabled"]:
        render_result = apply_render(ctx, {"profile": str(args.get("profile") or "final")})
        steps.append({"toolId": "magi.render", "result": render_result})

    apply_result = {
        "ok": True,
        "plan": plan,
        "steps": steps,
        "sourceAssetId": asset_id,
        "output_asset_id": current_asset if current_asset != asset_id else None,
        "sourcePreserved": True,
    }
    return wrap_apply_result(
        tool_id="magi.propose_finish",
        domain="finish",
        apply_result=apply_result,
        asset_ids_in=[asset_id],
        db=ctx.db,
        project_id=ctx.project_id,
        clip_id=str(plan.get("clipId") or "") or None,
        action_id=action_id,
        requested_at=requested_at,
    )


def preview_render(ctx: ToolContext, args: dict[str, Any]):
    return _preview("Queue MAGI finishing render", f"profile={args.get('profile') or 'final'}")


def apply_render(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....magi.final_render import enqueue_final_render

    requested_at = utc_now()
    action_id = new_action_id()
    try:
        result = enqueue_final_render(ctx.db, ctx.project_id, dict(args) or {"profile": "final"})
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc)[:800],
            "magiActionReceipt": build_receipt(
                action_id=action_id,
                tool_id="magi.render",
                status="failed",
                error=str(exc)[:800],
                requested_at=requested_at,
                domain="finish",
            ),
        }
    return wrap_apply_result(
        tool_id="magi.render",
        domain="finish",
        apply_result=result if isinstance(result, dict) else {"ok": True, "raw": result},
        asset_ids_in=[],
        db=ctx.db,
        project_id=ctx.project_id,
        action_id=action_id,
        requested_at=requested_at,
    )
