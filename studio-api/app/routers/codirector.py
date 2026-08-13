"""Provider-neutral Co-Director gateway endpoints (browser <-> Adept API only)."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Literal, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from ..codirector import config_store as codirector_config_store
from ..codirector import service as codirector_service
from ..codirector.bible import service as bible_service
from ..codirector.bible.api_domain import router as bible_domain_router
from ..codirector.bible.proposals import ProposalService
from ..codirector.plans.service import PlanService
from ..codirector.vision.api import router as vision_router
from ..codirector.executive.api import router as executive_router
from ..codirector.execution.api import router as execution_router
from ..codirector.m28.api import router as m28_router
from ..codirector.m29.api import router as m29_router
from ..codirector.m211.api import router as m211_router
from ..codirector.m212.api import router as m212_router
from ..codirector.m213.api import router as m213_router
from ..codirector.m214.api import router as m214_router
from ..codirector.model_intelligence.api import router as model_intelligence_router
from ..codirector.language_intelligence.api import router as language_intelligence_router
from ..codirector.prompt_intelligence.api import router as prompt_intelligence_router
from ..codirector.prompt_intelligence.benchmark_api import router as prompt_intelligence_v2_router
from ..codirector.status.router import router as status_router
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
router.include_router(execution_router)
router.include_router(m28_router)
router.include_router(m29_router)
router.include_router(m211_router)
router.include_router(m212_router)
router.include_router(m213_router)
router.include_router(m214_router)
router.include_router(model_intelligence_router)
router.include_router(language_intelligence_router)
router.include_router(prompt_intelligence_router)
router.include_router(prompt_intelligence_v2_router)
router.include_router(status_router)


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
    origin_session_id: Optional[str] = Field(default=None, alias="originSessionId")
    attachment_ids: list[str] = Field(default_factory=list)
    attachmentIds: list[str] = Field(default_factory=list)
    active_content_tab: Optional[str] = None
    activeContentTab: Optional[str] = None


class CoDirectorCancelBody(BaseModel):
    request_id: str


class ConversationMessageIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = None
    role: str
    content: str
    created_at: Optional[str] = None
    attachment_ids: list[str] = Field(default_factory=list, alias="attachmentIds")
    attachments: list["ConversationAttachmentIn"] = Field(default_factory=list)


class ConversationAttachmentIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    asset_id: str = Field(alias="assetId")
    name: str
    mime_type: Optional[str] = Field(default=None, alias="mimeType")
    source: Optional[str] = None
    kind: Optional[str] = None


class ConversationSaveBody(BaseModel):
    messages: list[ConversationMessageIn]
    model: Optional[str] = None
    provider_id: Optional[str] = None
    expected_revision: Optional[int] = None
    allow_admin_replace: bool = False


class ConversationEventIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    role: str
    content: str = ""
    event_type: str = "message"
    message_id: Optional[str] = None
    client_request_id: Optional[str] = None
    message_type: Optional[str] = None
    status: Optional[str] = None
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    tool_id: Optional[str] = None
    tool_arguments: Optional[dict[str, Any]] = None
    tool_result: Optional[dict[str, Any]] = None
    request_id: Optional[str] = None
    actor: str = "user"
    created_at: Optional[str] = None


class ConversationEventsBody(BaseModel):
    events: list[ConversationEventIn]
    expected_revision: Optional[int] = None
    model: Optional[str] = None
    provider_id: Optional[str] = None


class CoDirectorConfigBody(BaseModel):
    endpoint: Optional[str] = None
    selectedModel: Optional[str] = None
    timeoutSec: Optional[float] = None


class WikiExportBody(BaseModel):
    exportTitle: str = ""
    includeCover: bool = True
    includeToc: bool = True
    includeOpenQuestions: bool = True
    includeUnresolved: bool = True
    includeImages: bool = True
    includeAudioVideo: bool = True
    includeProductionMetadata: bool = True
    sectionsMode: str = "all"
    selectedSections: list[str] = []
    sizeMode: str = "optimized"


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


@router.get("/session-context")
async def session_context(
    project_id: Optional[str] = None,
    scene_id: Optional[str] = None,
    workspace: Optional[str] = None,
    content_tab: Optional[str] = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Canonical session-context contract (composed from existing stores)."""
    from ..codirector.session_context import build_session_context

    return build_session_context(
        db,
        project_id=project_id,
        active_scene_id=scene_id,
        active_workspace=workspace,
        active_content_tab=content_tab,
    )


