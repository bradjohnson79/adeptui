"""MAGI Co-Director READ-only tools (m6).

Capability-scoped, project-ownership-isolated reads. Every call requires an
authoritative ``project_id`` from ``ToolContext``; clips are addressed by their
immutable ``clipId``. No writes or proposals exist in this milestone — MAGI
mutations stay inside the Adept UI editor.

Tool Law contract: READ -> authoritative state; immutable IDs only; no fake
execution; no fabricated sequence content.
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
