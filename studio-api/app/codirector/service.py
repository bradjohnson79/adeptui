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
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator, Optional

from sqlalchemy.orm import Session

from .. import assistant as assistant_module
from ..assistant import SceneSetupProposal
from ..config import settings
from ..db import CoDirectorConversation, Project, Scene
from ..feature_flags import feature_flags
from ..learning import adaptive_lessons_block, learning_context_block, parse_learning
from . import config_store
from .bible.context import ProjectContextService
from .bible.proposals import ProposalService
from .bible.schemas import ContextManifest, ProposalOut
from .errors import (
    CAPABILITY_NOT_CONFIGURED,
    CAPABILITY_UNAVAILABLE,
    PROJECT_NOT_FOUND,
    REQUEST_CANCELLED,
    STRUCTURED_OUTPUT_INVALID,
    TOOL_LOOP_LIMIT_REACHED,
    VALIDATION_ERROR,
    CoDirectorError,
)
from .providers.base import ChatRequest, ChatResult, CoDirectorProvider, ProviderHealthResult, ProviderModel
from .providers.mock import MockCoDirectorProvider
from .providers.ollama import OllamaProvider
from .structured_output import ToolCallRequest, parse_structured_reply
from .tools import registry as tool_registry
from .tools.capabilities import CapabilityAdapter
from .tools.definitions import ToolInvocationOut
from .tools.execution import ToolExecutionService
from .tools.sanitize import render_result_for_model

try:
    from .intelligence.intent import classify_intent
    from .intelligence.service import IntelligenceService
except ImportError:  # pragma: no cover - defensive during partial installs
    classify_intent = None  # type: ignore[assignment]
    IntelligenceService = None  # type: ignore[assignment,misc]

PROVIDER_IDS: list[str] = ["ollama", "mock"]

