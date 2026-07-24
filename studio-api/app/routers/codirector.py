"""Provider-neutral Co-Director gateway endpoints (browser <-> Adept API only)."""

from __future__ import annotations

import json
import re
from typing import Any, Literal, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..codirector import config_store as codirector_config_store
from ..codirector import service as codirector_service
from ..codirector.errors import CoDirectorError, status_code_for_error
from ..db import SessionLocal, get_db

router = APIRouter(prefix="/codirector", tags=["codirector"])


def _http_error(err: CoDirectorError) -> HTTPException:
    return HTTPException(status_code=status_code_for_error(err.code), detail=err.to_dict())


class ChatMessageIn(BaseModel):
    role: str
    content: str


class CoDirectorChatBody(BaseModel):
    messages: list[ChatMessageIn]
    project_id: Optional[str] = None
    scene_id: Optional[str] = None
    model: Optional[str] = None
    provider_id: Optional[str] = None
    mode: Literal["chat", "prompt", "guide", "setup"] = "chat"
    request_id: Optional[str] = None


class CoDirectorCancelBody(BaseModel):
    request_id: str


class ConversationMessageIn(BaseModel):
    id: Optional[str] = None
    role: str
    content: str
    created_at: Optional[str] = None


class ConversationSaveBody(BaseModel):
    messages: list[ConversationMessageIn]
    model: Optional[str] = None
    provider_id: Optional[str] = None


class CoDirectorConfigBody(BaseModel):
    endpoint: Optional[str] = None
    selectedModel: Optional[str] = None
    timeoutSec: Optional[float] = None


_HOSTNAME_RE = re.compile(r"^[a-zA-Z0-9.-]+$")


def _validate_endpoint(endpoint: Optional[str]) -> None:
    if endpoint is None:
        return
    raw = endpoint.strip()
    parsed = urlparse(raw if "://" in raw else f"http://{raw}")
    hostname = parsed.hostname or ""
    if not hostname or not _HOSTNAME_RE.match(hostname):
        raise HTTPException(
            status_code=400,
            detail=CoDirectorError(
                "VALIDATION_ERROR",
                f"'{endpoint}' is not a valid host:port or URL.",
                details={"endpoint": endpoint},
                recoverable=True,
                recommended_action="none",
            ).to_dict(),
        )


@router.get("/config")
async def get_config() -> dict[str, Any]:
    return codirector_config_store.load_config()


@router.put("/config")
async def update_config(body: CoDirectorConfigBody) -> dict[str, Any]:
    _validate_endpoint(body.endpoint)
    if body.timeoutSec is not None and body.timeoutSec <= 0:
        raise HTTPException(
            status_code=400,
            detail=CoDirectorError(
                "VALIDATION_ERROR",
                "Timeout must be a positive number of seconds.",
                recoverable=True,
                recommended_action="none",
            ).to_dict(),
        )
    return codirector_config_store.save_config(body.model_dump(exclude_unset=True))


@router.get("/providers")
async def list_providers() -> dict[str, Any]:
    return {"providers": await codirector_service.list_providers_info()}


@router.get("/providers/{provider_id}/health")
async def provider_health(provider_id: str) -> dict[str, Any]:
    pid = None if provider_id == "active" else provider_id
    result = await codirector_service.get_health(pid)
    return result.to_dict()


@router.get("/providers/{provider_id}/models")
async def provider_models(provider_id: str) -> dict[str, Any]:
    pid = None if provider_id == "active" else provider_id
    try:
        models = await codirector_service.list_models(pid)
    except CoDirectorError as err:
        raise _http_error(err) from err
    return {"models": [m.to_dict() for m in models]}


@router.post("/chat")
async def chat(body: CoDirectorChatBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        result, scene_setup, suggested = await codirector_service.chat_for_project(
            db,
            messages=[m.model_dump() for m in body.messages],
            project_id=body.project_id,
            scene_id=body.scene_id,
            mode=body.mode,
            model=body.model,
            provider_id=body.provider_id,
            request_id=body.request_id,
        )
    except CoDirectorError as err:
        raise _http_error(err) from err
    return {
        "requestId": result.request_id,
        "reply": result.reply,
        "model": result.model_id,
        "providerId": result.provider_id,
        "suggestedPrompt": suggested,
        "sceneSetup": scene_setup.model_dump() if scene_setup else None,
    }


@router.post("/chat/stream")
async def chat_stream(body: CoDirectorChatBody) -> StreamingResponse:
    request_id = body.request_id or codirector_service.new_request_id()
    messages = [m.model_dump() for m in body.messages]

    async def event_source():
        # A `Depends(get_db)` session would be torn down by FastAPI's exit stack as soon as
        # this endpoint returns the StreamingResponse — before the body generator below is
        # ever iterated. Own the session's lifecycle for the duration of the stream instead.
        db = SessionLocal()
        try:
            async for event in codirector_service.stream_for_project(
                db,
                messages=messages,
                project_id=body.project_id,
                scene_id=body.scene_id,
                mode=body.mode,
                model=body.model,
                provider_id=body.provider_id,
                request_id=request_id,
            ):
                yield f"data: {json.dumps(event)}\n\n"
                if codirector_service.is_cancelled(request_id):
                    yield f"data: {json.dumps({'type': 'cancelled', 'requestId': request_id})}\n\n"
                    break
        except CoDirectorError as err:
            yield f"data: {json.dumps({'type': 'error', 'requestId': request_id, 'error': err.to_dict()})}\n\n"
        finally:
            codirector_service.clear_cancelled(request_id)
            db.close()

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Request-Id": request_id},
    )


@router.post("/cancel")
async def cancel(body: CoDirectorCancelBody) -> dict[str, Any]:
    return codirector_service.request_cancel(body.request_id)


@router.get("/conversations/{project_id}")
async def get_conversation(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    convo = codirector_service.get_conversation(db, project_id)
    if convo:
        return convo
    return {"projectId": project_id, "messages": [], "model": None, "providerId": None, "updatedAt": None}


@router.post("/conversations/{project_id}")
async def save_conversation(
    project_id: str, body: ConversationSaveBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    return codirector_service.save_conversation(
        db,
        project_id,
        messages=[m.model_dump() for m in body.messages],
        model=body.model,
        provider_id=body.provider_id,
    )


@router.delete("/conversations/{project_id}")
async def delete_conversation(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    ok = codirector_service.delete_conversation(db, project_id)
    return {"ok": ok, "projectId": project_id}
