"""HTTP API for M42 W47 Docker Runtime Manager."""

from __future__ import annotations

from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import service
from .gate import evaluate_gate
from .manager import get_manager
from .platform import detect_platform

router = APIRouter(prefix="/docker-runtime", tags=["docker-runtime-w47"])


class ManifestBody(BaseModel):
    manifest: dict[str, Any] = Field(default_factory=dict)
    image: Optional[str] = None
    name: Optional[str] = None
    runtimeId: Optional[str] = None
    modality: Optional[str] = None
    runTest: bool = True


class UninstallBody(BaseModel):
    option: Literal["ui_only", "container", "container_and_image", "container_image_and_private"] = (
        "container_image_and_private"
    )
    forceFailStep: Optional[str] = None


class UpdateBody(BaseModel):
    image: str


class WorkflowBody(BaseModel):
    workflow: dict[str, Any] = Field(default_factory=dict)


@router.get("/platform")
def platform() -> dict[str, Any]:
    return {"ok": True, "platform": detect_platform()}


@router.get("/runtimes")
def runtimes() -> dict[str, Any]:
    return {"ok": True, "runtimes": service.list_runtimes()}


@router.get("/runtimes/{runtime_id}")
def runtime_get(runtime_id: str) -> dict[str, Any]:
    return get_manager().inspect(runtime_id)


@router.post("/install/preview")
def install_preview(body: ManifestBody) -> dict[str, Any]:
    raw = body.manifest or {}
    if body.image:
        raw = {**raw, "image": body.image, "name": body.name, "runtimeId": body.runtimeId, "modality": body.modality}
    plan = service.preview_install(raw)
    return {"ok": plan.security.ok and plan.validation.ok, "plan": plan.model_dump(mode="json")}


@router.post("/install")
def install(body: ManifestBody) -> dict[str, Any]:
    raw = body.manifest or {}
    if body.image:
        raw = {**raw, "image": body.image, "name": body.name, "runtimeId": body.runtimeId, "modality": body.modality}
    result = service.install_runtime(raw, run_test=body.runTest)
    if not result.ok:
        raise HTTPException(400, detail={"code": "INSTALL_FAILED", "message": result.error or "install_failed"})
    return {"ok": True, "result": result.model_dump(mode="json")}


@router.post("/runtimes/{runtime_id}/start")
def start(runtime_id: str) -> dict[str, Any]:
    return get_manager().start(runtime_id)


@router.post("/runtimes/{runtime_id}/stop")
def stop(runtime_id: str) -> dict[str, Any]:
    return get_manager().stop(runtime_id)


@router.post("/runtimes/{runtime_id}/restart")
def restart(runtime_id: str) -> dict[str, Any]:
    return get_manager().restart(runtime_id)


@router.post("/runtimes/{runtime_id}/test")
def test_runtime(runtime_id: str) -> dict[str, Any]:
    from .gpu_preflight import check_gpu
    from .health import check_health

    start = get_manager().start(runtime_id)
    health = check_health(runtime_id)
    gpu = check_gpu(runtime_id)
    return {
        "ok": bool(start.get("ok") and health.ok and (gpu.frameworkAccelerator or detect_platform().get("simulate"))),
        "start": start,
        "health": health.model_dump(mode="json"),
        "gpu": gpu.model_dump(mode="json"),
    }


@router.get("/runtimes/{runtime_id}/logs")
def logs(runtime_id: str, tail: int = 200) -> dict[str, Any]:
    return get_manager().logs(runtime_id, tail=tail)


@router.get("/runtimes/{runtime_id}/diagnostics")
def diagnostics(runtime_id: str) -> dict[str, Any]:
    return {"ok": True, "report": service.diagnostics(runtime_id).model_dump(mode="json")}