# One read tool per turn, one follow-up completion. The bound exists so a model that likes
# calling tools can't turn a single user message into an unbounded chain of local work.
TOOL_LOOP_LIMIT = 1

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
        health = await provider.health()
    except CoDirectorError as err:
        health = ProviderHealthResult(
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
    health.intelligence_enabled = bool(feature_flags.codirector_intelligence_v2)
    health.vision_validation_enabled = bool(feature_flags.vision_validation_v1)
    health.timeline_references_enabled = bool(feature_flags.timeline_references_v1)
    health.production_executive_enabled = bool(feature_flags.production_executive_v1)
    health.production_intelligence_enabled = bool(feature_flags.codirector_production_intelligence_v1)
    health.adaptive_learning_enabled = bool(feature_flags.codirector_adaptive_learning_v1)
    return health


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


def _tool_instructions() -> str:
    """Static catalog block describing the tool registry to the model.

    Built from the registry alone — no capability probes run here, so composing a chat turn
    costs nothing extra. A model asking for a tool whose capability is missing gets a
    `capability_blocked` event at execution time, which is the honest answer anyway.
    """

    read_lines = []
    mutate_lines = []
    for definition in tool_registry.all_definitions():
        params = ", ".join(
            f"{p.name}{'' if p.required else '?'}:{p.type}" for p in definition.parameters
        )
        line = f"- {definition.tool_id}({params}) — {definition.description}"
        (read_lines if definition.kind == "read" else mutate_lines).append(line)

    return (
        "Co-Director tools:\n\n"
        "You may look things up, and you may propose changes. You can never apply a change "
        "yourself — a proposed change is shown to the user for approval and the server applies "
        "it only after they approve.\n\n"
        "To use a tool, end your reply with a ```tool fenced JSON block:\n"
        '```tool\n{"responseType": "read_tool_call", "toolId": "list_scenes", "arguments": {}}\n```\n'
        "Use responseType \"mutation_proposal\" for a tool that changes project data. Request at "
        "most ONE tool per reply, and only when you actually need it — answer directly when you "
        "already know enough. After a read tool returns, answer the user in plain prose without "
        "requesting another tool.\n\n"
        "Read tools (run immediately):\n" + "\n".join(read_lines) + "\n\n"
        "Change tools (require the user's approval):\n" + "\n".join(mutate_lines)
    )


def _build_system_message(context: str, *, include_tools: bool = False) -> dict[str, str]:
    system = assistant_module.SYSTEM_PROMPT
    if context.strip():
        system += "\n\nCurrent studio context:\n" + context.strip()
    if include_tools:
        system += "\n\n" + _tool_instructions()
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
        if feature_flags.codirector_adaptive_learning_v1:
            try:
                from .m212.lessons import LessonStore

                active = LessonStore.list_active_for_context(db, project_id=project_id, limit=40)
                a_block = adaptive_lessons_block(active)
                if a_block:
                    context = (context or "") + "\n\n" + a_block
            except Exception:
                pass

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

    # Tools are project-scoped: without a bound project there is nothing for them to read or
    # change, so the catalog is omitted and the prompt is identical to M2.1's.
    full_messages = [_build_system_message(context, include_tools=bool(project_id)), *chat_messages]
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


# --------------------------------------------------------------------------
# M2.2: bounded tool turns. Shared by the streaming and non-streaming chat paths so both agree
# on the loop bound, the event order, and what counts as a fatal failure (nothing does — a tool
# problem is always surfaced alongside a completed reply, never instead of one).
# --------------------------------------------------------------------------


@dataclass
class _ToolTurnOutcome:
    invocation: Optional[ToolInvocationOut] = None
    error: Optional[CoDirectorError] = None
    follow_up_prompt: Optional[str] = None


@dataclass
class _StructuredOutcome:
    """The result of interpreting one provider reply, ready to emit or return."""

    display: str = ""
    bible_proposal: Optional[ProposalOut] = None
    tool_proposal: Optional[ProposalOut] = None
    invocations: list[ToolInvocationOut] = field(default_factory=list)
    errors: list[CoDirectorError] = field(default_factory=list)
    follow_up_prompt: Optional[str] = None
    response_type: str = "message"


def _capability_error(err: CoDirectorError) -> bool:
    return err.code in (CAPABILITY_NOT_CONFIGURED, CAPABILITY_UNAVAILABLE)


async def _run_read_tool(
    db: Session,
    *,
    project_id: str,
    scene_id: Optional[str],
    request_id: str,
    tool_call: ToolCallRequest,
    outcome: _ToolTurnOutcome,
) -> AsyncIterator[dict[str, Any]]:
    """Execute one read tool, yielding lifecycle events as it goes."""

    yield {
        "type": "tool_requested",
        "requestId": request_id,
        "toolId": tool_call.tool_id,
        "kind": "read",
    }
    definition = tool_registry.find(tool_call.tool_id)
    yield {
        "type": "tool_started",
        "requestId": request_id,
        "toolId": tool_call.tool_id,
        "title": definition.title if definition else tool_call.tool_id,
    }

    try:
        invocation = await ToolExecutionService.execute_read(
            db,
            project_id=project_id,
            tool_id=tool_call.tool_id,
            arguments=tool_call.arguments,
            scene_id=scene_id,
            request_id=request_id,
        )
    except CoDirectorError as err:
        outcome.error = err
        if _capability_error(err):
            yield {
                "type": "capability_blocked",
                "requestId": request_id,
                "toolId": tool_call.tool_id,
                "capability": err.details.get("capability"),
                "error": err.to_dict(),
            }
        else:
            yield {
                "type": "tool_failed",
                "requestId": request_id,
                "toolId": tool_call.tool_id,
                "error": err.to_dict(),
            }
        outcome.follow_up_prompt = (
            f"The `{tool_call.tool_id}` tool could not run: {err.message} "
            "Tell the user plainly what you cannot check right now, and help them with what you "
            "do know. Do not request another tool."
        )
        return

    outcome.invocation = invocation
    if invocation.resultTruncated:
        yield {
            "type": "tool_result_truncated",
            "requestId": request_id,
            "toolId": tool_call.tool_id,
            "invocationId": invocation.id,
        }
    yield {
        "type": "tool_completed",
        "requestId": request_id,
        "toolId": tool_call.tool_id,
        "invocation": invocation.model_dump(mode="json"),
    }
    outcome.follow_up_prompt = (
        render_result_for_model(tool_call.tool_id, invocation.result or {}, truncated=invocation.resultTruncated)
        + "\n\nAnswer the user's original question using this result, in plain prose. "
        "Do not request another tool."
    )


async def _propose_tool_call(
    db: Session,
    *,
    project_id: str,
    scene_id: Optional[str],
    request_id: str,
    tool_call: ToolCallRequest,
    outcome: _StructuredOutcome,
) -> AsyncIterator[dict[str, Any]]:
    """Turn a mutating tool request into a durable proposal. Nothing is applied."""

    yield {
        "type": "tool_requested",
        "requestId": request_id,
        "toolId": tool_call.tool_id,
        "kind": "mutating",
    }
    try:
        proposal = await ToolExecutionService.propose(
            db,
            project_id=project_id,
            tool_id=tool_call.tool_id,
            arguments=tool_call.arguments,
            scene_id=scene_id,
            request_id=request_id,
            created_by="assistant",
        )
    except CoDirectorError as err:
        outcome.errors.append(err)
        if _capability_error(err):
            yield {
                "type": "capability_blocked",
                "requestId": request_id,
                "toolId": tool_call.tool_id,
                "capability": err.details.get("capability"),
                "error": err.to_dict(),
            }
        else:
            yield {
                "type": "tool_failed",
                "requestId": request_id,
                "toolId": tool_call.tool_id,
                "error": err.to_dict(),
            }
        return

    outcome.tool_proposal = proposal
    yield {
        "type": "tool_proposal_created",
        "requestId": request_id,
        "toolId": tool_call.tool_id,
        "proposal": proposal.model_dump(mode="json"),
    }


async def _interpret_reply(
    db: Session,
    *,
    project_id: Optional[str],
    scene_id: Optional[str],
    request_id: str,
    reply: str,
    tools_used: int,
    outcome: _StructuredOutcome,
) -> AsyncIterator[dict[str, Any]]:
    """Classify a reply and act on it, yielding any SSE events the action produces.

    Mutates `outcome` in place — the caller needs the display text and any proposal regardless of
    which branch ran, and an async generator can't return a value.
    """

    structured = parse_structured_reply(reply)
    outcome.display = structured.display or reply
    outcome.response_type = structured.response_type

    if structured.error:
        outcome.errors.append(
            CoDirectorError(
                STRUCTURED_OUTPUT_INVALID,
                structured.error,
                details={"requestId": request_id},
                recoverable=True,
                recommended_action="retry",
            )
        )
        return

    if structured.tool_call is None:
        if structured.bible_proposal is not None and project_id:
            extraction = structured.bible_proposal
            outcome.bible_proposal = ProposalService.create_proposal(
                db,
                project_id=project_id,
                proposal_type=extraction.proposal_type,
                title=extraction.title,
                summary=extraction.summary,
                payload=extraction.mutations,  # type: ignore[arg-type]
                request_id=request_id,
                created_by="assistant",
            )
        return

    if not project_id:
        outcome.errors.append(
            CoDirectorError(
                STRUCTURED_OUTPUT_INVALID,
                "Co-Director asked to use a project tool, but no project is open.",
                details={"requestId": request_id, "toolId": structured.tool_call.tool_id},
                recoverable=True,
                recommended_action="none",
            )
        )
        return

    if structured.response_type == "mutation_proposal":
        async for event in _propose_tool_call(
            db,
            project_id=project_id,
            scene_id=scene_id,
            request_id=request_id,
            tool_call=structured.tool_call,
            outcome=outcome,
        ):
            yield event
        return

    # read_tool_call
    if tools_used >= TOOL_LOOP_LIMIT:
        err = CoDirectorError(
            TOOL_LOOP_LIMIT_REACHED,
            "Co-Director tried to look something else up after already using a tool this turn.",
            details={"requestId": request_id, "toolId": structured.tool_call.tool_id, "limit": TOOL_LOOP_LIMIT},
            recoverable=True,
            recommended_action="retry",
        )
        outcome.errors.append(err)
        return

    tool_outcome = _ToolTurnOutcome()
    async for event in _run_read_tool(
        db,
        project_id=project_id,
        scene_id=scene_id,
        request_id=request_id,
        tool_call=structured.tool_call,
        outcome=tool_outcome,
    ):
        yield event
    if tool_outcome.invocation is not None:
        outcome.invocations.append(tool_outcome.invocation)
    if tool_outcome.error is not None:
        outcome.errors.append(tool_outcome.error)
    outcome.follow_up_prompt = tool_outcome.follow_up_prompt


def _follow_up_request(base: ChatRequest, *, assistant_reply: str, tool_prompt: str) -> ChatRequest:
    """Build the single permitted follow-up turn: same system context, tool result appended."""

    messages = [
        *base.messages,
        {"role": "assistant", "content": assistant_reply or "(requesting a lookup)"},
        {"role": "user", "content": tool_prompt},
    ]
    return ChatRequest(
        request_id=base.request_id,
        messages=messages,
        model_id=base.model_id,
        project_context=base.project_context,
        temperature=base.temperature,
        mode=base.mode,
    )


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
) -> tuple[
    ChatResult,
    SceneSetupProposal | None,
    str | None,
    ProposalOut | None,
    ContextManifest,
    list[ToolInvocationOut],
]:
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

    invocations: list[ToolInvocationOut] = []
    proposal: ProposalOut | None = None
    fatal_error: CoDirectorError | None = None
    tools_used = 0

    for _ in range(TOOL_LOOP_LIMIT + 1):
        setup = assistant_module.extract_scene_setup(result.reply)
        display = assistant_module.strip_scene_setup_blocks(result.reply) if setup else result.reply
        suggested = None if setup else assistant_module.extract_suggested_prompt(result.reply)

        outcome = _StructuredOutcome()
        async for _event in _interpret_reply(
            db,
            project_id=project_id,
            scene_id=scene_id,
            request_id=chat_request.request_id,
            reply=display or result.reply,
            tools_used=tools_used,
            outcome=outcome,
        ):
            pass  # the non-streaming path has no channel for lifecycle events

        invocations.extend(outcome.invocations)
        proposal = outcome.bible_proposal or outcome.tool_proposal or proposal
        # Only a structured-output failure is fatal on the non-streaming path, matching M2.1: a
        # tool that couldn't run is reported through the follow-up reply, not as an HTTP error.
        fatal_error = next(
            (e for e in outcome.errors if e.code in (STRUCTURED_OUTPUT_INVALID, TOOL_LOOP_LIMIT_REACHED)),
            None,
        )
        result.reply = outcome.display or result.reply

        if outcome.follow_up_prompt is None:
            if fatal_error is not None:
                raise fatal_error
            return result, setup, suggested, proposal, manifest, invocations

        tools_used += 1
        follow_up = _follow_up_request(
            chat_request, assistant_reply=outcome.display, tool_prompt=outcome.follow_up_prompt
        )
        result = await run_cancellable(follow_up.request_id, provider.generate(follow_up))

    if fatal_error is not None:
        raise fatal_error
    return result, None, None, proposal, manifest, invocations


