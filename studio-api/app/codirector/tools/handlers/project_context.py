"""Project context retrieval tool handler for Co-Director.

Read-only unified retrieval of project pillars (story, script, storyboard,
characters, foundation status) through the single authoritative
``app.codirector.project_context`` path. No caching, no duplicate stores.
"""

from __future__ import annotations

from typing import Any

from ..definitions import ToolContext


async def read_project_context(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Read project pillar content for Co-Director reasoning.

    Args:
        ctx: Tool context (carries ``db`` and ``project_id``).
        args: Optional ``pillars`` array selecting which pillars to return.

    Returns:
        Dict keyed by pillar name; absent pillars are ``None``.
    """
    from ...project_context import retrieve_project_context

    raw_pillars = args.get("pillars")
    pillars: list[str] | None = None
    if isinstance(raw_pillars, list):
        pillars = [str(p) for p in raw_pillars if isinstance(p, str) and p]
    return retrieve_project_context(ctx.db, ctx.project_id, pillars)
