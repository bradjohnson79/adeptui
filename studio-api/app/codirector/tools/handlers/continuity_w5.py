"""Wave 5 Continuity Co-Director tools — propose/preview only for mutations."""

from __future__ import annotations

from typing import Any

from ....continuity import service as continuity_service
from ....continuity import correction_service
from ...errors import CoDirectorError, TOOL_TARGET_NOT_FOUND
from ..definitions import ToolContext, ToolPreview


async def search_identities(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    items = continuity_service.list_identities(ctx.db, ctx.project_id)
    q = str(args.get("query") or "").strip().lower()
    if q:
        items = [
            i
            for i in items
            if q in (i.get("displayName") or "").lower()
            or q in (i.get("canonicalName") or "").lower()
        ]
    return {"items": items[: int(args.get("limit") or 50)], "_evidence": {"source": "continuity.identities"}}


async def get_identity(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    identity_id = str(args.get("identityId") or "")
    try:
        return {
            **continuity_service.get_identity(ctx.db, ctx.project_id, identity_id),
            "_evidence": {"source": "continuity.identities"},
        }
    except Exception as e:
        raise CoDirectorError(TOOL_TARGET_NOT_FOUND, str(e)) from e


async def get_identity_version(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    identity_id = str(args.get("identityId") or "")
    versions = continuity_service.list_versions(ctx.db, ctx.project_id, identity_id)
    version_id = args.get("versionId")
    if version_id:
        match = next((v for v in versions if v["id"] == version_id), None)
        if not match:
            raise CoDirectorError(TOOL_TARGET_NOT_FOUND, "Version not found")
        return {**match, "_evidence": {"source": "continuity.versions"}}
    return {"items": versions, "_evidence": {"source": "continuity.versions"}}


async def list_variants(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    version_id = str(args.get("versionId") or "")
    return {
        "items": continuity_service.list_variants(ctx.db, ctx.project_id, version_id),
        "_evidence": {"source": "continuity.variants"},
    }


async def get_reference_readiness(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    identity_id = str(args.get("identityId") or "")
    ready = continuity_service.identity_readiness(ctx.db, ctx.project_id, identity_id)
    return {**ready, "_evidence": {"source": "continuity.readiness", "notContinuityScore": True}}


def _parse_bindings(args: dict[str, Any]) -> list[dict[str, Any]]:
    import json

    raw = args.get("bindings") or args.get("bindingsJson")
    if isinstance(raw, list):
        return list(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            data = json.loads(raw)
            return list(data) if isinstance(data, list) else []
        except Exception:
            return []
    return []


async def preview_packet(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    packet_id = args.get("packetId")
    if packet_id:
        return {
            **continuity_service.get_packet(ctx.db, ctx.project_id, str(packet_id)),
            "_evidence": {"source": "continuity.packets"},
        }
    result = continuity_service.preflight(
        ctx.db,
        ctx.project_id,
        {
            "bindings": _parse_bindings(args),
            "workflowSupportsReferences": True,
            "requestId": "codirector-preview",
        },
    )
    return {**result, "_evidence": {"source": "continuity.preflight", "mode": "preview"}}


async def preflight(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    payload = dict(args)
    payload["bindings"] = _parse_bindings(args)
    return {
        **continuity_service.preflight(ctx.db, ctx.project_id, payload),
        "_evidence": {"source": "continuity.preflight"},
    }


async def get_evaluation(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    evaluation_id = str(args.get("evaluationId") or "")
    return {
        **continuity_service.get_evaluation(ctx.db, ctx.project_id, evaluation_id),
        "_evidence": {"source": "continuity.evaluations"},
    }


async def list_issues(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    items = continuity_service.list_issues(ctx.db, ctx.project_id)
    return {"items": items, "_evidence": {"source": "continuity.issues"}}


async def open_workspace(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    target = str(args.get("workspace") or "continuity")
    if target not in ("continuity", "identityregistry", "timeline", "magi", "bible"):
        target = "continuity"
    return {
        "action": "navigate",
        "workspace": target,
        "projectId": ctx.project_id,
        "message": f"Open {target} workspace — no mutation performed.",
        "_evidence": {"source": "continuity.navigation"},
    }


def _dims(args: dict[str, Any]) -> list[str]:
    if args.get("dimensions"):
        return list(args.get("dimensions") or [])
    csv = str(args.get("dimensionsCsv") or "").strip()
    return [p.strip() for p in csv.split(",") if p.strip()] if csv else []


def preview_propose_correction(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    dims = _dims(args)
    return ToolPreview(
        summary="Propose continuity correction (ImageEditIntent path only — no auto-enqueue)",
        lines=[
            f"Source asset: {args.get('sourceAssetId') or '—'}",
            f"Dimensions: {', '.join(dims) or 'overall_identity'}",
            "Creates a correction proposal only; enqueue requires separate user approval.",
            "Deferred/Blocked actions never enqueue.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
        warnings=["Does not approve identities, references, or Production Masters."],
    )


def apply_propose_correction(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Create a correction proposal only — never auto-enqueue."""
    payload = dict(args)
    payload["dimensions"] = _dims(args)
    return correction_service.propose_correction(ctx.db, ctx.project_id, payload)
