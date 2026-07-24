"""Download queue + install history HTTP API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .models import create_install_plan
from .queue import get_queue_manager
from .receipts import get_receipt, history_entries, verify_receipt
from .persistence import list_receipts

router = APIRouter(tags=["downloads"])


def _error(status: int, code: str, message: str, *, details: dict | None = None, recoverable: bool = True, action: str | None = None):
    raise HTTPException(
        status_code=status,
        detail={
            "code": code,
            "message": message,
            "details": details or {},
            "recoverable": recoverable,
            "recommendedAction": action,
        },
    )


@router.get("/downloads")
def list_downloads(active: bool | None = None, componentId: str | None = None):
    filters: dict = {}
    if active:
        filters["active"] = True
    if componentId:
        filters["componentId"] = componentId
    return {"operations": get_queue_manager().list(filters or None)}


@router.post("/downloads")
def enqueue_download(body: dict):
    """
    Body: { plan?: InstallPlan, componentId, providerId, destinationRoot, artifacts?, sourceId?, priority? }
    """
    plan = body.get("plan")
    if not isinstance(plan, dict):
        component_id = str(body.get("componentId") or body.get("component_id") or "").strip()
        destination = str(body.get("destinationRoot") or body.get("destination_root") or "").strip()
        if not component_id or not destination:
            _error(400, "INVALID_PLAN", "componentId and destinationRoot are required.")
        provider_id = str(body.get("providerId") or body.get("provider_id") or "fixture")
        artifacts = body.get("artifacts") or [{"remotePath": "pack.zip", "destinationRelativePath": "pack.json"}]
        plan = create_install_plan(
            component_id=component_id,
            source_id=body.get("sourceId") or body.get("source_id"),
            provider_id=provider_id,
            artifacts=list(artifacts),
            destination_root=destination,
            source_fingerprint=body.get("sourceFingerprint"),
            source_revision=body.get("sourceRevision"),
            estimated_download_bytes=body.get("estimatedDownloadBytes"),
            estimated_extracted_bytes=body.get("estimatedExtractedBytes"),
            metadata=body.get("metadata") or {},
        )
    priority = int(body.get("priority") or 100)
    try:
        op = get_queue_manager().enqueue(plan, priority=priority)
    except ValueError as exc:
        _error(400, "ENQUEUE_FAILED", str(exc))
    return {"operation": op}


@router.get("/downloads/{operation_id}")
def get_download(operation_id: str):
    op = get_queue_manager().get(operation_id)
    if not op:
        _error(404, "NOT_FOUND", "Download operation not found.")
    return {"operation": op}


@router.post("/downloads/{operation_id}/cancel")
def cancel_download(operation_id: str):
    try:
        return {"operation": get_queue_manager().cancel(operation_id)}
    except KeyError:
        _error(404, "NOT_FOUND", "Download operation not found.")


@router.post("/downloads/{operation_id}/pause")
def pause_download(operation_id: str):
    try:
        return {"operation": get_queue_manager().pause(operation_id)}
    except KeyError:
        _error(404, "NOT_FOUND", "Download operation not found.")
    except ValueError as exc:
        _error(400, "PAUSE_UNSUPPORTED", str(exc), action="cancel")


@router.post("/downloads/{operation_id}/resume")
def resume_download(operation_id: str):
    try:
        return {"operation": get_queue_manager().resume(operation_id)}
    except KeyError:
        _error(404, "NOT_FOUND", "Download operation not found.")
    except ValueError as exc:
        _error(400, "RESUME_FAILED", str(exc), action="retry")


@router.post("/downloads/{operation_id}/retry")
def retry_download(operation_id: str):
    try:
        return {"operation": get_queue_manager().retry(operation_id)}
    except KeyError:
        _error(404, "NOT_FOUND", "Download operation not found.")
    except ValueError as exc:
        _error(400, "RETRY_FAILED", str(exc))


@router.post("/downloads/{operation_id}/priority")
def priority_download(operation_id: str, body: dict):
    try:
        priority = int(body.get("priority"))
    except (TypeError, ValueError):
        _error(400, "INVALID_PRIORITY", "priority must be an integer.")
    try:
        return {"operation": get_queue_manager().reprioritize(operation_id, priority)}
    except KeyError:
        _error(404, "NOT_FOUND", "Download operation not found.")
    except ValueError as exc:
        _error(400, "PRIORITY_FAILED", str(exc))


@router.post("/downloads/{operation_id}/cleanup")
def cleanup_download(operation_id: str):
    try:
        return {"operation": get_queue_manager().cleanup(operation_id)}
    except KeyError:
        _error(404, "NOT_FOUND", "Download operation not found.")


@router.get("/install-history")
def install_history():
    return {"entries": history_entries(), "count": len(list_receipts())}


@router.get("/install-history/{install_id}")
def install_history_item(install_id: str):
    receipt = get_receipt(install_id)
    if not receipt:
        _error(404, "NOT_FOUND", "Install receipt not found.")
    return {"receipt": receipt}


@router.post("/install-history/{install_id}/verify")
def install_history_verify(install_id: str):
    try:
        return verify_receipt(install_id)
    except KeyError:
        _error(404, "NOT_FOUND", "Install receipt not found.")