@router.post("/runtimes/{runtime_id}/disable")
def disable(runtime_id: str) -> dict[str, Any]:
    from .registry import get_runtime, upsert_runtime

    desc = get_runtime(runtime_id)
    if not desc:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "runtime_not_found"})
    if desc.classification == "core_mandatory":
        raise HTTPException(400, detail={"code": "CORE_PROTECTED", "message": "core_cannot_disable"})
    get_manager().stop(runtime_id)
    desc.disabled = True
    desc.readiness = "disabled"
    upsert_runtime(desc)
    return {"ok": True, "runtime": desc.model_dump(mode="json")}


@router.post("/runtimes/{runtime_id}/enable")
def enable(runtime_id: str) -> dict[str, Any]:
    from .registry import get_runtime, upsert_runtime

    desc = get_runtime(runtime_id)
    if not desc:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "runtime_not_found"})
    desc.disabled = False
    upsert_runtime(desc)
    start = get_manager().start(runtime_id)
    repaired = service.repair_runtime(runtime_id)
    return {"ok": bool(start.get("ok") and repaired.get("ok")), "start": start, "repair": repaired}


@router.post("/runtimes/{runtime_id}/repair")
def repair(runtime_id: str) -> dict[str, Any]:
    return service.repair_runtime(runtime_id)


@router.post("/runtimes/{runtime_id}/update")
def update(runtime_id: str, body: UpdateBody) -> dict[str, Any]:
    return service.update_runtime(runtime_id, body.image)


@router.post("/runtimes/{runtime_id}/rollback")
def rollback(runtime_id: str) -> dict[str, Any]:
    return service.rollback_runtime(runtime_id)


@router.post("/runtimes/{runtime_id}/uninstall/preview")
def uninstall_preview(runtime_id: str, body: UninstallBody) -> dict[str, Any]:
    plan = service.preview_uninstall(runtime_id, body.option)
    return {"ok": plan.blockedReason is None, "plan": plan.model_dump(mode="json")}


@router.post("/runtimes/{runtime_id}/uninstall")
def uninstall(runtime_id: str, body: UninstallBody) -> dict[str, Any]:
    result = service.uninstall_runtime(runtime_id, body.option, force_fail_step=body.forceFailStep)
    if not result.ok:
        raise HTTPException(
            400,
            detail={"code": "UNINSTALL_FAILED", "message": result.error, "rolledBack": result.rolledBack},
        )
    return {"ok": True, "result": result.model_dump(mode="json")}


@router.post("/workflow/inspect")
def workflow_inspect(body: WorkflowBody) -> dict[str, Any]:
    return service.import_comfy_workflow(body.workflow)


@router.get("/dock-models")
def dock_models() -> dict[str, Any]:
    """Docker + native runtime entries for Production Dock classification."""
    items = []
    for r in service.list_runtimes():
        if r.get("disabled"):
            readiness = "Disabled"
            executable = False
        elif r.get("readiness") == "ready":
            readiness = "Ready"
            executable = True
        elif r.get("readiness") == "tested_locally":
            readiness = "Tested Locally"
            executable = True
        elif r.get("readiness") == "requires_repair":
            readiness = "Requires Repair"
            executable = False
        elif r.get("lifecycle") == "stopped":
            readiness = "Container Stopped"
            executable = False
        else:
            readiness = str(r.get("readiness") or "Unverified")
            executable = False
        items.append(
            {
                "id": f"docker-runtime:{r['id']}" if r.get("executionClass") == "docker_local" else r["id"],
                "runtimeId": r["id"],
                "label": r["name"],
                "modality": r.get("modality") or "video",
                "executionClass": r.get("executionClass") or "native_local",
                "classification": r.get("classification"),
                "readiness": readiness,
                "executable": executable and not r.get("disabled"),
                "gpuReady": r.get("gpuReady"),
                "uninstallAllowed": r.get("uninstallAllowed"),
                "locality": "hosted" if r.get("executionClass") == "hosted_api" else "local",
            }
        )
    return {"ok": True, "models": items}


@router.get("/gate")
def gate() -> dict[str, Any]:
    return evaluate_gate()
