"""Production state / memory / candidate read handlers (orchestrator milestone).

Thin read-only wrappers over the production_state projection modules;
never mutate. Every handler is best-effort and bounded.
"""

from __future__ import annotations

from typing import Any

from ..definitions import ToolContext


async def read_production_snapshot(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Compact production state snapshot (mission Part 1)."""
    from ...production_state.snapshot import build_production_snapshot

    return build_production_snapshot(ctx.db, ctx.project_id, ctx.scene_id)


async def read_production_memory(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Structured recent production memory (mission Parts 3-4)."""
    from ...production_state.memory import build_production_memory

    limit = int(args.get("limit") or 10)
    memory = build_production_memory(ctx.db, ctx.project_id, ctx.scene_id)
    memory["toolActions"] = (memory.get("toolActions") or [])[: max(1, min(limit, 50))]
    return memory


async def resolve_production_reference(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Resolve a conversational production reference to candidates (Part 4)."""
    from ...production_state.memory import resolve_reference

    ref = str(args.get("ref") or "").strip()
    return resolve_reference(ctx.db, ctx.project_id, ref, scene_id=ctx.scene_id)


async def list_candidates(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """List recent generation candidates (Part 9)."""
    from ...production_state.snapshot import _candidates

    limit = int(args.get("limit") or 12)
    return {"candidates": _candidates(ctx.db, ctx.project_id, ctx.scene_id)[: max(1, min(limit, 50))]}


async def resolve_candidate(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Resolve a candidate reference (alias of production.resolve_reference)."""
    return await resolve_production_reference(ctx, args)