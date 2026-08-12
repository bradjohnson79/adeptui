from __future__ import annotations

from typing import Any

from ...status.registry import StatusContext
from ...status.runner import run_status_check
from ...status.store import latest_run
from ...status.types import DeepDiagnosticRequest, StatusCheckRequest
from ..definitions import ToolContext


async def _run(ctx: ToolContext, *, mode: str = "standard", check_ids: list[str] | None = None) -> dict[str, Any]:
    request = StatusCheckRequest(
        projectId=ctx.project_id,
        sceneId=ctx.scene_id,
        workspace=None,
        checkIds=check_ids or [],
    )
    run = await run_status_check(
        StatusContext(db=ctx.db, project_id=ctx.project_id, scene_id=ctx.scene_id, workspace=None, mode=mode), request, mode=mode  # type: ignore[arg-type]
    )
    return run.model_dump(mode="json")


async def _latest_or_run(ctx: ToolContext) -> dict[str, Any]:
    run = latest_run(project_id=ctx.project_id, scene_id=ctx.scene_id)
    if run is None:
        return await _run(ctx)
    return run.model_dump(mode="json")


async def status_check(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return await _run(ctx)


async def status_summary(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    run = await _latest_or_run(ctx)
    return {
        "runId": run["runId"],
        "checkedAt": run["completedAt"],
        "summary": run["summary"],
        "explainability": run["explainability"],
    }


async def status_check_component(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    check_id = str(args.get("checkId") or "").strip()
    if not check_id:
        return {"ok": False, "status": "blocked", "message": "checkId is required."}
    run = await _run(ctx, check_ids=[check_id])
    return {"runId": run["runId"], "result": run["results"][0] if run["results"] else None}


async def status_list_blockers(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    run = await _latest_or_run(ctx)
    blockers = [result for result in run["results"] if result.get("status") in {"blocked", "failed", "offline", "not_installed", "not_configured"}]
    return {"runId": run["runId"], "blockers": blockers}


async def status_list_warnings(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    run = await _latest_or_run(ctx)
    warnings = [result for result in run["results"] if result.get("status") in {"degraded", "warning", "not_tested", "experimental", "unknown"}]
    return {"runId": run["runId"], "warnings": warnings}


async def status_recovery_options(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    run = await _latest_or_run(ctx)
    actions: list[dict[str, Any]] = []
    for result in run["results"]:
        for action in result.get("recoveryActions") or []:
            actions.append({"checkId": result["checkId"], "checkTitle": result["title"], **action})
    return {"runId": run["runId"], "actions": actions}


async def deep_diagnostic(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    request = DeepDiagnosticRequest(
        projectId=ctx.project_id,
        sceneId=ctx.scene_id,
        workspace=None,
        checkIds=[],
        confirm=bool(args.get("confirm")),
    )
    if not request.confirm:
        return {
            "ok": False,
            "status": "blocked",
            "message": "Deep Diagnostic requires confirm=true.",
            "requiresConfirmation": True,
        }
    run = await run_status_check(
        StatusContext(db=ctx.db, project_id=ctx.project_id, scene_id=ctx.scene_id, workspace=None, mode="deep"),
        request,
        mode="deep",
    )
    return run.model_dump(mode="json")
