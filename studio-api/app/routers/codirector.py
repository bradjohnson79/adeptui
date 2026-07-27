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
from ..codirector.bible import service as bible_service
from ..codirector.bible.api_domain import router as bible_domain_router
from ..codirector.bible.proposals import ProposalService
from ..codirector.vision.api import router as vision_router
from ..codirector.executive.api import router as executive_router
from ..codirector.m28.api import router as m28_router
from ..codirector.m29.api import router as m29_router
from ..codirector.m211.api import router as m211_router
from ..codirector.m212.api import router as m212_router
from ..codirector.m213.api import router as m213_router
from ..codirector.m214.api import router as m214_router
from ..codirector.model_intelligence.api import router as model_intelligence_router
from ..codirector.language_intelligence.api import router as language_intelligence_router
from ..codirector.bible.schemas import (
    ApprovalDecisionRequest,
    BibleMutationSet,
    CreateVersionRequest,
    ImportConfirmRequest,
    ImportPreviewRequest,
)
from ..codirector.errors import CoDirectorError, status_code_for_error
from ..codirector.tools import registry as tool_registry
from ..codirector.tools.definitions import TOOL_SCHEMA_VERSION, ToolProposalRequest, ToolReadRequest
from ..codirector.tools.execution import ToolExecutionService
from ..db import SessionLocal, get_db

