"""Capability, workflow, and ComfyUI readiness endpoints.

These four capability routes are the contract other consumers read: the Health Dashboard,
the Setup Wizard, the Source Manager blocker actions, and (later) Co-Director M2.2's
capability adapter. They are read-only apart from `refresh`, which only drops the probe
cache — it never installs, downloads, or mutates project state.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from . import errors, service
from .models import CapabilityOut, CapabilitySnapshotOut

router = APIRouter(tags=["capabilities"])


def _http_error(err: errors.CapabilityError) -> HTTPException:
    return HTTPException(
        status_code=errors.status_code_for_error(err.code),
        detail=err.to_dict(),
    )


@router.get("/capabilities", response_model=CapabilitySnapshotOut)
async def get_capabilities(
    project_id: str | None = Query(default=None, alias="projectId"),
    refresh: bool = Query(default=False),
) -> CapabilitySnapshotOut:
    return await service.get_capabilities(project_id=project_id, force=refresh)


@router.get("/capabilities/{capability_id}", response_model=CapabilityOut)
async def get_capability(
    capability_id: str,
    project_id: str | None = Query(default=None, alias="projectId"),
) -> CapabilityOut:
    try:
        return await service.get_capability(capability_id, project_id=project_id)
    except errors.CapabilityError as err:
        raise _http_error(err) from err


@router.post("/capabilities/refresh", response_model=CapabilitySnapshotOut)
async def refresh_capabilities(
    project_id: str | None = Query(default=None, alias="projectId"),
) -> CapabilitySnapshotOut:
    """Re-probe the environment. Read-only: no install, download, or project mutation."""
    return await service.get_capabilities(project_id=project_id, force=True)


@router.get("/projects/{project_id}/capabilities", response_model=CapabilitySnapshotOut)
async def get_project_capabilities(
    project_id: str,
    refresh: bool = Query(default=False),
) -> CapabilitySnapshotOut:
    return await service.get_capabilities(project_id=project_id, force=refresh)


@router.get("/comfy/health")
async def get_comfy_health() -> dict[str, Any]:
    from ..comfy_health import comfy_health

    return await comfy_health()


@router.get("/workflows")
async def get_workflows() -> dict[str, Any]:
    from ..workflows.readiness import list_workflows

    return {"workflows": list_workflows()}


@router.get("/workflows/{workflow_id}/readiness")
async def get_workflow_readiness(workflow_id: str) -> dict[str, Any]:
    from ..comfy_health import node_types
    from ..workflows.readiness import workflow_readiness

    try:
        return workflow_readiness(workflow_id, node_types=await node_types())
    except KeyError as exc:
        raise _http_error(
            errors.CapabilityError(
                code=errors.WORKFLOW_NOT_FOUND,
                message=f"Unknown workflow '{workflow_id}'.",
                details={"workflowId": workflow_id},
                recoverable=False,
                recommended_action="list_workflows",
            )
        ) from exc