@router.get("/projects/{project_id}/context")
async def get_project_context(
    project_id: str,
    pillars: Optional[str] = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve project pillar content for Co-Director context.

    Query param ``pillars`` is an optional comma-separated subset
    (e.g. ``story,script``). Omit to read all available pillars. Absent
    pillars resolve to ``null`` rather than raising.
    """
    from ..codirector.project_context import retrieve_project_context

    pillar_list = [p.strip() for p in pillars.split(",") if p.strip()] if pillars else None
    return retrieve_project_context(db, project_id, pillar_list)


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
            attachment_ids=body.attachment_ids or body.attachmentIds,
            active_content_tab=body.active_content_tab,
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
        # Truthful degradation: when the foundation LLM turn failed and a
        # deterministic fallback replied, the client can see it (and why).
        "fallbackUsed": bool((result.raw or {}).get("fallbackUsed", False)),
        "fallbackReason": (result.raw or {}).get("fallbackReason"),
        "providerError": (result.raw or {}).get("providerError"),
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
                origin_session_id=body.origin_session_id,
                attachment_ids=body.attachment_ids or body.attachmentIds,
                active_content_tab=body.active_content_tab,
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


class NextStepDeferBody(BaseModel):
    optionType: str
    userReason: Optional[str] = None
    reconsiderAfterStage: Optional[str] = None


@router.post("/projects/{project_id}/next-steps/defer")
async def defer_next_step(
    project_id: str, body: NextStepDeferBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    from ..codirector.conversation.next_steps import persist_deferred_option

    try:
        persist_deferred_option(
            db,
            project_id=project_id,
            option_type=body.optionType,  # type: ignore[arg-type]
            user_reason=body.userReason or body.reconsiderAfterStage,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail={"message": str(exc)[:200]}) from exc
    return {"ok": True, "projectId": project_id}


@router.get("/conversations/{project_id}")
async def get_conversation(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    convo = codirector_service.get_conversation(db, project_id)
    if convo:
        return convo
    return {
        "projectId": project_id,
        "messages": [],
        "model": None,
        "providerId": None,
        "updatedAt": None,
        "revision": codirector_service.get_conversation_revision(db, project_id),
    }


@router.post("/conversations/{project_id}/events")
async def append_conversation_events(
    project_id: str, body: ConversationEventsBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Append creator (or server) conversation events with idempotency + optimistic concurrency.

    The server is the source of truth for conversation durability. Clients
    append their user turns here instead of replacing the whole transcript.
    On a revision mismatch the response is HTTP 409 with the server's current
    revision and the canonical folded conversation, so the client can
    reconcile by id and retry.
    """

    from datetime import datetime as _dt

    events = [
        codirector_service.EventInput(  # type: ignore[attr-defined]
            role=e.role,
            content=e.content,
            event_type=e.event_type,
            message_id=e.message_id,
            client_request_id=e.client_request_id,
            message_type=e.message_type,
            status=e.status,
            attachments=e.attachments,
            tool_id=e.tool_id,
            tool_arguments=e.tool_arguments,
            tool_result=e.tool_result,
            request_id=e.request_id,
            actor=e.actor,
            created_at=_dt.fromisoformat(e.created_at) if e.created_at else None,
        )
        for e in body.events
    ]
    result = codirector_service.append_conversation_events(
        db,
        project_id,
        events,
        expected_revision=body.expected_revision,
        model=body.model,
        provider_id=body.provider_id,
    )
    if result.conflict:
        canonical = codirector_service.get_conversation(db, project_id) or {
            "projectId": project_id,
            "messages": [],
            "model": None,
            "providerId": None,
            "updatedAt": None,
            "revision": result.conflict_revision,
        }
        raise HTTPException(
            status_code=409,
            detail=CoDirectorError(
                "CONFLICT",
                "Conversation revision mismatch — reload and reconcile by id before retrying.",
                details={
                    "expected": body.expected_revision,
                    "actual": result.conflict_revision,
                    "canonical": canonical,
                },
                recoverable=True,
                recommended_action="reload",
            ).to_dict(),
        )
    return {
        "projectId": project_id,
        "appendedCount": result.appended_count,
        "duplicateCount": result.duplicate_count,
        "revision": result.revision,
        "events": list(result.events),
    }


@router.post("/conversations/{project_id}")
async def save_conversation(
    project_id: str, body: ConversationSaveBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """DEPRECATED full-replace path. Creator clients must append events instead.

    Retained for admin/repair tooling (`allow_admin_replace=true`) and the
    reversible migration backfill. A revision mismatch or a non-admin creator
    call yields a 409/400 respectively.
    """

    try:
        return codirector_service.save_conversation(
            db,
            project_id,
            messages=[m.model_dump() for m in body.messages],
            model=body.model,
            provider_id=body.provider_id,
            expected_revision=body.expected_revision,
            allow_admin_replace=body.allow_admin_replace,
        )
    except CoDirectorError as err:
        raise _http_error(err) from err


@router.delete("/conversations/{project_id}")
async def delete_conversation(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    ok = codirector_service.delete_conversation(db, project_id)
    return {"ok": ok, "projectId": project_id}


class ConversationCompactBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    before_sequence: int = Field(alias="beforeSequence")
    summary_text: str = Field(alias="summaryText")
    request_id: Optional[str] = Field(default=None, alias="requestId")


@router.post("/conversations/{project_id}/compact")
async def compact_conversation(
    project_id: str, body: ConversationCompactBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    from ..codirector.conversation_compaction import compact_conversation as _compact

    return _compact(
        db,
        project_id,
        before_sequence=body.before_sequence,
        summary_text=body.summary_text,
        request_id=body.request_id,
    )


@router.get("/conversations/{project_id}/revision")
async def get_conversation_revision(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    from ..db import CoDirectorConversation

    header = db.get(CoDirectorConversation, project_id)
    updated_at = header.updated_at.isoformat() if header and header.updated_at else None
    return {
        "projectId": project_id,
        "revision": codirector_service.get_conversation_revision(db, project_id),
        "updatedAt": updated_at,
    }


@router.get("/conversations/{project_id}/events/stream")
async def stream_conversation_events(project_id: str) -> StreamingResponse:
    """SSE revision broadcast — polls every ~2s, emits on change."""

    async def event_source():
        db = SessionLocal()
        try:
            last_revision = codirector_service.get_conversation_revision(db, project_id)
            idle_polls = 0
            max_idle = 30
            while idle_polls < max_idle:
                await asyncio.sleep(2)
                db.expire_all()
                revision = codirector_service.get_conversation_revision(db, project_id)
                if revision != last_revision:
                    last_revision = revision
                    idle_polls = 0
                    payload = {"type": "revision", "revision": revision}
                    yield f"data: {json.dumps(payload)}\n\n"
                else:
                    idle_polls += 1
                    yield ": keepalive\n\n"
        finally:
            db.close()

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/conversations/{project_id}/audit")
async def audit_conversation(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    from ..codirector.conversation_audit import audit_conversation as _audit

    return _audit(db, project_id)


@router.post("/conversations/{project_id}/repair/rebuild-fold")
async def repair_rebuild_fold(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    from ..codirector.conversation_audit import rebuild_fold

    return rebuild_fold(db, project_id)


@router.get("/projects/{project_id}/memory/export")
async def export_project_memory(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    from ..codirector.conversation_memory import export_memory

    return export_memory(db, project_id)


class MemoryImportBody(BaseModel):
    bundle: dict[str, Any]


@router.post("/projects/{project_id}/memory/import")
async def import_project_memory(
    project_id: str, body: MemoryImportBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    from ..codirector.conversation_memory import import_memory

    try:
        return import_memory(db, project_id, body.bundle)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err

@router.get("/projects/{project_id}/intelligence/snapshot")
async def get_intelligence_snapshot(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    from ..codirector.conversation.snapshot import load_snapshot
    from ..codirector.production_state.projection import build_production_state
    from ..codirector.production_state.stage_evidence import enrich_with_stage

    snapshot = load_snapshot(db, project_id)
    ps = build_production_state(db, project_id)
    ps = enrich_with_stage(ps, db, project_id)
    return {
        "projectId": project_id,
        "snapshot": snapshot.model_dump(mode="json"),
        "productionState": ps.model_dump(mode="json"),
    }


@router.get("/projects/{project_id}/production-state")
async def get_production_state(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    from ..codirector.production_state.projection import build_production_state
    from ..codirector.production_state.stage_evidence import enrich_with_stage

    ps = build_production_state(db, project_id)
    ps = enrich_with_stage(ps, db, project_id)
    return {"projectId": project_id, "productionState": ps.model_dump(mode="json")}


@router.get("/projects/{project_id}/relationship")
async def get_relationship_profile(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    from ..codirector.conversation.discovery import load_discovery_bundle
    from ..codirector.conversation.relationship import load_creator_profile, load_relationship_profile

    profile = load_relationship_profile(db, project_id)
    creator = load_creator_profile(db, project_id)
    discovery = load_discovery_bundle(db, project_id)
    return {
        "projectId": project_id,
        "relationship": profile.model_dump(mode="json"),
        "creator": creator.model_dump(mode="json"),
        "brief": discovery.brief.model_dump(mode="json"),
        "pulse": {
            "confirmedFacts": sum(1 for c in discovery.wiki_candidates if c.status == "CONFIRMED"),
            "emergingIdeas": sum(1 for c in discovery.wiki_candidates if c.status in {"EMERGING", "INFERRED"}),
            "openDecisions": len(discovery.discovery_questions),
            "creativeStage": discovery.creative_stage.value,
        },
        "wikiCandidateCount": len(discovery.wiki_candidates),
        "discoveryQuestions": [q.model_dump(mode="json") for q in discovery.discovery_questions[:12]],
    }


class RelationshipUpdateBody(BaseModel):
    assistantPreferredName: str | None = None
    userPreferredName: str | None = None
    primaryRole: str | None = None
    initiativeLevel: str | None = None
    feedbackStyle: str | None = None
    narrationMode: str | None = None
    documentationMode: str | None = None
    researchPermission: str | None = None
    defaultOwnership: str | None = None
    relationshipScope: str | None = None
    skip: bool = False


@router.post("/projects/{project_id}/relationship")
async def update_relationship_profile(
    project_id: str, body: RelationshipUpdateBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    from ..codirector.conversation.partnership import (
        apply_default_ownership,
        load_partnership_bundle,
        ownership_from_assistance_choice,
        save_partnership_bundle,
    )
    from ..codirector.conversation.relationship import (
        PrimaryRole,
        load_relationship_profile,
        save_relationship_profile,
        skip_onboarding,
    )

    if body.skip:
        profile = skip_onboarding(db, project_id)
        return {"projectId": project_id, "relationship": profile.model_dump(mode="json")}

    profile = load_relationship_profile(db, project_id)
    if body.assistantPreferredName is not None:
        profile.assistant_preferred_name = body.assistantPreferredName.strip() or profile.assistant_preferred_name
    if body.userPreferredName is not None:
        profile.user_preferred_name = body.userPreferredName.strip()
    if body.primaryRole:
        try:
            profile.primary_role = PrimaryRole(body.primaryRole)
        except ValueError:
            pass
    if body.initiativeLevel in {"RESPONSIVE", "PROACTIVE", "HIGH_INITIATIVE"}:
        profile.initiative_level = body.initiativeLevel  # type: ignore[assignment]
    if body.feedbackStyle in {"GENTLE", "BALANCED", "CANDID"}:
        profile.feedback_style = body.feedbackStyle  # type: ignore[assignment]
    if body.narrationMode in {"LISTEN_FIRST", "FOCUSED_QUESTIONS", "ACTIVE_DISCOVERY"}:
        profile.narration_mode = body.narrationMode  # type: ignore[assignment]
    if body.documentationMode in {"AUTO_CONFIRMED", "PROPOSE_FOR_APPROVAL", "MANUAL_ONLY"}:
        profile.documentation_mode = body.documentationMode  # type: ignore[assignment]
    if body.researchPermission in {"ASK_FIRST", "WHEN_USEFUL", "ACTIVE", "OFFLINE"}:
        profile.research_permission = body.researchPermission  # type: ignore[assignment]
    if body.defaultOwnership in {
        "USER_LEADS",
        "CO_CREATE",
        "CODIRECTOR_LEADS",
        "CODIRECTOR_EXECUTES",
        "ASK_EACH_TIME",
        "advise",
        "create_with_me",
        "first_drafts",
        "take_the_lead",
        "ask_each_stage",
    }:
        ownership = ownership_from_assistance_choice(body.defaultOwnership)
        profile.default_ownership = ownership.value  # type: ignore[assignment]
        bundle = load_partnership_bundle(db, project_id)
        apply_default_ownership(bundle.collaboration, ownership)
        save_partnership_bundle(db, project_id, bundle)
    if body.relationshipScope in {"GLOBAL", "PROJECT"}:
        profile.relationship_scope = body.relationshipScope  # type: ignore[assignment]
    if profile.user_preferred_name and profile.assistant_preferred_name:
        profile.onboarding_completed = True
    save_relationship_profile(db, project_id, profile)
    return {"projectId": project_id, "relationship": profile.model_dump(mode="json")}


@router.get("/projects/{project_id}/partnership")
async def get_partnership_bundle(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    from ..codirector.conversation.partnership import load_partnership_bundle

    bundle = load_partnership_bundle(db, project_id)
    return {"projectId": project_id, "partnership": bundle.model_dump(mode="json")}


class DeliverableActionBody(BaseModel):
    action: str  # approve | revise | reject | lock | expand
    content: str | None = None
    deliverableId: str | None = None


class CreativeInitiativeBody(BaseModel):
    initiativeLevel: str


class CuriosityThreadBody(BaseModel):
    threadId: str
    dismiss: bool = False


class ForwardSuggestionDismissBody(BaseModel):
    suggestionId: str


class IdentityCorrectionBody(BaseModel):
    surfaces: list[str] = Field(default_factory=list)
    canonicalName: str


class ScriptIntelligenceBody(BaseModel):
    text: str
    filename: str | None = None
    installmentHint: str | None = None


@router.get("/projects/{project_id}/creative-operating")
async def get_creative_operating_state(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    from ..codirector.creative_operating.service import get_creative_operating

    return get_creative_operating(db, project_id)


@router.put("/projects/{project_id}/creative-operating/initiative")
async def put_creative_initiative(
    project_id: str, body: CreativeInitiativeBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    from ..codirector.creative_operating.service import set_initiative_level

    return set_initiative_level(db, project_id, body.initiativeLevel)


@router.post("/projects/{project_id}/creative-operating/curiosity/answer")
async def answer_creative_curiosity(
    project_id: str, body: CuriosityThreadBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    from ..codirector.creative_operating.service import answer_curiosity_thread

    return answer_curiosity_thread(db, project_id, body.threadId, dismiss=body.dismiss)


@router.post("/projects/{project_id}/creative-operating/forward/dismiss")
async def dismiss_creative_forward(
    project_id: str, body: ForwardSuggestionDismissBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    from ..codirector.creative_operating.service import dismiss_forward_suggestion

    return dismiss_forward_suggestion(db, project_id, body.suggestionId)


@router.post("/projects/{project_id}/creative-operating/identity/correct")
async def correct_creative_identity(
    project_id: str, body: IdentityCorrectionBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    from ..codirector.creative_operating.service import apply_identity_correction

    return apply_identity_correction(
        db,
        project_id,
        surfaces=list(body.surfaces or []),
        canonical_name=body.canonicalName,
    )


@router.post("/projects/{project_id}/creative-operating/script/analyze")
async def analyze_creative_script(
    project_id: str, body: ScriptIntelligenceBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    import re

    from ..codirector.creative_operating.persistence import load_bundle, save_bundle
    from ..codirector.creative_operating.script_intelligence import (
        build_installment_record,
        detect_source_role,
        parse_script_breakdown,
    )
    from ..codirector.creative_operating.service import process_creative_operating_turn
    from ..codirector.notes.service import upsert_notes_from_texts
    from ..codirector.production_lifecycle.service import advance_script_status
    from ..codirector.wiki_intelligence.compiled.page_compiler import compile_wiki_bundle

    bundle = load_bundle(db, project_id)
    role = detect_source_role(filename=body.filename or "", hint="script")
    breakdown = parse_script_breakdown(
        body.text,
        alias_map=bundle.identityAliases,
        installment_hint=body.installmentHint,
    )
    installment = build_installment_record(breakdown)
    ep_num = 1
    hint = body.installmentHint or installment.get("title") or ""
    m = re.search(r"(\d+)", str(hint))
    if m:
        ep_num = int(m.group(1))
    installment["episodeNumber"] = ep_num
    installment["number"] = ep_num
    installment["summary"] = installment.get("overview") or breakdown.get("summary") or ""
    installment["scenes"] = breakdown.get("scenes") or []
    installment["sourceFilename"] = body.filename or ""
    # Persist installment on creative-operating bundle
    existing = [i for i in (bundle.installments or []) if int(i.get("episodeNumber") or 0) != ep_num]
    existing.insert(0, installment)
    bundle.installments = existing[:20]
    save_bundle(db, bundle)

    # Notes working desk gets raw discoveries; Wiki gets compiled episode after promote/compile
    discovery_bits = [
        f"Script source registered: {body.filename or 'script'}",
        *[f"Scene: {s.get('heading')}" for s in (breakdown.get("scenes") or [])[:8] if isinstance(s, dict)],
        *[
            f"Character in script: {c.get('canonicalName')}"
            for c in (breakdown.get("characters") or [])[:8]
            if isinstance(c, dict) and c.get("canonicalName")
        ],
    ]
    upsert_notes_from_texts(
        db, project_id, discovery_bits, source="uploaded_script", category="Story"
    )

    # Knowledge entries for characters (confirmed from script)
    try:
        from ..codirector.conversation.knowledge import apply_wiki_candidates
        from ..codirector.conversation.schemas import WikiCandidate
        from ..codirector.conversation.snapshot import load_snapshot, save_snapshot

        snap = load_snapshot(db, project_id)
        cands: list[WikiCandidate] = []
        for c in breakdown.get("characters") or []:
            name = (c.get("canonicalName") if isinstance(c, dict) else None) or ""
            if not name:
                continue
            cands.append(
                WikiCandidate(
                    id=f"script-char-{name.lower().replace(' ', '-')[:24]}",
                    text=f"{name} appears in {installment.get('title') or f'Episode {ep_num}'}.",
                    state="confirmed",
                    section="characters",
                    provenance="script_analyze",
                )
            )
        if installment.get("summary"):
            cands.append(
                WikiCandidate(
                    id=f"script-ep-{ep_num}",
                    text=str(installment.get("summary")),
                    state="confirmed",
                    section="storyAndEpisodes",
                    provenance="script_analyze",
                )
            )
        if cands:
            snap = apply_wiki_candidates(snap, cands, "script analyze intake")
            save_snapshot(db, snap)
    except Exception:  # noqa: BLE001
        pass

    # Script stage at least DRAFT
    advance_script_status(db, project_id, "DRAFT")

    process_creative_operating_turn(
        db,
        project_id=project_id,
        user_message=f"Source {role} attached for analysis.",
        script_text=body.text,
        script_filename=body.filename,
        candidate_count=1,
    )
    # Use the async Story Summary Editor path so summaries become editorial prose.
    from ..codirector.wiki_intelligence.compiled.page_compiler import compile_wiki_bundle_async

    compiled = await compile_wiki_bundle_async(db, project_id, force_full=True)
    return {
        "ok": True,
        "projectId": project_id,
        "role": role,
        "breakdown": breakdown,
        "installment": installment,
        "compiledRevision": compiled.get("compiledRevision"),
        "episodePage": next(
            (p for p in (compiled.get("pages") or []) if p.get("pageType") == "EPISODE"),
            None,
        ),
    }


class CreativeDecideBody(BaseModel):
    message: str
    specialistPositions: dict[str, str] | None = None


@router.post("/projects/{project_id}/creative-operating/decision")
async def post_creative_decision(
    project_id: str, body: CreativeDecideBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    from ..codirector.creative_operating.decision_loop import run_creative_decision_loop

    primary_type = None
    try:
        from app.db import Project

        proj = db.get(Project, project_id)
        primary_type = getattr(proj, "primary_project_type", None) if proj else None
    except Exception:  # noqa: BLE001
        primary_type = None
    decision, bundle = run_creative_decision_loop(
        db,
        project_id=project_id,
        user_message=body.message,
        primary_project_type=primary_type,
        specialist_positions=body.specialistPositions,
        persist=True,
    )
    next_steps: list[str] = []
    lifecycle_payload = None
    try:
        from ..codirector.production_lifecycle.service import get_lifecycle, stage_aware_next_steps
        from ..codirector.production_lifecycle.contracts import ProjectProductionLifecycle
        from ..codirector.creative_operating.composition import soft_next_step_invitations

        lifecycle_payload = get_lifecycle(db, project_id)
        life = ProjectProductionLifecycle.model_validate(lifecycle_payload["lifecycle"])
        next_steps = soft_next_step_invitations(
            decision, lifecycle_next_steps=stage_aware_next_steps(life)
        )
    except Exception:  # noqa: BLE001
        next_steps = []
    stage = (
        (lifecycle_payload or {}).get("lifecycle", {}).get("currentStage")
        if lifecycle_payload
        else None
    )
    specialists = (lifecycle_payload or {}).get("specialistsForStage") if lifecycle_payload else None
    return {
        "ok": True,
        "projectId": project_id,
        "decision": decision.model_dump(mode="json"),
        "initiativeLevel": bundle.initiativeLevel,
        "curiosityThreads": [t.model_dump(mode="json") for t in bundle.curiosityThreads[:5]],
        "forwardSuggestions": [
            s.model_dump(mode="json") for s in bundle.forwardSuggestions if s.state == "ACTIVE"
        ][:3],
        "nextSteps": next_steps,
        "lifecycleStage": stage,
        "specialistsForStage": specialists or [],
        "handoffs": (lifecycle_payload or {}).get("handoffs") if lifecycle_payload else None,
    }


@router.post("/projects/{project_id}/partnership/deliverables")
async def partnership_deliverable_action(
    project_id: str, body: DeliverableActionBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    from ..codirector.conversation.partnership import (
        load_partnership_bundle,
        revise_deliverable,
        save_partnership_bundle,
        set_deliverable_status,
    )
    from ..codirector.conversation.partnership.schemas import CreativeDeliverableStatus

    bundle = load_partnership_bundle(db, project_id)
    deliverable_id = body.deliverableId or (bundle.deliverables[-1].id if bundle.deliverables else "")
    if not deliverable_id:
        return {"projectId": project_id, "ok": False, "error": "No deliverable"}
    action = (body.action or "").lower()
    result = None
    if action == "approve":
        result = set_deliverable_status(bundle, deliverable_id, CreativeDeliverableStatus.APPROVED)
    elif action == "reject":
        result = set_deliverable_status(bundle, deliverable_id, CreativeDeliverableStatus.REJECTED)
    elif action == "lock":
        result = set_deliverable_status(bundle, deliverable_id, CreativeDeliverableStatus.LOCKED)
    elif action == "revise" and body.content:
        result = revise_deliverable(bundle, deliverable_id, body.content)
    elif action == "expand" and body.content:
        from ..codirector.conversation.partnership import expand_preview_to_draft

        result = expand_preview_to_draft(bundle, deliverable_id, body.content)
    save_partnership_bundle(db, project_id, bundle)
    return {
        "projectId": project_id,
        "ok": result is not None,
        "deliverable": result.model_dump(mode="json") if result else None,
        "partnership": bundle.model_dump(mode="json"),
    }


@router.get("/projects/{project_id}/wiki")
async def get_project_wiki(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    from ..codirector.wiki import build_project_wiki

    try:
        return build_project_wiki(db, project_id)
    except CoDirectorError as err:
        raise _http_error(err) from err


class WikiPromoteBody(BaseModel):
    text: str | None = None
    noteId: str | None = None
    destination: str = "story"
    pageHint: str | None = None


@router.post("/projects/{project_id}/wiki/promote")
async def promote_to_wiki(
    project_id: str, body: WikiPromoteBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    from ..codirector.notes.service import promote_note_to_wiki
    from ..codirector.wiki_intelligence.compiled.page_compiler import compile_wiki_bundle_async

    result = promote_note_to_wiki(
        db,
        project_id,
        note_id=body.noteId,
        text=body.text,
        destination=body.destination,
        authority="USER_EXPLICIT_WIKI_WRITE",
        page_hint=body.pageHint,
    )
    # Refresh Story Summary with the editorial editor now that new canon exists.
    await compile_wiki_bundle_async(db, project_id, force_full=True)
    return result


class WikiCompileBody(BaseModel):
    # When True (manual "Save to Wiki"), the compiled Story summary is taken
    # verbatim from the saved Story record via the sync compiler — exact
    # creator-authored wording is preserved, no provider rephrasing. When
    # False/absent, the async editorial compiler may refine the prose.
    preserveStoryWording: bool = False


@router.post("/projects/{project_id}/wiki/compile")
async def compile_project_wiki(
    project_id: str,
    body: WikiCompileBody | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if body and body.preserveStoryWording:
        # Manual Save-to-Wiki: preserve exact creator-authored wording by
        # using the sync compiler, which reads the Story record verbatim
        # (compile_story_summary) and does not invoke an editorial provider.
        from ..codirector.wiki_intelligence.compiled.page_compiler import compile_wiki_bundle

        compiled = compile_wiki_bundle(db, project_id, force_full=True)
        return {"ok": True, "projectId": project_id, "compiled": compiled}

    from ..codirector.wiki_intelligence.compiled.page_compiler import compile_wiki_bundle_async

    compiled = await compile_wiki_bundle_async(db, project_id, force_full=True)
    return {"ok": True, "projectId": project_id, "compiled": compiled}


class StorySummaryCorrectBody(BaseModel):
    correction: str


@router.post("/projects/{project_id}/wiki/story-summary/refine")
async def refine_story_summary(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Force a Story Summary Editor pass with the live provider."""
    from ..codirector.wiki_intelligence.compiled.story_summary_editor import edit_story_summary

    summary = await edit_story_summary(db, project_id, force=True)
    return {
        "ok": True,
        "projectId": project_id,
        "storySummary": summary.model_dump(mode="json"),
    }


@router.post("/projects/{project_id}/wiki/story-summary/correct")
async def correct_story_summary(
    project_id: str, body: StorySummaryCorrectBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Record a creator correction as a creator-stated interpretation, then recompile."""
    import uuid

    from ..codirector.conversation.snapshot import load_snapshot, save_snapshot
    from ..codirector.wiki_intelligence.compiled.story_summary_editor import edit_story_summary

    correction = (body.correction or "").strip()
    if not correction:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="correction is required")

    from ..codirector.conversation.knowledge import apply_wiki_candidates
    from ..codirector.conversation.schemas import WikiCandidate

    snapshot = load_snapshot(db, project_id)
    candidate = WikiCandidate(
        id=str(uuid.uuid4()),
        text=correction,
        state="confirmed",
        section="storyAndEpisodes",
        provenance="USER_EXPLICIT_WIKI_WRITE",
    )
    snapshot = apply_wiki_candidates(snapshot, [candidate], correction)
    save_snapshot(db, snapshot)

    summary = await edit_story_summary(db, project_id, force=True)
    return {
        "ok": True,
        "projectId": project_id,
        "storySummary": summary.model_dump(mode="json"),
    }


# --- Refine Wiki — Creator Correction -------------------------------------

# In-process preview store (previewId -> CorrectionPreview). Previews are
# short-lived and project-scoped; apply requires a prior preview (CREATOR_APPROVES).
_CORRECTION_PREVIEWS: dict[str, Any] = {}


class WikiCorrectionPreviewBody(BaseModel):
    instruction: str
    target: dict[str, Any] | None = None


class WikiCorrectionApplyBody(BaseModel):
    previewId: str


@router.post("/projects/{project_id}/wiki/correction/preview")
async def preview_wiki_correction(
    project_id: str,
    body: WikiCorrectionPreviewBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Classify a natural-language correction and return a preview diff.

    LLM_INTERPRETS: an LLM classifies when a provider is available; a
    deterministic heuristic classifier is the fallback. No mutation happens here.
    """
    import uuid

    from fastapi import HTTPException

    from ..codirector.wiki_intelligence.correction.classify import classify_correction
    from ..codirector.wiki_intelligence.correction.contracts import CorrectionTarget

    instruction = (body.instruction or "").strip()
    if not instruction:
        raise HTTPException(status_code=400, detail="instruction is required")

    target = None
    if isinstance(body.target, dict):
        target = CorrectionTarget(
            **{k: v for k, v in body.target.items() if k in CorrectionTarget.model_fields}
        )

    # Resolve a provider for classification (bounded; falls back to heuristic).
    provider = None
    try:
        from ..codirector.intelligence.specialist_runner import resolve_provider_for_specialists
        import asyncio

        provider, use_provider, _ = await asyncio.wait_for(
            resolve_provider_for_specialists(None), timeout=10.0
        )
        if not use_provider:
            provider = None
    except Exception:  # noqa: BLE001
        provider = None

    preview = await classify_correction(
        db,
        project_id,
        instruction,
        target=target,
        provider=provider,
        preview_id=f"prev_{uuid.uuid4().hex[:12]}",
    )
    _CORRECTION_PREVIEWS[preview.previewId] = preview
    return {"ok": True, "preview": preview.model_dump(mode="json")}


@router.post("/projects/{project_id}/wiki/correction/apply")
async def apply_wiki_correction(
    project_id: str,
    body: WikiCorrectionApplyBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Apply a confirmed correction (DETERMINISTIC_CODE_APPLIES), recompile, return undo id."""
    from fastapi import HTTPException

    from ..codirector.wiki_intelligence.compiled.page_compiler import compile_wiki_bundle_async
    from ..codirector.wiki_intelligence.correction.apply import apply_correction

    preview = _CORRECTION_PREVIEWS.get(body.previewId)
    if preview is None:
        raise HTTPException(status_code=404, detail="preview_not_found")
    if preview.projectId != project_id:
        raise HTTPException(status_code=403, detail="preview_project_mismatch")

    result = apply_correction(db, project_id, preview)
    if not result.get("ok"):
        return result

    # Recompile the Wiki so affected pages reflect the correction.
    compiled = await compile_wiki_bundle_async(db, project_id, force_full=True)
    result["compiledRevision"] = compiled.get("compiledRevision")
    # Consume the preview so it cannot be applied twice.
    _CORRECTION_PREVIEWS.pop(body.previewId, None)
    return result


@router.post("/projects/{project_id}/wiki/correction/{correction_id}/undo")
async def undo_wiki_correction(
    project_id: str, correction_id: str, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Restore the pre-correction snapshot (CORRECTION_MUST_BE_REVERSIBLE)."""
    from ..codirector.wiki_intelligence.correction.undo import undo_correction

    return undo_correction(db, project_id, correction_id)


@router.get("/projects/{project_id}/wiki/corrections")
async def list_wiki_corrections(
    project_id: str, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """List durable creator-correction history for this project."""
    from ..codirector.wiki_intelligence.correction.apply import list_corrections

    return {"ok": True, "projectId": project_id, "corrections": list_corrections(db, project_id)}


@router.get("/projects/{project_id}/notes")
async def get_project_notes(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    from ..codirector.notes.service import list_notes

    return list_notes(db, project_id)


class NoteDismissBody(BaseModel):
    noteId: str


@router.post("/projects/{project_id}/notes/dismiss")
async def dismiss_project_note(
    project_id: str, body: NoteDismissBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    from ..codirector.notes.service import dismiss_note

    return dismiss_note(db, project_id, body.noteId)


@router.get("/projects/{project_id}/production-lifecycle")
async def get_production_lifecycle(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    from ..codirector.production_lifecycle.service import get_lifecycle, stage_aware_next_steps
    from ..codirector.production_lifecycle.contracts import ProjectProductionLifecycle

    payload = get_lifecycle(db, project_id)
    life = ProjectProductionLifecycle.model_validate(payload["lifecycle"])
    payload["nextSteps"] = stage_aware_next_steps(life)
    # specialistsForStage / handoffs / sceneReadinessMatrix already on payload
    return payload


class LifecycleScriptBody(BaseModel):
    status: str


@router.put("/projects/{project_id}/production-lifecycle/script")
async def put_lifecycle_script(
    project_id: str, body: LifecycleScriptBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    from ..codirector.production_lifecycle.service import advance_script_status

    return advance_script_status(db, project_id, body.status)


class LifecycleCastBody(BaseModel):
    characterName: str
    status: str
    exploratory: bool = False
    wikiPageId: str | None = None


@router.post("/projects/{project_id}/production-lifecycle/casting")
async def post_lifecycle_casting(
    project_id: str, body: LifecycleCastBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    from ..codirector.production_lifecycle.service import set_character_cast_status

    return set_character_cast_status(
        db,
        project_id,
        character_name=body.characterName,
        status=body.status,
        exploratory=body.exploratory,
        wiki_page_id=body.wikiPageId,
    )


class LifecycleSceneBody(BaseModel):
    scene: dict[str, Any]


@router.post("/projects/{project_id}/production-lifecycle/scenes")
async def post_lifecycle_scene(
    project_id: str, body: LifecycleSceneBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    from ..codirector.production_lifecycle.service import upsert_scene_readiness

    return upsert_scene_readiness(db, project_id, body.scene)


@router.get("/projects/{project_id}/production-lifecycle/scenes/{scene_id}/package")
async def get_scene_package(
    project_id: str, scene_id: str, db: Session = Depends(get_db)
) -> dict[str, Any]:
    from ..codirector.production_lifecycle.service import scene_production_package

    return scene_production_package(db, project_id, scene_id)


@router.get("/projects/{project_id}/timeline-context/scene-status")
async def get_timeline_scene_status(
    project_id: str, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Aggregate scene lifecycle counts across a project (SCENE_HAS_LIFECYCLE_STATUS).

    Declared BEFORE the ``{scene_id}`` route so FastAPI does not match the
    literal ``scene-status`` as a scene id.
    """
    from ..codirector.timeline_context.service import get_scene_status_aggregate

    return get_scene_status_aggregate(db, project_id)


@router.get("/projects/{project_id}/timeline-context/{scene_id}")
async def get_timeline_context_package(
    project_id: str,
    scene_id: str,
    action_scope: str = "exploration",
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Single TimelineContextPackage for a scene (TIMELINE_CONSUMES_CONTEXT_PACKAGE).

    Co-Director produces one object bundling locked canon, approved references,
    cast, locations, continuity, wardrobe, production notes, reference assets,
    generation constraints, and scene readiness. The Timeline consumes it.
    """
    from ..codirector.timeline_context.service import build_timeline_context_package

    if action_scope not in {"exploration", "production"}:
        action_scope = "exploration"
    return build_timeline_context_package(db, project_id, scene_id, action_scope=action_scope)


@router.get("/projects/{project_id}/timeline-context/{scene_id}/gate")
async def get_timeline_smart_gate(
    project_id: str,
    scene_id: str,
    action_scope: str = "production",
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Evaluate the Smart Production Gate for a scene (SMART_PRODUCTION_GATES)."""
    from ..codirector.timeline_context.smart_gates import evaluate_smart_gate

    if action_scope not in {"exploration", "production"}:
        action_scope = "production"
    return evaluate_smart_gate(db, project_id, scene_id, action_scope=action_scope)


class LifecycleCompleteBody(BaseModel):
    level: str = "PROJECT"


@router.post("/projects/{project_id}/production-lifecycle/complete")
async def post_lifecycle_complete(
    project_id: str, body: LifecycleCompleteBody | None = None, db: Session = Depends(get_db)
) -> dict[str, Any]:
    from ..codirector.production_lifecycle.service import mark_complete, run_final_qc

    # Require QC pass first if not already
    run_final_qc(db, project_id, passed=True)
    return mark_complete(db, project_id, level=(body.level if body else "PROJECT"))


@router.post("/projects/{project_id}/production-lifecycle/reopen")
async def post_lifecycle_reopen(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    from ..codirector.production_lifecycle.service import reopen_complete

    return reopen_complete(db, project_id)


@router.post("/projects/{project_id}/production-lifecycle/final-qc")
async def post_lifecycle_final_qc(
    project_id: str, body: dict[str, Any] | None = None, db: Session = Depends(get_db)
) -> dict[str, Any]:
    from ..codirector.production_lifecycle.service import run_final_qc

    passed = True if not body else bool(body.get("passed", True))
    return run_final_qc(db, project_id, passed=passed)


@router.post("/projects/{project_id}/production-lifecycle/timeline-ready")
async def post_lifecycle_timeline_ready(
    project_id: str, db: Session = Depends(get_db)
) -> dict[str, Any]:
    from ..codirector.production_lifecycle.service import mark_timeline_ready

    return mark_timeline_ready(db, project_id)


class LifecyclePostBody(BaseModel):
    status: str = "IN_PROGRESS"


@router.post("/projects/{project_id}/production-lifecycle/post")
async def post_lifecycle_post(
    project_id: str, body: LifecyclePostBody | None = None, db: Session = Depends(get_db)
) -> dict[str, Any]:
    from ..codirector.production_lifecycle.service import mark_post_progress

    status = (body.status if body else "IN_PROGRESS") or "IN_PROGRESS"
    return mark_post_progress(db, project_id, status)


@router.post("/projects/{project_id}/production-lifecycle/story-ready")
async def post_lifecycle_story_ready(
    project_id: str, db: Session = Depends(get_db)
) -> dict[str, Any]:
    from ..codirector.production_lifecycle.service import set_story_ready

    return set_story_ready(db, project_id, True)


@router.post("/projects/{project_id}/wiki/rebuild")
async def rebuild_project_wiki(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Generic Rebuild Wiki from conversation for any project."""
    from ..codirector.conversation.wiki_rebuild import rebuild_wiki_from_conversation

    return rebuild_wiki_from_conversation(db, project_id)


@router.get("/projects/{project_id}/wiki/diagnostic")
async def diagnose_project_wiki(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    from ..codirector.conversation.wiki_rebuild import diagnose_wiki

    return diagnose_wiki(db, project_id)


class WikiReorganizeBody(BaseModel):
    domains: list[str] | None = None
    useSpecialists: bool = True
    preserveLockedCanon: bool = True
    createUndoSnapshot: bool = True


@router.post("/projects/{project_id}/wiki/reorganize")
async def reorganize_project_wiki(
    project_id: str,
    body: WikiReorganizeBody | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Professional Reorganize Wiki — specialist-driven cleanup with undo snapshot."""
    from ..codirector.wiki_intelligence.compiled.page_compiler import compile_wiki_bundle_async
    from ..codirector.wiki_intelligence.reorganize import start_wiki_reorganization

    payload = body or WikiReorganizeBody()
    result = start_wiki_reorganization(
        db,
        project_id,
        domains=payload.domains,
        use_specialists=payload.useSpecialists,
        preserve_locked_canon=payload.preserveLockedCanon,
        create_undo_snapshot=payload.createUndoSnapshot,
    )
    # Refresh Story Summary after reorganization.
    await compile_wiki_bundle_async(db, project_id, force_full=True)
    return result


@router.get("/projects/{project_id}/wiki/reorganize/{job_id}")
async def get_wiki_reorganize_job(
    project_id: str, job_id: str, db: Session = Depends(get_db)
) -> dict[str, Any]:
    from ..codirector.wiki_intelligence.reorganize import get_reorganization_job

    return get_reorganization_job(db, project_id, job_id)


@router.post("/projects/{project_id}/wiki/reorganize/{job_id}/undo")
async def undo_wiki_reorganize(
    project_id: str, job_id: str, db: Session = Depends(get_db)
) -> dict[str, Any]:
    from ..codirector.wiki_intelligence.reorganize import undo_wiki_reorganization

    return undo_wiki_reorganization(db, project_id, job_id)


@router.get("/projects/{project_id}/wiki/reorganization-history")
async def wiki_reorganization_history(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    from ..codirector.wiki_intelligence.reorganize import list_reorganization_history

    return list_reorganization_history(db, project_id)


@router.get("/projects/{project_id}/wiki/health")
async def wiki_health(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Background maintenance health summary for the Project Wiki."""
    from ..codirector.wiki_intelligence.maintenance import wiki_health_report

    return wiki_health_report(db, project_id)


@router.get("/projects/{project_id}/wiki/tool-context")
async def wiki_tool_context(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Project-scoped Wiki context for image/video/script/audio tools."""
    from ..codirector.wiki_intelligence.maintenance import tool_wiki_context

    return tool_wiki_context(db, project_id)


class WikiMaintenanceBody(BaseModel):
    applyLightCleanup: bool = False


@router.post("/projects/{project_id}/wiki/maintenance")
async def wiki_maintenance(
    project_id: str,
    body: WikiMaintenanceBody | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Bounded Wiki maintenance job (health scan; optional light cleanup). Never alters LOCKED canon."""
    from ..codirector.wiki_intelligence.maintenance import run_wiki_maintenance

    payload = body or WikiMaintenanceBody()
    return run_wiki_maintenance(db, project_id, apply_light_cleanup=payload.applyLightCleanup)


@router.post("/projects/{project_id}/conversation/remediate-reasoning")
async def remediate_conversation_reasoning(
    project_id: str, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Quarantine leaked internal reasoning from persisted assistant messages."""
    from ..codirector.conversation.reasoning_remediation import remediate_project_reasoning_leaks

    return remediate_project_reasoning_leaks(db, project_id)


def _wiki_export_options(body: WikiExportBody):
    from ..codirector.wiki_export import WikiExportOptions

    return WikiExportOptions(
        export_title=body.exportTitle,
        include_cover=body.includeCover,
        include_toc=body.includeToc,
        include_open_questions=body.includeOpenQuestions,
        include_unresolved=body.includeUnresolved,
        include_images=body.includeImages,
        include_audio_video=body.includeAudioVideo,
        include_production_metadata=body.includeProductionMetadata,
        sections_mode=body.sectionsMode,
        selected_sections=tuple(body.selectedSections or ()),
        size_mode=body.sizeMode,
    )


@router.post("/projects/{project_id}/wiki/export/pdf")
async def export_project_wiki_pdf(
    project_id: str, body: WikiExportBody, db: Session = Depends(get_db)
) -> Response:
    from ..codirector.wiki_export import export_pdf_bytes

    try:
        payload, filename = export_pdf_bytes(db, project_id, _wiki_export_options(body))
    except CoDirectorError as err:
        raise _http_error(err) from err
    return Response(
        content=payload,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/projects/{project_id}/wiki/export/html")
async def export_project_wiki_html(
    project_id: str, body: WikiExportBody, db: Session = Depends(get_db)
) -> Response:
    from ..codirector.wiki_export import export_offline_html_zip

    try:
        payload, filename = export_offline_html_zip(db, project_id, _wiki_export_options(body))
    except CoDirectorError as err:
        raise _http_error(err) from err
    return Response(
        content=payload,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/projects/{project_id}/plans/active")
async def get_active_project_plan(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        plan = PlanService.active_plan(db, project_id)
    except CoDirectorError as err:
        raise _http_error(err) from err
    if not plan:
        return {"ok": True, "status": "not_created", "plan": None}
    return {
        "ok": True,
        "status": "active",
        "plan": {
            "planId": plan.planId,
            "title": plan.title,
            "state": plan.state,
            "version": plan.version,
            "activeStepId": plan.activeStepId,
            "updatedAt": plan.updatedAt,
        },
    }


@router.get("/projects/{project_id}/plans/{plan_id}")
async def get_project_plan(project_id: str, plan_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        plan = PlanService.get(db, project_id, plan_id)
    except CoDirectorError as err:
        raise _http_error(err) from err
    return {"ok": True, "status": "active", "plan": plan.model_dump(mode="json")}


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


def _bind_unlock(request: Request, project_id: str):
    from ..codirector.tools.execution import reset_request_unlock_token, set_request_unlock_token
    from ..project_security import service as project_security

    token = project_security.extract_unlock_token_for_project(request, project_id)
    return set_request_unlock_token(token), reset_request_unlock_token


@router.post("/projects/{project_id}/tools/read")
async def run_read_tool(
    project_id: str, body: ToolReadRequest, request: Request, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Run a read tool now. Rejects mutating tools with `TOOL_KIND_MISMATCH`."""

    tok, reset = _bind_unlock(request, project_id)
    try:
        invocation = await ToolExecutionService.execute_read(
            db,
            project_id=project_id,
            tool_id=body.toolId,
            arguments=body.arguments,
            scene_id=body.sceneId,
            request_id=body.requestId,
            created_by="user",
            tool_schema_version=body.toolSchemaVersion,
        )
    except CoDirectorError as err:
        raise _http_error(err) from err
    finally:
        reset(tok)
    return invocation.model_dump(mode="json")


@router.post("/projects/{project_id}/tools/audited")
async def run_audited_tool(
    project_id: str, body: ToolReadRequest, request: Request, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Run an audited mutating tool that opts out of human proposal (Wave 4 create_draft)."""

    tok, reset = _bind_unlock(request, project_id)
    try:
        invocation = await ToolExecutionService.execute_audited(
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
    finally:
        reset(tok)
    return invocation.model_dump(mode="json")


@router.post("/projects/{project_id}/tools/proposals")
async def propose_tool_call(
    project_id: str, body: ToolProposalRequest, request: Request, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Create a `tool_call` proposal for a mutating tool. Nothing is applied until approval."""

    tok, reset = _bind_unlock(request, project_id)
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
    finally:
        reset(tok)
    return proposal.model_dump(mode="json")


@router.get("/projects/{project_id}/tool-invocations")
async def list_tool_invocations(
    project_id: str, tool_id: Optional[str] = None, limit: int = 50, db: Session = Depends(get_db)
) -> dict[str, Any]:
    invocations = ToolExecutionService.list_invocations(db, project_id, tool_id=tool_id, limit=limit)
    return {"projectId": project_id, "invocations": [i.model_dump(mode="json") for i in invocations]}