def _last_user_message(messages: list[dict[str, str]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return (message.get("content") or "").strip()
    return ""


def _intelligence_enabled_for_turn(
    *,
    project_id: str | None,
    messages: list[dict[str, str]],
    mode: str,
) -> bool:
    if not feature_flags.codirector_intelligence_v2:
        return False
    if not project_id or IntelligenceService is None or classify_intent is None:
        return False
    text = _last_user_message(messages)
    if not text:
        return False
    intent = classify_intent(text, mode=mode)
    service = IntelligenceService()
    if intent.isSimpleQuestion and intent.primaryIntent == "answer_question":
        return False
    if intent.primaryIntent == "create_storyboard":
        return True
    return service.should_use_intelligence(intent)


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

    if _intelligence_enabled_for_turn(
        project_id=project_id,
        messages=messages,
        mode=mode,
    ):
        assert IntelligenceService is not None
        intelligence = IntelligenceService()
        async for event in intelligence.stream_intelligence(
            db,
            project_id=project_id or "",
            user_message=_last_user_message(messages),
            scene_id=scene_id,
            mode=mode,
            provider=provider,
            model_id=model,
            request_id=chat_request.request_id,
        ):
            yield event
        return

    active_request = chat_request
    tools_used = 0

    while True:
        follow_up_prompt: Optional[str] = None
        follow_up_reply = ""

        async for event in provider.stream(active_request):
            if event.get("type") != "completed":
                yield event
                continue

            content = str(event.get("content") or "")
            setup = assistant_module.extract_scene_setup(content)
            display = assistant_module.strip_scene_setup_blocks(content) if setup else content
            suggested = None if setup else assistant_module.extract_suggested_prompt(content)

            outcome = _StructuredOutcome()
            async for tool_event in _interpret_reply(
                db,
                project_id=project_id,
                scene_id=scene_id,
                request_id=chat_request.request_id,
                reply=display or content,
                tools_used=tools_used,
                outcome=outcome,
            ):
                yield tool_event

            if outcome.follow_up_prompt is not None:
                # The reply was a tool request, not an answer. Its `completed` is withheld so the
                # transcript only ever shows the answer that follows; the FE has already cleared
                # the in-flight bubble on `tool_requested`. Any error here was already reported as
                # `tool_failed` / `capability_blocked`, so it is not repeated as a generic `error`
                # — the client would read that as a failed turn when the turn is still going.
                follow_up_prompt = outcome.follow_up_prompt
                follow_up_reply = outcome.display
                continue

            yield {
                **event,
                "content": outcome.display or content,
                "sceneSetup": setup.model_dump() if setup else None,
                "suggestedPrompt": suggested,
            }
            if outcome.bible_proposal is not None:
                yield {
                    "type": "proposal_created",
                    "requestId": chat_request.request_id,
                    "proposal": outcome.bible_proposal.model_dump(mode="json"),
                }
            for err in outcome.errors:
                yield {"type": "error", "requestId": chat_request.request_id, "error": err.to_dict()}

        if follow_up_prompt is None:
            return
        tools_used += 1
        active_request = _follow_up_request(
            active_request, assistant_reply=follow_up_reply, tool_prompt=follow_up_prompt
        )


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
