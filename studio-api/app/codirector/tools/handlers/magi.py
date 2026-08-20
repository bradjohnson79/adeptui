"""MAGI Co-Director tools.

Read tools inspect authoritative sequence state. Mutation tools write finishing
state or queue jobs and never overwrite source media.
"""

from __future__ import annotations

from typing import Any

from ...errors import CoDirectorError, TOOL_TARGET_NOT_FOUND
from ..definitions import ToolContext


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
    """Read the m5 timeline-export provenance ledger (projectId-scoped, read-only).

    Returns ``sequence.exportLedger`` — the batchBlockId-keyed record of MAGI
    clips placed onto the W46 Timeline (m5). Never mutates or regenerates.
    """
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
    """Surface MAGI editor readiness as a compact structured summary (read-only).

    The full readiness payload (production surfaces, deferred surfaces, actions,
    korri policy) is served to the UI by ``GET /api/magi/readiness``; the
    Co-Director tool intentionally returns a compact summary so the result never
    exceeds the tool envelope budget. Read-only — no execution claims.
    """
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


def _preview(summary: str, *lines: str):
    from ..definitions import ToolPreview

    return ToolPreview(
        summary=summary,
        lines=list(lines) + ["Source media stays intact. Approval required."],
        warnings=["This writes MAGI finishing state or queues a job."],
    )


def preview_color_apply(ctx: ToolContext, args: dict[str, Any]):
    return _preview("Apply MAGI color look", f"preset={args.get('presetId') or 'custom'}", f"asset={args.get('assetId')}")


def apply_color_apply(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....magi.color_grading import apply_color_grade_to_asset
    from ....magi.finishing import set_clip_grade

    asset_id = str(args.get("assetId") or "")
    preset_id = str(args.get("presetId") or "")
    result = apply_color_grade_to_asset(ctx.db, ctx.project_id, asset_id, preset_id, {})
    if args.get("clipId"):
        set_clip_grade(ctx.project_id, str(args["clipId"]), preset_id, {})
    return result


def preview_upscale(ctx: ToolContext, args: dict[str, Any]):
    return _preview("Queue MAGI upscale", f"engine={args.get('engine') or 'ffmpeg-scale'}", f"asset={args.get('assetId')}")


def apply_upscale(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....magi.upscaling import enqueue_upscale

    return enqueue_upscale(
        ctx.db,
        project_id=ctx.project_id,
        asset_id=str(args.get("assetId") or ""),
        engine=str(args.get("engine") or "ffmpeg-scale"),
        model=str(args.get("model") or "lanczos"),
        target_resolution=str(args.get("target") or "1920x1080"),
        preview=False,
    )


def preview_audio_generate(ctx: ToolContext, args: dict[str, Any]):
    return _preview("Generate MAGI music or SFX", str(args.get("prompt") or "")[:180], f"kind={args.get('kind')}")


def apply_audio_generate(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....magi.audio_generate import enqueue_audio

    return enqueue_audio(ctx.db, ctx.project_id, dict(args))


def preview_render(ctx: ToolContext, args: dict[str, Any]):
    return _preview("Queue MAGI finishing render", f"profile={args.get('profile') or 'final'}")


def apply_render(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....magi.final_render import enqueue_final_render

    return enqueue_final_render(ctx.db, ctx.project_id, dict(args) or {"profile": "final"})
