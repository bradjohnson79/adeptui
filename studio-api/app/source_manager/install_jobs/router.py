from __future__ import annotations

import asyncio
import json
import queue
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import events as install_events
from .requirements import resolve_requirements
from .service import (
    cancel,
    create_or_resume_install,
    download_queue,
    get_job,
    install_history,
    jobs_for_component,
    list_jobs,
    pause,
    repair,
    resume,
    retry,
)
from .sources import save_source, validate_source

router = APIRouter(tags=["install-jobs"])


class InstallBody(BaseModel):
    confirm: bool = True
    confirm_download_models: bool = Field(default=False, alias="confirmDownloadModels")
    install_path: str | None = Field(default=None, alias="installPath")
    source_url: str | None = Field(default=None, alias="sourceUrl")

    model_config = {"populate_by_name": True}


class RepairBody(BaseModel):
    action: str


class ValidateSourceBody(BaseModel):
    url: str
    revision: str | None = None


class SaveSourceBody(BaseModel):
    url: str | None = None
    revision: str | None = None
    confirm: bool = False
    verification: dict | None = None


def _bad_request(exc: Exception) -> None:
    raise HTTPException(400, str(exc)) from exc


@router.get("/setup/install-jobs")
def setup_install_jobs(active: bool | None = None, active_only: bool = False, componentId: str | None = None):
    jobs = list_jobs(active_only=bool(active if active is not None else active_only))
    if componentId:
        jobs = [job for job in jobs if job.get("componentId") == componentId]
    return {"jobs": jobs}


@router.get("/setup/install-jobs/events")
async def setup_install_job_events(request: Request, lastEventId: str | None = None):
    """SSE stream of install-job snapshots and patches."""

    after_id: int | None = None
    header_last = request.headers.get("last-event-id") or lastEventId
    if header_last:
        try:
            after_id = int(header_last)
        except ValueError:
            after_id = None

    outbound: queue.Queue[dict[str, Any] | None] = queue.Queue()

    def _on_event(event: dict[str, Any]) -> None:
        outbound.put(event)

    unsubscribe = install_events.subscribe(_on_event)

    async def event_stream():
        try:
            snapshot = {"type": "snapshot", "jobs": list_jobs(active_only=False)}
            yield f"event: snapshot\ndata: {json.dumps(snapshot, ensure_ascii=False)}\n\n"
            for event in install_events.recent_events(after_id=after_id):
                yield install_events.encode_sse(event)
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.to_thread(outbound.get, True, 15.0)
                except Exception:
                    yield "event: ping\ndata: {}\n\n"
                    continue
                if event is None:
                    break
                # Prefer fully serialized job shape for UI consumers.
                job_id = str((event.get("job") or {}).get("id") or "")
                if job_id:
                    try:
                        event = {
                            **event,
                            "job": get_job(job_id),
                        }
                    except KeyError:
                        pass
                yield install_events.encode_sse(event)
        finally:
            unsubscribe()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/setup/install-jobs/{job_id}")
def setup_install_job(job_id: str):
    try:
        return {"job": get_job(job_id)}
    except KeyError as exc:
        raise HTTPException(404, "Install job not found.") from exc


@router.get("/setup/components/{component_id}/install-job")
def setup_component_install_job(component_id: str):
    jobs = jobs_for_component(component_id)
    if not jobs:
        raise HTTPException(404, "No install job found for this component.")
    return {"job": jobs[0]}


@router.post("/setup/install-jobs")
def setup_install_jobs_create(body: dict):
    """Compatibility create used by studio-web `api.installJobs.create`."""
    component_id = str(body.get("componentId") or body.get("component_id") or "").strip()
    if not component_id:
        raise HTTPException(400, "componentId is required.")
    try:
        job = create_or_resume_install(
            component_id,
            confirm=bool(body.get("confirm", True)),
            confirm_download_models=bool(
                body.get("confirmDownloadModels")
                if body.get("confirmDownloadModels") is not None
                else body.get("confirm_download_models", False)
            ),
            source_url=body.get("sourceUrl") or body.get("source_url"),
            install_path=body.get("destinationRoot")
            or body.get("installPath")
            or body.get("install_path"),
        )
        return {"job": job, "created": True}
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        _bad_request(exc)


