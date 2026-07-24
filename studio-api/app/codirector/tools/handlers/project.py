"""Read handlers for project identity and status."""

from __future__ import annotations

from typing import Any

from .... import project_service
from ....db import Project
from ...errors import TOOL_TARGET_NOT_FOUND, CoDirectorError
from ..definitions import ToolContext


def _require_project(ctx: ToolContext) -> Project:
    project = ctx.db.get(Project, ctx.project_id)
    if not project:
        raise CoDirectorError(
            TOOL_TARGET_NOT_FOUND,
            "Project not found.",
            details={"projectId": ctx.project_id},
            recoverable=False,
            recommended_action="none",
        )
    return project


async def get_project_profile(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return project_service.project_profile(_require_project(ctx))


async def get_project_status(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return project_service.project_status(ctx.db, _require_project(ctx))
