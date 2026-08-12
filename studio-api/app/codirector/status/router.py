from __future__ import annotations

import asyncio
import queue

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ...db import get_db
from .registry import StatusContext
from .runner import encode_sse, recent_events, registry_payload, run_status_check, subscribe_events, unsubscribe_events
from .store import latest_run, list_runs
from .types import DeepDiagnosticRequest, StatusCheckRequest

router = APIRouter(prefix="/status", tags=["codirector-status"])


@router.get("/registry")
async def get_registry() -> dict:
    return registry_payload()


@router.post("/check")
async def post_check(body: StatusCheckRequest, db: Session = Depends(get_db)) -> dict:
    ctx = StatusContext(db=db, project_id=body.projectId, scene_id=body.sceneId, workspace=body.workspace, mode="standard")
    run = await run_status_check(ctx, body, mode="standard")
    return run.model_dump(mode="json")


@router.post("/check/{check_id}")
async def post_check_one(check_id: str, body: StatusCheckRequest, db: Session = Depends(get_db)) -> dict:
    body.checkIds = [check_id]
    ctx = StatusContext(db=db, project_id=body.projectId, scene_id=body.sceneId, workspace=body.workspace, mode="standard")
    run = await run_status_check(ctx, body, mode="standard")
    return run.model_dump(mode="json")


@router.post("/deep-diagnostic")
async def post_deep_diagnostic(body: DeepDiagnosticRequest, db: Session = Depends(get_db)) -> dict:
    if not body.confirm:
        raise HTTPException(status_code=400, detail={"code": "CONFIRM_REQUIRED", "message": "Deep Diagnostic requires explicit confirmation."})
    ctx = StatusContext(db=db, project_id=body.projectId, scene_id=body.sceneId, workspace=body.workspace, mode="deep")
    run = await run_status_check(ctx, body, mode="deep")
    return run.model_dump(mode="json")


@router.get("/latest")
async def get_latest(
    project_id: str | None = Query(default=None, alias="projectId"),
    scene_id: str | None = Query(default=None, alias="sceneId"),
) -> dict:
    run = latest_run(project_id=project_id, scene_id=scene_id)
    return {"run": None if run is None else run.model_dump(mode="json")}


@router.get("/history")
async def get_history(
    project_id: str | None = Query(default=None, alias="projectId"),
    scene_id: str | None = Query(default=None, alias="sceneId"),
    limit: int = Query(default=20, ge=1, le=20),
) -> dict:
    rows = list_runs(project_id=project_id, scene_id=scene_id, limit=limit)
    return {"runs": [row.model_dump(mode="json") for row in rows]}


@router.get("/events")
async def get_events(request: Request, lastEventId: str | None = None):
    after_id = None
    raw_last = request.headers.get("last-event-id") or lastEventId
    if raw_last:
        try:
            after_id = int(raw_last)
        except ValueError:
            after_id = None

    outbound = subscribe_events()

    async def event_stream():
        try:
            yield encode_sse({"type": "snapshot", "events": recent_events(after_id=after_id)})
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.to_thread(outbound.get, True, 15.0)
                except queue.Empty:
                    yield "event: ping\ndata: {}\n\n"
                    continue
                if event is None:
                    break
                yield encode_sse(event)
        finally:
            unsubscribe_events(outbound)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
