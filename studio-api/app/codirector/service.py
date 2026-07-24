"""Co-Director gateway: provider selection, chat composition, cancellation, persistence.

Browser never talks to Ollama directly — everything routes through this gateway so
transport failures can be classified into structured `CoDirectorError`s instead of a
bare `TypeError: Failed to fetch` reaching the chat UI.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime
from typing import Any, AsyncIterator, Optional

from sqlalchemy.orm import Session

from .. import assistant as assistant_module
from ..assistant import SceneSetupProposal
from ..config import settings
from ..db import CoDirectorConversation, Project, Scene
from ..learning import learning_context_block, parse_learning
from . import config_store
from .bible.context import ProjectContextService
from .bible.proposals import ProposalService
from .bible.schemas import ContextManifest, ProposalOut
from .errors import (
    PROJECT_NOT_FOUND,
    REQUEST_CANCELLED,
    STRUCTURED_OUTPUT_INVALID,
    VALIDATION_ERROR,
    CoDirectorError,
)
from .providers.base import ChatRequest, ChatResult, CoDirectorProvider, ProviderHealthResult, ProviderModel
from .providers.mock import MockCoDirectorProvider
from .providers.ollama import OllamaProvider
from .structured_output import extract_proposal_block, strip_proposal_blocks

PROVIDER_IDS: list[str] = ["ollama", "mock"]

_active_tasks: dict[str, "asyncio.Task[Any]"] = {}
_cancelled: set[str] = set()


def new_request_id() -> str:
    return uuid.uuid4().hex


def e2e_enabled() -> bool:
    return os.environ.get("STUDIO_E2E", "").strip() in ("1", "true", "TRUE", "yes", "YES")


def active_provider_id() -> str:
    """ADEPT_CODIRECTOR_PROVIDER wins; otherwise E2E defaults to the deterministic mock.

    The mock provider is a test/offline double only — it is never selectable in a
    production run even if `ADEPT_CODIRECTOR_PROVIDER=mock` is set by mistake, because
    that would silently mask a broken local-model deployment for real users.
    """
    override = os.environ.get("ADEPT_CODIRECTOR_PROVIDER", "").strip().lower()
    if override == "mock" and not e2e_enabled():
        return "ollama"
    if override in PROVIDER_IDS:
        return override
    if e2e_enabled():
        return "mock"
    return "ollama"


def list_provider_ids() -> list[str]:
    """Providers selectable via the UI/API — mock is hidden outside E2E."""
    if e2e_enabled():
        return list(PROVIDER_IDS)
    return [p for p in PROVIDER_IDS if p != "mock"]


def build_provider(provider_id: str) -> CoDirectorProvider:
    if provider_id == "mock":
        if not e2e_enabled():
            raise CoDirectorError(
                "PROVIDER_NOT_CONFIGURED",
                "The mock Co-Director provider is only available in E2E/test runs.",
                details={"provider": provider_id},
                recoverable=False,
                recommended_action="select_model",
            )
        return MockCoDirectorProvider()
    if provider_id == "ollama":
        cfg = config_store.load_config()
        return OllamaProvider(
            base_url=str(cfg.get("endpoint") or settings.ollama_url),
            default_model=str(cfg.get("selectedModel") or "") or (settings.ollama_model or None),
            timeout_sec=float(cfg.get("timeoutSec") or settings.ollama_timeout_sec),
        )
    raise CoDirectorError(
        "PROVIDER_NOT_CONFIGURED",
        f"Unknown Co-Director provider '{provider_id}'.",
        details={"provider": provider_id},
        recoverable=False,
        recommended_action="select_model",
    )


def get_provider(provider_id: str | None = None) -> CoDirectorProvider:
    return build_provider(provider_id or active_provider_id())


async def list_providers_info() -> list[dict[str, Any]]:
    active = active_provider_id()
    out: list[dict[str, Any]] = []
    for pid in list_provider_ids():
        provider = build_provider(pid)
        out.append({"id": pid, "displayName": provider.display_name, "active": pid == active})
    return out


async def get_health(provider_id: str | None = None) -> ProviderHealthResult:
    pid = provider_id or active_provider_id()
    try:
        provider = build_provider(pid)
        return await provider.health()
    except CoDirectorError as err:
        return ProviderHealthResult(
            provider_id=pid,
            display_name=pid,
            status="Degraded",
            reachable=False,
            endpoint="",
            selected_model=None,
            model_available=False,
            models=[],
            message=err.message,
            code=err.code,
            recommended_action=err.recommended_action,
        )


async def list_models(provider_id: str | None = None) -> list[ProviderModel]:
    provider = get_provider(provider_id)
    return await provider.list_models()


# --------------------------------------------------------------------------
# Chat composition (shared by /api/codirector/chat and legacy /api/assistant/chat)
# --------------------------------------------------------------------------


def _build_project_payload(db: Session, project_id: str) -> dict[str, Any]:
    from ..db import Asset  # local import avoids widening module-level surface

    project = db.get(Project, project_id)
    scenes = db.query(Scene).filter(Scene.project_id == project_id).order_by(Scene.index).all()
    assets = db.query(Asset).filter(Asset.project_id == project_id).all()
    return {
        "name": project.name,
        "engine_default": project.engine_default,
        "width": project.width,
        "height": project.height,
        "fps": project.fps,
        "preset": project.preset,
        "vram_gb": project.vram_gb,
        "global_prompt": project.global_prompt,
        "assets": [{"id": a.id, "tag": a.tag, "kind": a.kind, "filename": a.filename} for a in assets],
        "scenes": [
            {
                "id": s.id,
                "index": s.index,
                "name": s.name,
                "engine": s.engine,
                "duration_sec": s.duration_sec,
                "prompt": s.prompt,
                "start_asset_id": s.start_asset_id,
                "middle_asset_id": s.middle_asset_id,
                "end_asset_id": s.end_asset_id,
                "lipsync_enabled": s.lipsync_enabled,
            }
            for s in scenes
        ],
    }


def _scene_director_dict(scene: Scene) -> dict[str, Any]:
    from ..director_timeline import migrate_scene_to_director, parse_director_timeline

    if scene.director_json and scene.director_json.strip():
        director = parse_director_timeline(
            scene.director_json,
            fallback_duration=scene.duration_sec,
            fallback_prompt=scene.prompt,
        )
    else:
        director = migrate_scene_to_director(
            duration_sec=scene.duration_sec,
            prompt=scene.prompt,
            start_asset_id=scene.start_asset_id,
            middle_asset_id=scene.middle_asset_id,
            end_asset_id=scene.end_asset_id,
            audio_asset_id=scene.audio_asset_id,
            lipsync_tracks_json=scene.lipsync_tracks_json,
        )
    return director.model_dump(mode="json")


def _apply_mode_nudge(messages: list[dict[str, str]], mode: str) -> None:
    if not messages:
        return
    last = messages[-1]
    text = last.get("content", "")
    if mode == "setup":
        last["content"] = (
            "Build a complete SCENE_SETUP for the selected scene in Adept UI Video Studio. "
            "Use only asset tags/ids listed in context. Fill engine, duration, media_mode, "
            "global_prompt (look/feel), motion prompt or prompt_segments, and image_slots when "
            "image assets exist. Place audio_ref/sfx only if audio assets exist. "
            "Write a short plan for the user, then end with a ```scene_setup JSON fence.\n\n"
            "User request:\n" + text
        )
    elif mode == "prompt":
        last["content"] = (
            "Write or improve a ready-to-paste video prompt for the selected scene. "
            "Put the final prompt in a ```prompt fenced block. "
            "Also give a 1-2 sentence tip.\n\nUser request:\n" + text
        )
    elif mode == "guide":
        last["content"] = (
            "Explain how to do this in Adept UI Video Studio with numbered UI steps.\n\n" + text
        )
    elif mode == "chat":
        lowered = text.lower()
        if any(
            k in lowered
            for k in (
                "build the scene",
                "build a scene",
                "set up the scene",
                "setup the scene",
                "set up this scene",
                "configure the scene",
                "create the scene",
                "fill the scene",
                "assemble the scene",
                "scene setup",
            )
        ):
            last["content"] = (
                "Build a complete SCENE_SETUP for the selected scene. "
                "Short plan + ```scene_setup JSON fence. Use only listed assets.\n\n"
                "User request:\n" + text
            )


def _build_system_message(context: str) -> dict[str, str]:
    system = assistant_module.SYSTEM_PROMPT
    if context.strip():
        system += "\n\nCurrent studio context:\n" + context.strip()
    return {"role": "system", "content": system}


async def _prepare_chat_request(
    db: Session,
    *,
    messages: list[dict[str, str]],
    project_id: str | None,
    scene_id: str | None,
    mode: str,
    model: str | None,
    provider_id: str | None,
    request_id: str | None,
) -> tuple[CoDirectorProvider, ChatRequest, ContextManifest]:
    request_id = request_id or new_request_id()
    context = ""
    if project_id:
        project = db.get(Project, project_id)
        if not project:
            raise CoDirectorError(
                PROJECT_NOT_FOUND,
                "Project not found.",
                details={"projectId": project_id},
                recoverable=False,
                recommended_action="none",
            )
        project_payload = _build_project_payload(db, project_id)
        director_payload = None
        if scene_id:
            scene = db.get(Scene, scene_id)
            if scene and scene.project_id == project_id:
                director_payload = _scene_director_dict(scene)
        context = assistant_module.build_context_block(project_payload, scene_id, director_payload)
        learn = parse_learning(
            getattr(project, "learning_json", "") or "",
            getattr(project, "learning_enabled_json", "") or "",
        )
        block = learning_context_block(learn)
        if block:
            context = (context or "") + "\n\n" + block

    # Bible excerpt is additive and independently bounded — projects without a Bible (or
    # without project_id at all) see byte-for-byte the same context as before M2.1.
    bible_excerpt, context_manifest = ProjectContextService.build(db, project_id)
    if bible_excerpt:
        context = (context or "") + "\n\n" + bible_excerpt

    chat_messages = [
        {"role": m.get("role", "user"), "content": m.get("content", "")}
        for m in messages
        if m.get("role") != "system"
    ]
    if not chat_messages or not any((m.get("content") or "").strip() for m in chat_messages):
        raise CoDirectorError(
            VALIDATION_ERROR,
            "At least one non-empty message is required.",
            recoverable=False,
            recommended_action="none",
        )
    _apply_mode_nudge(chat_messages, mode)

    full_messages = [_build_system_message(context), *chat_messages]
    provider = get_provider(provider_id)
    chat_request = ChatRequest(
        request_id=request_id,
        messages=full_messages,
        model_id=model,
        project_context=context,
        mode=mode,
    )
    return provider, chat_request, context_manifest


async def run_cancellable(request_id: str, coro: Any) -> Any:
    task: "asyncio.Task[Any]" = asyncio.ensure_future(coro)
    _active_tasks[request_id] = task
    try:
        return await task
    except asyncio.CancelledError as exc:
        raise CoDirectorError(
            REQUEST_CANCELLED,
            "The request was cancelled.",
            details={"requestId": request_id},
            recommended_action="retry",
        ) from exc
    finally:
        _active_tasks.pop(request_id, None)


def request_cancel(request_id: str) -> dict[str, Any]:
    _cancelled.add(request_id)
    task = _active_tasks.get(request_id)
    task_cancelled = False
    if task is not None and not task.done():
        task.cancel()
        task_cancelled = True
    return {"requestId": request_id, "cancelled": True, "taskCancelled": task_cancelled}


def is_cancelled(request_id: str) -> bool:
    return request_id in _cancelled


def clear_cancelled(request_id: str) -> None:
    _cancelled.discard(request_id)


def _create_proposal_from_reply(
    db: Session, *, project_id: str | None, request_id: str, reply: str
) -> tuple[str, ProposalOut | None, CoDirectorError | None]:
    """Extract a ```proposal fence (if any) and persist it. Never mutates the Bible directly.

    Returns `(display_text, proposal_or_none, structured_error_or_none)`. A malformed fence
    yields a non-fatal `STRUCTURED_OUTPUT_INVALID` error — the chat turn still completes.
    """

    extraction = extract_proposal_block(reply)
    if extraction is None:
        return reply, None, None
    display = strip_proposal_blocks(reply)
    if extraction.error or extraction.mutations is None:
        return display, None, CoDirectorError(
            STRUCTURED_OUTPUT_INVALID,
            extraction.error or "Co-Director's proposal could not be understood.",
            details={"requestId": request_id},
            recoverable=True,
            recommended_action="retry",
        )
    if not project_id:
        return display, None, None
    proposal = ProposalService.create_proposal(
        db,
        project_id=project_id,
        proposal_type=extraction.proposal_type,
        title=extraction.title,
        summary=extraction.summary,
        payload=extraction.mutations,
        request_id=request_id,
        created_by="assistant",
    )
    return display, proposal, None


async def chat_for_project(
    db: Session,
    *,
    messages: list[dict[str, str]],
    project_id: str | None,
    scene_id: str | None,
    mode: str,
    model: str | None,
    provider_id: str | None = None,
    request_id: str | None = None,
) -> tuple[ChatResult, SceneSetupProposal | None, str | None, ProposalOut | None, ContextManifest]:
    provider, chat_request, manifest = await _prepare_chat_request(
        db,
        messages=messages,
        project_id=project_id,
        scene_id=scene_id,
        mode=mode,
        model=model,
        provider_id=provider_id,
        request_id=request_id,
    )
    result = await run_cancellable(chat_request.request_id, provider.generate(chat_request))
    setup = assistant_module.extract_scene_setup(result.reply)
    display = assistant_module.strip_scene_setup_blocks(result.reply) if setup else result.reply
    suggested = None if setup else assistant_module.extract_suggested_prompt(result.reply)
    display, proposal, structured_error = _create_proposal_from_reply(
        db, project_id=project_id, request_id=chat_request.request_id, reply=display or result.reply
    )
    if structured_error is not None:
        raise structured_error
    result.reply = display or result.reply
    return result, setup, suggested, proposal, manifest


async def stream_for_project(
    db: Session,
    *,
    messages: list[dict[str, str]],
    project_id: str | None,
    scene_id: str | None,
    mode: str,
    model: str | None,
    provider_id: str | None = None,
    request_id: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    provider, chat_request, manifest = await _prepare_chat_request(
        db,
        messages=messages,
        project_id=project_id,
        scene_id=scene_id,
        mode=mode,
        model=model,
        provider_id=provider_id,
        request_id=request_id,
    )
    if manifest.bibleVersionId:
        yield {"type": "context_manifest", "requestId": chat_request.request_id, "manifest": manifest.model_dump(mode="json")}

    async for event in provider.stream(chat_request):
        if event.get("type") == "completed":
            content = str(event.get("content") or "")
            setup = assistant_module.extract_scene_setup(content)
            display = assistant_module.strip_scene_setup_blocks(content) if setup else content
            suggested = None if setup else assistant_module.extract_suggested_prompt(content)
            display, proposal, structured_error = _create_proposal_from_reply(
                db, project_id=project_id, request_id=chat_request.request_id, reply=display or content
            )
            event = {
                **event,
                "content": display or content,
                "sceneSetup": setup.model_dump() if setup else None,
                "suggestedPrompt": suggested,
            }
            yield event
            if proposal is not None:
                yield {
                    "type": "proposal_created",
                    "requestId": chat_request.request_id,
                    "proposal": proposal.model_dump(mode="json"),
                }
            if structured_error is not None:
                yield {
                    "type": "error",
                    "requestId": chat_request.request_id,
                    "error": structured_error.to_dict(),
                }
            continue
        yield event


# --------------------------------------------------------------------------
# Conversation persistence (project-scoped)
# --------------------------------------------------------------------------


def _conversation_to_dict(row: CoDirectorConversation) -> dict[str, Any]:
    try:
        messages = json.loads(row.messages_json or "[]")
    except Exception:
        messages = []
    return {
        "projectId": row.project_id,
        "messages": messages,
        "model": row.model_id,
        "providerId": row.provider_id,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def get_conversation(db: Session, project_id: str) -> dict[str, Any] | None:
    row = db.get(CoDirectorConversation, project_id)
    if not row:
        return None
    return _conversation_to_dict(row)


def save_conversation(
    db: Session,
    project_id: str,
    *,
    messages: list[dict[str, Any]],
    model: str | None,
    provider_id: str | None,
) -> dict[str, Any]:
    row = db.get(CoDirectorConversation, project_id)
    if not row:
        row = CoDirectorConversation(project_id=project_id)
        db.add(row)
    row.messages_json = json.dumps(messages)
    row.model_id = model
    row.provider_id = provider_id
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return _conversation_to_dict(row)


def delete_conversation(db: Session, project_id: str) -> bool:
    row = db.get(CoDirectorConversation, project_id)
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True
