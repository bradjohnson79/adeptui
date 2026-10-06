"""Single-CRS production lineage — bind ExecutionPlan children to the real Job.

Wrapper success is orchestration complete, not production complete.
Child job_id must be the visual-sheet Job.id from the pack.
"""

from __future__ import annotations

from typing import Any

from .contracts import ChildJobStatus, ChildJobView, ExecutionPlan, ExecutionStatus

CRS_TOOL_IDS = frozenset({"character_creator.propose_visual_sheet"})
CRS_CAPABILITIES = frozenset(
    {
        "character.generate_visual_sheet",
        "create_character_reference_sheet",
    }
)


def is_crs_tool(tool_id: str) -> bool:
    return (tool_id or "") in CRS_TOOL_IDS


def is_crs_capability(capability: str) -> bool:
    return (capability or "") in CRS_CAPABILITIES


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def extract_crs_pack(tool_result: Any) -> dict[str, Any]:
    result = _as_dict(tool_result)
    pack = result.get("pack")
    if isinstance(pack, dict):
        return pack
    visual = result.get("visualSheet")
    if isinstance(visual, dict):
        return visual
    if result.get("candidates") or result.get("jobs"):
        return result
    return {}


def extract_crs_job_id(pack: dict[str, Any]) -> str | None:
    jobs = _as_dict(pack.get("jobs"))
    hero = jobs.get("hero")
    if isinstance(hero, dict):
        job_id = str(hero.get("jobId") or hero.get("job_id") or "").strip()
        if job_id:
            return job_id
    candidates = pack.get("candidates") or []
    if isinstance(candidates, list) and candidates:
        first = candidates[0] if isinstance(candidates[0], dict) else {}
        job_id = str(first.get("jobId") or first.get("job_id") or "").strip()
        if job_id:
            return job_id
        views = first.get("viewJobs") or []
        if isinstance(views, list) and views and isinstance(views[0], dict):
            job_id = str(views[0].get("jobId") or views[0].get("job_id") or "").strip()
            if job_id:
                return job_id
    return None


def extract_crs_asset_id(pack: dict[str, Any]) -> str | None:
    candidates = pack.get("candidates") or []
    if isinstance(candidates, list) and candidates and isinstance(candidates[0], dict):
        first = candidates[0]
        for key in ("sheetAssetId", "sheet_asset_id", "assetId", "asset_id"):
            value = str(first.get(key) or "").strip()
            if value:
                return value
    jobs = _as_dict(pack.get("jobs"))
    hero = jobs.get("hero") if isinstance(jobs.get("hero"), dict) else {}
    for key in ("sheetAssetId", "assetId", "asset_id"):
        value = str(hero.get(key) or "").strip()
        if value:
            return value
    return None


def extract_crs_character_id(pack: dict[str, Any], tool_result: Any) -> str | None:
    result = _as_dict(tool_result)
    for key in ("characterId", "character_id"):
        value = str(result.get(key) or pack.get(key) or "").strip()
        if value:
            return value
    return None


def bind_crs_child(
    plan: ExecutionPlan,
    *,
    tool_id: str,
    tool_result: Any,
    ok: bool,
    error: str | None,
    fallback_job_id: str,
) -> ExecutionPlan:
    """Attach the real visual-sheet Job as the single ExecutionPlan child."""

    pack = extract_crs_pack(tool_result)
    job_id = extract_crs_job_id(pack) or fallback_job_id
    asset_id = extract_crs_asset_id(pack)
    character_id = extract_crs_character_id(pack, tool_result) or plan.character_id
    production_state = "failed"
    child_status = ChildJobStatus.FAILED
    if ok:
        if asset_id:
            production_state = "completed"
            child_status = ChildJobStatus.COMPLETED
        else:
            production_state = "queued"
            child_status = ChildJobStatus.QUEUED

    plan.character_id = character_id
    plan.plan_data = {
        **dict(plan.plan_data or {}),
        "tool_id": tool_id,
        "tool_invocation_id": str((pack.get("createdAt") or "") or plan.execution_id),
        "production_job_id": job_id,
        "character_id": character_id,
        "sheet_generation_id": str(pack.get("characterId") or character_id or ""),
        "pack_status": pack.get("status"),
        "orchestration_state": "complete" if ok else "failed",
        "production_state": production_state,
        "result_asset_ids": [asset_id] if asset_id else [],
        "crs_revision": pack.get("crsRevision") or pack.get("crs_revision"),
    }
    plan.child_jobs = [
        ChildJobView(
            job_id=job_id,
            label="Character Reference Sheet",
            status=child_status,
            child_index=0,
            asset_id=asset_id,
            error=None if ok else (error or "CRS_ENQUEUE_FAILED"),
            stage="queued" if child_status == ChildJobStatus.QUEUED else child_status.value,
        )
    ]
    plan.result_asset_ids = [asset_id] if asset_id else []
    if not ok:
        plan.status = ExecutionStatus.FAILED
        plan.progress = 0.0
    elif asset_id:
        plan.status = ExecutionStatus.COMPLETED
        plan.progress = 1.0
    else:
        plan.status = ExecutionStatus.QUEUED
        plan.progress = 0.0
    return plan


def apply_crs_completion_law(plan: ExecutionPlan) -> None:
    """Child done + no CRS asset is not ready. Do not invent a new status enum."""

    if not is_crs_capability(plan.capability):
        return
    if plan.status != ExecutionStatus.COMPLETED:
        return
    if plan.result_asset_ids:
        plan.plan_data = {**dict(plan.plan_data or {}), "production_state": "completed"}
        return
    plan.status = ExecutionStatus.RUNNING
    plan.progress = min(float(plan.progress or 0.0), 0.99)
    plan.plan_data = {**dict(plan.plan_data or {}), "production_state": "running"}
    for child in plan.child_jobs:
        if child.status == ChildJobStatus.COMPLETED and not child.asset_id:
            child.status = ChildJobStatus.RUNNING
            child.stage = "finalizing"
