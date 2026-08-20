"""Structured error envelope + canonical error taxonomy for the MAGI API (m8).

All MAGI HTTP errors share one shape so the frontend can render per-pane,
actionable recovery instead of raw trace text:

    {"error": {"code": str, "message": str, "fields": {...}?}}

The taxonomy below is the single source of truth for canonical MAGI error codes
(uppercase), their HTTP status, classification, and creator-facing guidance.
Legacy lowercase codes emitted before m8 are mapped to their canonical code via
``magi_canonical_code`` so callers keep working while the API stabilizes on the
uppercase set.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException


MAGI_ERROR_TAXONOMY: dict[str, dict[str, Any]] = {
    "INVALID_SEQUENCE": {
        "status_code": 400,
        "kind": "validation",
        "message": "The MAGI sequence document is not valid.",
        "recovery": "Re-apply the last edit and save again.",
    },
    "INVALID_REVISION": {
        "status_code": 422,
        "kind": "validation",
        "message": "expectedRevision must be a positive integer.",
    },
    "REVISION_CONFLICT": {
        "status_code": 409,
        "kind": "conflict",
        "message": "The MAGI sequence changed on the server since it was loaded.",
        "recovery": "Reload to see the latest edits, then re-apply yours.",
    },
    "INVALID_CLIP_ASSET": {
        "status_code": 422,
        "kind": "validation",
        "message": "Sequence contains clips without an asset reference.",
    },
    "ASSET_NOT_FOUND": {
        "status_code": 400,
        "kind": "not_found",
        "message": "Sequence references assets that do not exist.",
    },
    "ASSET_PROJECT_MISMATCH": {
        "status_code": 400,
        "kind": "validation",
        "message": "Sequence references assets owned by another project.",
    },
    "ASSET_OWNERSHIP": {
        "status_code": 400,
        "kind": "validation",
        "message": "The asset does not exist in this project.",
    },
    "ASSET_ID_REQUIRED": {
        "status_code": 400,
        "kind": "validation",
        "message": "An assetId is required.",
    },
    "CLIPS_REQUIRED": {
        "status_code": 400,
        "kind": "validation",
        "message": "MAGI timeline export requires a non-empty 'clips' array.",
    },
    "CLIP_NOT_FOUND": {
        "status_code": 404,
        "kind": "not_found",
        "message": "The MAGI sequence does not contain the referenced clip.",
        "recovery": "Refresh the sequence and export again.",
    },
    "SCENE_NOT_FOUND": {
        "status_code": 404,
        "kind": "not_found",
        "message": "The timeline scene does not exist.",
    },
    "BATCH_NOT_FOUND": {
        "status_code": 404,
        "kind": "not_found",
        "message": "The timeline batch block does not exist.",
    },
    "SEQUENCE_NOT_FOUND": {
        "status_code": 404,
        "kind": "not_found",
        "message": "No MAGI sequence exists for this project.",
        "recovery": "Save the sequence once before exporting.",
        # Latent by design: MAGI always serves an empty sequence on read, so this
        # code is part of the contract but does not fire in normal operation.
    },
    "PERSISTENCE_FAILED": {
        "status_code": 500,
        "kind": "persistence",
        "message": "The MAGI sequence could not be persisted.",
        "recovery": "Try saving again in a moment.",
    },
    "RENDER_FAILED": {
        "status_code": 400,
        "kind": "render",
        "message": "MAGI overlay render failed.",
    },
    "OVERLAY_NOT_FOUND": {
        "status_code": 404,
        "kind": "not_found",
        "message": "Composition not found.",
    },
    "OVERLAY_INVALID": {
        "status_code": 400,
        "kind": "validation",
        "message": "Overlay composition failed validation.",
    },
    "IMPORT_FAILED": {
        "status_code": 400,
        "kind": "handoff",
        "message": "MAGI timeline import failed.",
    },
    "EXPORT_FAILED": {
        "status_code": 400,
        "kind": "handoff",
        "message": "MAGI timeline export failed.",
    },
    "TIMELINE_HANDOFF_FAILED": {
        "status_code": 502,
        "kind": "handoff",
        "message": "The clips could not be placed on the timeline.",
        "recovery": "Check the timeline and retry the export.",
    },
    "UNSUPPORTED_OPERATION": {
        "status_code": 400,
        "kind": "unsupported",
        "message": "This MAGI surface is not executable yet.",
        "recovery": "Use the certified image MAGI Actions path instead.",
    },
    "ASSET_REQUIRED": {
        "status_code": 400,
        "kind": "validation",
        "message": "An asset is required.",
    },
    "GPU_UPSCALE_UNAVAILABLE": {
        "status_code": 409,
        "kind": "runtime",
        "message": "GPU Upscaling unavailable. FFmpeg upscale remains available.",
        "recovery": "Install MAGI GPU Upscaling in Setup, or use FFmpeg upscale.",
    },
    "AUDIO_GENERATION_FAILED": {
        "status_code": 400,
        "kind": "runtime",
        "message": "Audio generation failed.",
    },
    "JOB_NOT_FOUND": {
        "status_code": 404,
        "kind": "not_found",
        "message": "MAGI job not found.",
    },
}

MAGI_ERROR_LEGACY_ALIASES: dict[str, str] = {
    "validation_failed": "INVALID_SEQUENCE",
    "revision_conflict": "REVISION_CONFLICT",
    "invalid_revision": "INVALID_REVISION",
    "clips_required": "CLIPS_REQUIRED",
    "import_failed": "IMPORT_FAILED",
    "export_failed": "EXPORT_FAILED",
    "render_failed": "RENDER_FAILED",
    "overlay_not_found": "OVERLAY_NOT_FOUND",
    "overlay_invalid": "OVERLAY_INVALID",
    "asset_ownership": "ASSET_OWNERSHIP",
    "asset_id_required": "ASSET_ID_REQUIRED",
}


def magi_canonical_code(code: str) -> str:
    """Map any known legacy/lowercase code to its canonical uppercase code."""
    if code in MAGI_ERROR_TAXONOMY:
        return code
    return MAGI_ERROR_LEGACY_ALIASES.get(code, code)


def magi_taxonomy(code: str) -> dict[str, Any]:
    """Return the canonical taxonomy entry for a code (empty dict if unknown)."""
    return MAGI_ERROR_TAXONOMY.get(magi_canonical_code(code), {})


def magi_error(
    code: str,
    message: str,
    *,
    status_code: int = 400,
    fields: Optional[dict[str, Any]] = None,
) -> HTTPException:
    """Raise a structured MAGI error envelope with a canonical code."""
    detail: dict[str, Any] = {"error": {"code": magi_canonical_code(code), "message": message}}
    if fields:
        detail["error"]["fields"] = fields
    return HTTPException(status_code=status_code, detail=detail)


def error_envelope(code: str, message: str, *, fields: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Build the envelope dict without raising (for non-HTTP result payloads)."""
    out: dict[str, Any] = {"error": {"code": magi_canonical_code(code), "message": message}}
    if fields:
        out["error"]["fields"] = fields
    return out