@router.post("/setup/components/{component_id}/install")
def setup_component_install(component_id: str, body: InstallBody | None = None):
    payload = body or InstallBody()
    try:
        job = create_or_resume_install(
            component_id,
            confirm=bool(payload.confirm),
            confirm_download_models=bool(payload.confirm_download_models),
            source_url=payload.source_url,
            install_path=payload.install_path,
        )
        return {"job": job, "created": True}
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        _bad_request(exc)


@router.post("/setup/install-jobs/{job_id}/pause")
def setup_install_job_pause(job_id: str):
    try:
        return {"job": pause(job_id)}
    except KeyError as exc:
        raise HTTPException(404, "Install job not found.") from exc
    except Exception as exc:  # noqa: BLE001
        _bad_request(exc)


@router.post("/setup/install-jobs/{job_id}/resume")
def setup_install_job_resume(job_id: str):
    try:
        return {"job": resume(job_id)}
    except KeyError as exc:
        raise HTTPException(404, "Install job not found.") from exc
    except Exception as exc:  # noqa: BLE001
        _bad_request(exc)


@router.post("/setup/install-jobs/{job_id}/cancel")
def setup_install_job_cancel(job_id: str):
    try:
        return {"job": cancel(job_id)}
    except KeyError as exc:
        raise HTTPException(404, "Install job not found.") from exc
    except Exception as exc:  # noqa: BLE001
        _bad_request(exc)


@router.post("/setup/install-jobs/{job_id}/retry")
def setup_install_job_retry(job_id: str):
    try:
        return {"job": retry(job_id)}
    except KeyError as exc:
        raise HTTPException(404, "Install job not found.") from exc
    except Exception as exc:  # noqa: BLE001
        _bad_request(exc)


@router.post("/setup/install-jobs/{job_id}/repair")
def setup_install_job_repair(job_id: str, body: RepairBody | None = None):
    action = (body.action if body else None) or "retry_download"
    try:
        return {"job": repair(job_id, action)}
    except KeyError as exc:
        raise HTTPException(404, "Install job not found.") from exc
    except Exception as exc:  # noqa: BLE001
        _bad_request(exc)


@router.post("/setup/install-jobs/{job_id}/verify")
def setup_install_job_verify(job_id: str):
    try:
        return {"job": repair(job_id, "reverify")}
    except KeyError as exc:
        raise HTTPException(404, "Install job not found.") from exc
    except Exception as exc:  # noqa: BLE001
        _bad_request(exc)


@router.get("/source-manager/components/{component_id}/requirements")
def source_manager_component_requirements(component_id: str):
    return resolve_requirements(component_id)


@router.get("/source-manager/capabilities/{capability_id}/required-components")
def source_manager_capability_requirements(capability_id: str):
    return resolve_requirements(capability_id)


@router.post("/source-manager/components/{component_id}/sources/validate")
def source_manager_validate_component_source(component_id: str, body: ValidateSourceBody):
    try:
        return validate_source(component_id, body.url, revision=body.revision)
    except Exception as exc:  # noqa: BLE001
        _bad_request(exc)


@router.post("/source-manager/components/{component_id}/sources")
def source_manager_save_component_source(component_id: str, body: SaveSourceBody):
    try:
        return save_source(
            component_id,
            verification=body.verification,
            url=body.url,
            revision=body.revision,
            confirm=bool(body.confirm),
        )
    except Exception as exc:  # noqa: BLE001
        _bad_request(exc)


@router.get("/source-manager/download-queue")
def source_manager_download_queue(active: bool | None = None, componentId: str | None = None):
    return download_queue(active_only=active, component_id=componentId)


@router.get("/source-manager/install-history")
def source_manager_install_history():
    return install_history()