router = APIRouter(prefix="/codirector", tags=["codirector"])
router.include_router(bible_domain_router)
router.include_router(vision_router)
router.include_router(executive_router)
router.include_router(m28_router)
router.include_router(m29_router)
router.include_router(m211_router)
router.include_router(m212_router)
router.include_router(m213_router)
router.include_router(m214_router)
router.include_router(model_intelligence_router)
router.include_router(language_intelligence_router)


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
    conversation_locale: Optional[str] = None
    conversationLocale: Optional[str] = None


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
        (
            result,
            scene_setup,
            suggested,
            proposal,
            manifest,
            invocations,
        ) = await codirector_service.chat_for_project(
            db,
            messages=[m.model_dump() for m in body.messages],
            project_id=body.project_id,
            scene_id=body.scene_id,
            mode=body.mode,
            model=body.model,
            provider_id=body.provider_id,
            request_id=body.request_id,
            conversation_locale=body.conversation_locale or body.conversationLocale,
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
        "proposal": proposal.model_dump(mode="json") if proposal else None,
        "contextManifest": manifest.model_dump(mode="json") if manifest.bibleVersionId else None,
        "toolInvocations": [i.model_dump(mode="json") for i in invocations],
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
                conversation_locale=body.conversation_locale or body.conversationLocale,
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


# --------------------------------------------------------------------------
# M2.1: Production Bible (project-scoped, versioned). `project_id` in the path always wins
# over any project id embedded in a request body.
# --------------------------------------------------------------------------


@router.get("/projects/{project_id}/bible")
async def get_bible(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    out = bible_service.get_bible_out(db, project_id)
    if out is None:
        raise HTTPException(
            status_code=404,
            detail=CoDirectorError(
                "BIBLE_NOT_FOUND",
                "This project doesn't have a Production Bible yet. Create one first.",
                details={"projectId": project_id},
                recoverable=True,
                recommended_action="create_bible",
            ).to_dict(),
        )
    return out.model_dump(mode="json")


@router.get("/projects/{project_id}/bible/versions")
async def list_bible_versions(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        versions = bible_service.list_versions_out(db, project_id)
    except CoDirectorError as err:
        raise _http_error(err) from err
    return {"projectId": project_id, "versions": [v.model_dump(mode="json") for v in versions]}


@router.get("/projects/{project_id}/bible/versions/{version_number}")
async def get_bible_version(project_id: str, version_number: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        version = bible_service.get_version_out(db, project_id, version_number)
    except CoDirectorError as err:
        raise _http_error(err) from err
    return version.model_dump(mode="json")


@router.post("/projects/{project_id}/bible/import/preview")
async def bible_import_preview(
    project_id: str, body: ImportPreviewRequest = ImportPreviewRequest(), db: Session = Depends(get_db)
) -> dict[str, Any]:
    try:
        preview = bible_service.build_import_preview(
            db, project_id, include_scenes=body.includeScenes, include_assets_as_props=body.includeAssetsAsProps
        )
    except CoDirectorError as err:
        raise _http_error(err) from err
    return preview.model_dump(mode="json")


@router.post("/projects/{project_id}/bible/import/confirm")
async def bible_import_confirm(project_id: str, body: ImportConfirmRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        out = bible_service.confirm_import(
            db,
            project_id,
            entities=body.entities,
            facts=body.facts,
            summary=body.summary,
            change_reason=body.changeReason,
        )
    except CoDirectorError as err:
        raise _http_error(err) from err
    return out.model_dump(mode="json")


@router.post("/projects/{project_id}/bible/versions")
async def create_bible_version(project_id: str, body: CreateVersionRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        version = bible_service.create_new_version(db, project_id, body.mutations, created_by=body.createdBy)
    except CoDirectorError as err:
        raise _http_error(err) from err
    return version.model_dump(mode="json")


# --------------------------------------------------------------------------
# M2.1: Durable proposals + approvals + execution receipts.
# --------------------------------------------------------------------------


class CreateProposalBody(BaseModel):
    proposal_type: str = "entity_update"
    title: str
    summary: str = ""
    payload: BibleMutationSet
    request_id: Optional[str] = None
    created_by: str = "user"


@router.get("/projects/{project_id}/proposals")
async def list_proposals(project_id: str, status: Optional[str] = None, db: Session = Depends(get_db)) -> dict[str, Any]:
    proposals = ProposalService.list(db, project_id, status=status)
    return {"projectId": project_id, "proposals": [p.model_dump(mode="json") for p in proposals]}


@router.post("/projects/{project_id}/proposals")
async def create_proposal(project_id: str, body: CreateProposalBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Manual/testing entry point. The normal path is the model emitting a ```proposal fence
    during chat, handled inside `codirector_service.stream_for_project` / `chat_for_project`."""
    proposal = ProposalService.create_proposal(
        db,
        project_id=project_id,
        proposal_type=body.proposal_type,
        title=body.title,
        summary=body.summary,
        payload=body.payload,
        request_id=body.request_id,
        created_by=body.created_by,
    )
    return proposal.model_dump(mode="json")


@router.get("/projects/{project_id}/proposals/{proposal_id}")
async def get_proposal(project_id: str, proposal_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        proposal = ProposalService.get(db, project_id, proposal_id)
    except CoDirectorError as err:
        raise _http_error(err) from err
    return proposal.model_dump(mode="json")


@router.get("/projects/{project_id}/proposals/{proposal_id}/preview")
async def preview_proposal(project_id: str, proposal_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return ProposalService.preview(db, project_id, proposal_id)
    except CoDirectorError as err:
        raise _http_error(err) from err


@router.post("/projects/{project_id}/proposals/{proposal_id}/approve")
async def approve_proposal(
    project_id: str, proposal_id: str, body: ApprovalDecisionRequest = ApprovalDecisionRequest(), db: Session = Depends(get_db)
) -> dict[str, Any]:
    try:
        receipt = ProposalService.approve(db, project_id, proposal_id, note=body.note, decided_by=body.decidedBy)
    except CoDirectorError as err:
        raise _http_error(err) from err
    return receipt.model_dump(mode="json")


@router.post("/projects/{project_id}/proposals/{proposal_id}/reject")
async def reject_proposal(
    project_id: str, proposal_id: str, body: ApprovalDecisionRequest = ApprovalDecisionRequest(), db: Session = Depends(get_db)
) -> dict[str, Any]:
    try:
        proposal = ProposalService.reject(db, project_id, proposal_id, note=body.note, decided_by=body.decidedBy)
    except CoDirectorError as err:
        raise _http_error(err) from err
    return proposal.model_dump(mode="json")


@router.post("/projects/{project_id}/proposals/{proposal_id}/request-revision")
async def request_revision_proposal(
    project_id: str, proposal_id: str, body: ApprovalDecisionRequest = ApprovalDecisionRequest(), db: Session = Depends(get_db)
) -> dict[str, Any]:
    try:
        proposal = ProposalService.request_revision(db, project_id, proposal_id, note=body.note, decided_by=body.decidedBy)
    except CoDirectorError as err:
        raise _http_error(err) from err
    return proposal.model_dump(mode="json")


@router.post("/projects/{project_id}/proposals/{proposal_id}/cancel")
async def cancel_proposal(
    project_id: str, proposal_id: str, body: ApprovalDecisionRequest = ApprovalDecisionRequest(), db: Session = Depends(get_db)
) -> dict[str, Any]:
    try:
        proposal = ProposalService.cancel(db, project_id, proposal_id, note=body.note, decided_by=body.decidedBy)
    except CoDirectorError as err:
        raise _http_error(err) from err
    return proposal.model_dump(mode="json")


@router.get("/projects/{project_id}/proposals/{proposal_id}/receipt")
async def get_proposal_receipt(project_id: str, proposal_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        receipt = ProposalService.get_receipt(db, project_id, proposal_id)
    except CoDirectorError as err:
        raise _http_error(err) from err
    return receipt.model_dump(mode="json")


# --------------------------------------------------------------------------
# M2.2: bounded tool registry. Read tools execute here; mutating tools only ever produce a
# proposal, and are approved/rejected through the proposal endpoints above — there is
# deliberately no "execute tool" endpoint.
# --------------------------------------------------------------------------


@router.get("/tools")
async def list_tools() -> dict[str, Any]:
    """The tool catalog, independent of any project. No capability probes run here."""

    return {"toolSchemaVersion": TOOL_SCHEMA_VERSION, "tools": tool_registry.catalog()}


@router.get("/projects/{project_id}/tools")
async def list_project_tools(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        availability, capabilities = await ToolExecutionService.availability(db, project_id)
    except CoDirectorError as err:
        raise _http_error(err) from err
    return {
        "projectId": project_id,
        "toolSchemaVersion": TOOL_SCHEMA_VERSION,
        "tools": tool_registry.catalog(),
        "availability": [a.model_dump(mode="json") for a in availability],
        "capabilities": capabilities,
    }


@router.get("/projects/{project_id}/tools/availability")
async def get_tool_availability(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        availability, capabilities = await ToolExecutionService.availability(db, project_id)
    except CoDirectorError as err:
        raise _http_error(err) from err
    return {
        "projectId": project_id,
        "availability": [a.model_dump(mode="json") for a in availability],
        "capabilities": capabilities,
    }


@router.post("/projects/{project_id}/tools/read")
async def run_read_tool(project_id: str, body: ToolReadRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Run a read tool now. Rejects mutating tools with `TOOL_KIND_MISMATCH`."""

    try:
        invocation = await ToolExecutionService.execute_read(
            db,
            project_id=project_id,
            tool_id=body.toolId,
            arguments=body.arguments,
            scene_id=body.sceneId,
            request_id=body.requestId,
            created_by="user",
        )
    except CoDirectorError as err:
        raise _http_error(err) from err
    return invocation.model_dump(mode="json")


@router.post("/projects/{project_id}/tools/proposals")
async def propose_tool_call(project_id: str, body: ToolProposalRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Create a `tool_call` proposal for a mutating tool. Nothing is applied until approval."""

    try:
        proposal = await ToolExecutionService.propose(
            db,
            project_id=project_id,
            tool_id=body.toolId,
            arguments=body.arguments,
            scene_id=body.sceneId,
            request_id=body.requestId,
            created_by=body.createdBy,
        )
    except CoDirectorError as err:
        raise _http_error(err) from err
    return proposal.model_dump(mode="json")


@router.get("/projects/{project_id}/tool-invocations")
async def list_tool_invocations(
    project_id: str, tool_id: Optional[str] = None, limit: int = 50, db: Session = Depends(get_db)
) -> dict[str, Any]:
    invocations = ToolExecutionService.list_invocations(db, project_id, tool_id=tool_id, limit=limit)
    return {"projectId": project_id, "invocations": [i.model_dump(mode="json") for i in invocations]}
