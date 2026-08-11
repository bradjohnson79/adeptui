"""Co-Director gateway: provider selection, chat composition, cancellation, persistence.

Browser never talks to Ollama directly — everything routes through this gateway so
transport failures can be classified into structured `CoDirectorError`s instead of a
bare `TypeError: Failed to fetch` reaching the chat UI.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator, Iterable, Optional

from sqlalchemy.orm import Session

from .. import assistant as assistant_module
from ..assistant import SceneSetupProposal
from ..config import settings
from ..db import CoDirectorConversation, CoDirectorConversationEvent, Project, Scene
from .context_enrichment import (
    attachment_context_block,
    compact_wiki_context,
    content_tab_hint_block,
    execution_result_context_block,
)
from ..feature_flags import feature_flags
from ..learning import adaptive_lessons_block, learning_context_block, parse_learning
from . import config_store
from .bible.context import ProjectContextService
from .bible.proposals import ProposalService
from .bible.schemas import ContextManifest, ProposalOut
from .conversation_events import (
    AppendBatchResult,
    EventInput,
    append_events,
    conversation_to_dict as events_conversation_to_dict,
    current_revision,
    delete_all_events,
    fold_events,
)
from .errors import (
    CAPABILITY_NOT_CONFIGURED,
    CAPABILITY_UNAVAILABLE,
    PROJECT_NOT_FOUND,
    PROJECT_REQUIRED,
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
from .operator import has_operator_ack, register_operator_request
from .operator.contracts import OPERATOR_TOOLS

try:
    from .intelligence.intent import classify_intent
    from .intelligence.service import IntelligenceService
except ImportError:  # pragma: no cover - defensive during partial installs
    classify_intent = None  # type: ignore[assignment]
    IntelligenceService = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

PROVIDER_IDS: list[str] = ["ollama", "mock"]

# Up to three consecutive read tools per turn, plus one follow-up completion. The bound exists so
# a model that likes calling tools can't turn a single user message into an unbounded chain of
# local work, while still permitting legitimate read-before-write grounding sequences such as
# "list scenes → get scene X → list bible entities" before a single proposal. A mutation
# proposal always terminates the loop (see `_propose_tool_call`); only read tools may chain.
TOOL_LOOP_LIMIT = 3

_active_tasks: dict[str, "asyncio.Task[Any]"] = {}
_cancelled: set[str] = set()


def new_request_id() -> str:
    return uuid.uuid4().hex


def e2e_enabled() -> bool:
    return os.environ.get("STUDIO_E2E", "").strip() in ("1", "true", "TRUE", "yes", "YES")


def _mock_provider_allowed() -> bool:
    """Config-enforced mock provider guard (c2/D17).

    The mock Co-Director provider is a deterministic test/offline double. It is
    never selectable in a production run. Selection requires:

      1. `STUDIO_E2E` env flag set (test/E2E run), AND
      2. NOT a production deployment — refused when `ADEPT_ENV=production`
         (a hard config marker independent of `STUDIO_E2E`), unless an explicit
         allow-mock signal is set (persisted config `allowMockProvider=true` or
         `ADEPT_ALLOW_MOCK_PROVIDER` env) for a deliberate operator opt-in.

    This means a stray `STUDIO_E2E` in a production shell can no longer surface
    the mock provider: `ADEPT_ENV=production` blocks it regardless. Tests do not
    set `ADEPT_ENV=production`, so the existing E2E test contract is preserved.
    """

    if not e2e_enabled():
        return False
    adept_env = os.environ.get("ADEPT_ENV", "").strip().lower()
    production = adept_env == "production"
    if not production:
        return True
    # Production: block unless an explicit operator opt-in is present.
    try:
        cfg = config_store.load_config()
    except Exception:  # noqa: BLE001
        cfg = {}
    if bool(cfg.get("allowMockProvider")):
        return True
    return os.environ.get("ADEPT_ALLOW_MOCK_PROVIDER", "").strip() in (
        "1",
        "true",
        "TRUE",
        "yes",
        "YES",
    )


def _is_production_env() -> bool:
    return os.environ.get("ADEPT_ENV", "").strip().lower() == "production"


def active_provider_id() -> str:
    """ADEPT_CODIRECTOR_PROVIDER wins; otherwise E2E defaults to the deterministic mock.

    The mock provider is a test/offline double only — it is never selectable in a
    production run even if `ADEPT_CODIRECTOR_PROVIDER=mock` is set by mistake, because
    that would silently mask a broken local-model deployment for real users. The
    guard is config-enforced (see `_mock_provider_allowed`): it requires both the
    `STUDIO_E2E` env flag and an explicit allow-mock config/env signal.
    """
    override = os.environ.get("ADEPT_CODIRECTOR_PROVIDER", "").strip().lower()
    if override == "mock" and not _mock_provider_allowed():
        # c2/D17: log the fallback so a misconfigured production shell is visible.
        logger.warning(
            "Co-Director mock provider requested but refused (STUDIO_E2E=%s, ADEPT_ENV=%s); "
            "falling back to 'ollama'. Set ADEPT_ENV!=production or an explicit allow-mock "
            "signal to enable the mock provider.",
            os.environ.get("STUDIO_E2E", ""),
            os.environ.get("ADEPT_ENV", ""),
        )
        return "ollama"
    if override in PROVIDER_IDS:
        return override
    if _mock_provider_allowed():
        return "mock"
    return "ollama"


def list_provider_ids() -> list[str]:
    """Providers selectable via the UI/API — mock is hidden unless explicitly allowed."""
    if _mock_provider_allowed():
        return list(PROVIDER_IDS)
    return [p for p in PROVIDER_IDS if p != "mock"]


def build_provider(provider_id: str) -> CoDirectorProvider:
    if provider_id == "mock":
        if not _mock_provider_allowed():
            raise CoDirectorError(
                "PROVIDER_NOT_CONFIGURED",
                "The mock Co-Director provider is only available in E2E/test runs with an "
                "explicit allow-mock signal (config `allowMockProvider=true` or "
                "ADEPT_ALLOW_MOCK_PROVIDER env) and STUDIO_E2E set.",
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
    health.unified_experience_enabled = bool(feature_flags.codirector_unified_experience_v1)
    health.virtual_environment_studio_enabled = bool(feature_flags.virtual_environment_studio_v1)
    health.audio_production_enabled = bool(feature_flags.audio_production_v1)
    health.director_timeline_enabled = bool(feature_flags.director_timeline_v1)
    if pid == "mock" or health.provider_id == "mock":
        health.test_only = True
        health.honesty = health.honesty or "mocked"
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


# c2/D7: general premature tool-success claim detection. The wiki-specific detector
# below (service.py ~2000) handles "added/updated/saved to the wiki"; this regex catches
# broader mutation-success claims ("I've added/created/updated/deleted/saved/applied …")
# that are NOT backed by an executed mutating tool. The foundation stream path never
# executes mutating tools, so any such claim there is a false-success claim. The legacy
# stream path passes `mutating_tool_executed` so a claim backed by a real tool result is
# not flagged.
_PREMATURE_TOOL_SUCCESS_RE = re.compile(
    r"\b(?:i(?:'|’|ve| have)?\s*(?:added|created|updated|deleted|removed|saved|applied|generated)\b"
    r"|i(?:'|’|ve)?\s*\w+\s*(?:added|created|updated|deleted|saved)\b"
    r"|(?:added|created|updated|deleted|saved|applied)\s+(?:the|a|an|your|this)\s+"
    r"(?:scene|character|asset|plan|bible|canon|continuity|reference|voice|batch|clip|step))\b",
    re.IGNORECASE,
)
_WIKI_PREMATURE_RE = re.compile(
    r"\b(?:added to (?:the )?wiki|updated (?:the )?wiki|saved to (?:the )?wiki)\b",
    re.IGNORECASE,
)


def _detect_premature_tool_success_claim(reply: str, *, mutating_tool_executed: bool) -> tuple[bool, str | None]:
    """Return (is_premature, matched_phrase) for a streamed reply.

    A claim is premature when the reply asserts a mutation completed
    (`_PREMATURE_TOOL_SUCCESS_RE`) but no mutating tool executed this turn. Wiki
    claims are left to the wiki-specific detector and excluded here so the two
    corrections do not both fire for the same text.
    """

    if mutating_tool_executed or not reply:
        return False, None
    m = _PREMATURE_TOOL_SUCCESS_RE.search(reply)
    if not m:
        return False, None
    # Skip wiki claims — handled by wiki_status.prematureClaim.
    if _WIKI_PREMATURE_RE.search(reply):
        return False, None
    return True, m.group(0)


# c2/D18: verified-operator grounding (Co-Director 2.0 Mission A, contract §1.6).
# An operator success claim ("opened X" / "open X" / "focus the timeline") is only
# grounded when an `operator_acknowledged` event exists for the request id that
# produced it. No ack → the reply is grounded to "requested, not confirmed".
# Conservative + additive: it only fires when an operator tool executed this turn
# AND its destination phrase appears AND no ack exists for the turn's request id.
_OPERATOR_PREMATURE_RE: dict[str, re.Pattern] = {
    "audio.open_studio": re.compile(r"\bopen(?:ed|ing)? (?:the )?audio studio\b", re.IGNORECASE),
    "voice_performance.open_workspace": re.compile(
        r"\bopen(?:ed|ing)? (?:the )?(?:voice studio|voice workspace)\b", re.IGNORECASE
    ),
    "timeline.focus_ui": re.compile(r"\bfocus(?:ed|ing)? (?:the )?timeline\b", re.IGNORECASE),
    "character_creator.open_voice_creator": re.compile(
        r"\bopen(?:ed|ing)? (?:the )?voice creator\b", re.IGNORECASE
    ),
    "workspace.open_scriptwriter": re.compile(
        r"\bopen(?:ed|ing)? (?:the )?script writer\b", re.IGNORECASE
    ),
}


def _operator_premature_success_claim(
    reply: str,
    *,
    executed_operator_tool_ids: Iterable[str],
    has_ack: bool,
) -> tuple[bool, str | None]:
    """Return (is_premature, matched_phrase) for an operator action claim.

    Fires only when an executed operator tool has NO ack and its destination
    phrase appears in the reply. ``has_ack`` is True only when every executed
    operator tool this turn was acknowledged, so a single unacknowledged
    operator request keeps the gate active.
    """
    if has_ack or not reply:
        return False, None
    for tool_id in executed_operator_tool_ids:
        pattern = _OPERATOR_PREMATURE_RE.get(tool_id)
        if pattern is None:
            continue
        m = pattern.search(reply)
        if m:
            return True, m.group(0)
    return False, None


# Phase 5 §5U — structured payload leakage guard:
# The following must NEVER appear in a creator-facing response:
# - Raw tool fences (```tool ... ```)
# - JSON tool/proposal payloads ({"responseType":"mutation_proposal", ...})
# - [mock] tags
# - Python tracebacks
# - Internal error codes without human-readable messages
# These are tested in Phase 5 E2E scenario P5-E2E-14.

_SCRIPT_SAVED_RE = re.compile(
    r"\byour (?:script|screenplay|text|writing) has been saved\b|\bscript was saved\b",
    re.IGNORECASE,
)


def _detect_premature_script_save_claim(reply: str, *, script_saved: bool) -> tuple[bool, str | None]:
    if script_saved or not reply:
        return False, None
    m = _SCRIPT_SAVED_RE.search(reply)
    if not m:
        return False, None
    return True, m.group(0)


def _tool_instructions(
    *,
    exposed_tool_ids: Optional[set[str]] = None,
) -> str:
    """Static catalog block describing the tool registry to the model.

    Built from the registry alone — no capability probes run here, so composing a chat turn
    costs nothing extra. A model asking for a tool whose capability is missing gets a
    `capability_blocked` event at execution time, which is the honest answer anyway.

    c2-routing: when ``exposed_tool_ids`` is supplied (from the capability-scoped
    exposure layer, ``tools.exposure``), only those tools are described to the
    model instead of all ~485. When it is ``None`` the full registry is described
    (preserves the previous behavior for callers that have not opted in).
    """

    read_lines = []
    mutate_lines = []
    for definition in tool_registry.all_definitions():
        if exposed_tool_ids is not None and definition.tool_id not in exposed_tool_ids:
            continue
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
        "Truthfulness about tool results (non-negotiable):\n"
        "- NEVER claim a change has been applied (\"I've added/created/updated/deleted/saved …\") "
        "unless the server has returned a tool result proving it. A ```tool fence is a REQUEST, "
        "not a result — until the server returns `tool_completed` or `tool_proposal_created`, "
        "nothing has happened.\n"
        "- A mutation proposal is NOT a completed change. Say \"I've proposed …\" or "
        "\"I can add … — here's the preview\" — never \"I added …\". The change applies only "
        "after the user approves it.\n"
        "- If a read tool failed or was blocked, say plainly what you could not check. Do not "
        "claim you verified something you did not.\n"
        "- The server surfaces a visible correction to the creator if you stream a success "
        "claim that no tool result backs. State only what the evidence supports.\n\n"
        "Read tools (run immediately):\n" + "\n".join(read_lines) + "\n\n"
        "Change tools (require the user's approval):\n" + "\n".join(mutate_lines)
    )


def _build_system_message(
    context: str,
    *,
    include_tools: bool = False,
    conversation_locale: str | None = None,
    exposed_tool_ids: Optional[set[str]] = None,
) -> dict[str, str]:
    system = assistant_module.SYSTEM_PROMPT
    if context.strip():
        system += "\n\nCurrent studio context:\n" + context.strip()
    if include_tools:
        system += "\n\n" + _tool_instructions(exposed_tool_ids=exposed_tool_ids)
    # M3.0F: explicit conversation language preference is authoritative.
    if conversation_locale and conversation_locale != "en":
        system += (
            f"\n\nRespond in locale '{conversation_locale}'. "
            "Preserve proper names, glossary terms, and fictional languages exactly. "
            "Do not translate Co-Director, Production Bible, or other protected Adept terms."
        )
    elif conversation_locale == "en":
        system += "\n\nRespond in English unless the user explicitly switches language mid-turn."
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
    conversation_locale: str | None = None,
    attachment_ids: list[str] | None = None,
    active_content_tab: str | None = None,
) -> tuple[CoDirectorProvider, ChatRequest, ContextManifest]:
    request_id = request_id or new_request_id()
    context = ""
    locale = conversation_locale
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
        if not locale:
            try:
                import json as _json

                settings = _json.loads(getattr(project, "settings_json", "") or "{}")
                lang = settings.get("language") or {}
                locale = lang.get("conversationLocale") or lang.get("interfaceLocale")
            except Exception:
                locale = None
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

    if project_id:
        wiki_block = compact_wiki_context(db, project_id)
        if wiki_block:
            context = (context or "") + "\n\n" + wiki_block
        attachment_block = attachment_context_block(
            db, project_id=project_id, attachment_ids=attachment_ids
        )
        if attachment_block:
            context = (context or "") + "\n\n" + attachment_block
        # Workstream H, spec §42 — result-aware context so "number 3" resolves
        # to Frame 3 of the most recent completed execution. Best-effort: empty
        # when no completed execution exists or the pack store is unavailable.
        execution_result_block = execution_result_context_block(db, project_id)
        if execution_result_block:
            context = (context or "") + "\n\n" + execution_result_block

    # Active Project Content tab — lightweight pillar hint (not a hard filter).
    content_tab_hint = content_tab_hint_block(active_content_tab)
    if content_tab_hint:
        context = (context or "") + "\n\n" + content_tab_hint

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
    # c2-routing: capability-scoped tool exposure. Derive the exposed tool set from the
    # user's message (intent) so the model is shown only relevant tools instead of all
    # ~485. The safe baseline (project/scene/timeline/asset/job reads) is always present,
    # ambiguous intent expands rather than restricts, and the set never drops below the
    # baseline. See ``tools.exposure``.
    exposed_tool_ids: Optional[set[str]] = None
    if project_id:
        try:
            from .tools.exposure import expose_ordered

            user_intent = _last_user_message(messages)
            # Map the chat mode to a coarse surface; "setup" mode maps to the setup
            # surface, others default to the project/chat baseline + intent expansion.
            surface = "setup" if mode == "setup" else None
            exposed_tool_ids = set(
                expose_ordered(workspace_surface=surface, intent=user_intent)
            )
        except Exception:  # noqa: BLE001
            exposed_tool_ids = None  # fall back to full catalog
    full_messages = [
        _build_system_message(
            context,
            include_tools=bool(project_id),
            conversation_locale=locale,
            exposed_tool_ids=exposed_tool_ids,
        ),
        *chat_messages,
    ]
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
    origin_session_id: Optional[str] = None,
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
                "kind": "read",
                "arguments": dict(tool_call.arguments),
                "capability": err.details.get("capability"),
                "error": err.to_dict(),
            }
        else:
            yield {
                "type": "tool_failed",
                "requestId": request_id,
                "toolId": tool_call.tool_id,
                "kind": "read",
                "arguments": dict(tool_call.arguments),
                "error": err.to_dict(),
            }
        outcome.follow_up_prompt = (
            f"The `{tool_call.tool_id}` tool could not run: {err.message} "
            "Tell the user plainly what you cannot check right now, and help them with what you "
            "do know. Do not request another tool."
        )
        return

    outcome.invocation = invocation
    # Verified Operator channel (Co-Director 2.0 Mission A): the four
    # operator-capable tools stay `kind="read"`, but on a successful read the
    # service registers an operator request, appends the `operator_requested`
    # event, and decorates the handler result with the `operator` block. The
    # `tool_completed` event below carries the decorated result to the single
    # frontend reception point.
    if tool_call.tool_id in OPERATOR_TOOLS and isinstance(invocation.result, dict):
        operator_block = register_operator_request(
            db,
            project_id=project_id,
            request_id=request_id,
            tool_id=tool_call.tool_id,
            result=invocation.result,
            origin_session_id=origin_session_id or "tab_unknown",
        )
        invocation.result["operator"] = operator_block
    _safe_append_tool_event(
        db,
        project_id,
        request_id=request_id,
        tool_id=tool_call.tool_id,
        arguments=dict(tool_call.arguments),
        result=invocation.result or {},
    )
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
                "kind": "mutating",
                "arguments": dict(tool_call.arguments),
                "capability": err.details.get("capability"),
                "error": err.to_dict(),
            }
        else:
            yield {
                "type": "tool_failed",
                "requestId": request_id,
                "toolId": tool_call.tool_id,
                "kind": "mutating",
                "arguments": dict(tool_call.arguments),
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
    # c2/D10: surface staleness at propose time, not only at approval. If the
    # proposal was created against already-stale base resource versions, flag
    # it immediately so the creator is not presented with a stale proposal as
    # fresh. Approval-time behavior is unchanged.
    if getattr(proposal, "isStale", False):
        yield {
            "type": "proposal_stale",
            "requestId": request_id,
            "toolId": tool_call.tool_id,
            "proposalId": proposal.id,
            "message": (
                "This proposal was built against resource versions that have since changed. "
                "Review before approving — it may need a refresh."
            ),
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
    origin_session_id: Optional[str] = None,
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
                PROJECT_REQUIRED,
                "No project selected. Open or create a project before using production tools.",
                details={
                    "requestId": request_id,
                    "toolId": structured.tool_call.tool_id,
                    "partialWorkCreated": False,
                },
                recoverable=True,
                recommended_action="select_project",
            )
        )
        return

    definition = tool_registry.find(structured.tool_call.tool_id)
    # Audited writes: mutating tools that opt out of human proposal approval
    # (`requires_approval=False`) execute immediately via `execute_audited`. The
    # branch is derived from the registry's `requires_approval` flag for the
    # resolved tool — NOT a hardcoded tool id set — so every audited tool
    # (production_plan.create_draft, audio.cancel_batch,
    # minimax_h3.offer_ltx_fallback, minimax_h3.cancel) routes through
    # execute_audited instead of being silently re-gated as an approval proposal.
    # This never weakens execute_read: only mutating, no-approval tools qualify.
    if (
        definition is not None
        and definition.kind == "mutating"
        and not definition.requires_approval
    ):
        yield {
            "type": "tool_requested",
            "requestId": request_id,
            "toolId": structured.tool_call.tool_id,
            "kind": "mutating",
            "audited": True,
        }
        try:
            invocation = await ToolExecutionService.execute_audited(
                db,
                project_id=project_id,
                tool_id=structured.tool_call.tool_id,
                arguments=structured.tool_call.arguments,
                scene_id=scene_id,
                request_id=request_id,
                created_by="assistant",
            )
        except CoDirectorError as err:
            outcome.errors.append(err)
            yield {
                "type": "tool_failed",
                "requestId": request_id,
                "toolId": structured.tool_call.tool_id,
                "kind": "mutating",
                "arguments": dict(structured.tool_call.arguments),
                "error": err.to_dict(),
            }
            return
        _safe_append_tool_event(
            db,
            project_id,
            request_id=request_id,
            tool_id=structured.tool_call.tool_id,
            arguments=dict(structured.tool_call.arguments),
            result=invocation.result or {},
        )
        # The turn outcome must record the audited mutating execution so downstream
        # truthfulness checks (premature success-claim detection) can verify a
        # mutation-success claim against an actual succeeded invocation.
        outcome.invocations.append(invocation)
        yield {
            "type": "tool_completed",
            "requestId": request_id,
            "toolId": structured.tool_call.tool_id,
            "invocation": invocation.model_dump(mode="json"),
            "unapprovedDraft": True,
            # c2/D9: surface the audited-write justification on the creator-facing
            # receipt too, so the model cannot imply the draft is approved.
            "auditedJustification": (
                (invocation.result or {}).get("auditedJustification")
                if isinstance(invocation.result, dict)
                else None
            ),
        }
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
        origin_session_id=origin_session_id,
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
    conversation_locale: str | None = None,
    attachment_ids: list[str] | None = None,
    active_content_tab: str | None = None,
) -> tuple[
    ChatResult,
    SceneSetupProposal | None,
    str | None,
    ProposalOut | None,
    ContextManifest,
    list[ToolInvocationOut],
]:
    from .conversation import run_conversation_core_turn
    from .providers.base import ChatResult as _ChatResult

    provider, chat_request, manifest = await _prepare_chat_request(
        db,
        messages=messages,
        project_id=project_id,
        scene_id=scene_id,
        mode=mode,
        model=model,
        provider_id=provider_id,
        request_id=request_id,
        conversation_locale=conversation_locale,
        attachment_ids=attachment_ids,
        active_content_tab=active_content_tab,
    )
    # Sync chat shares the stream defer/budget path — Wiki is not on the critical path.
    core = run_conversation_core_turn(
        db,
        project_id=project_id,
        messages=list(messages),
        user_message=_last_user_message(messages),
        mode=mode,
        defer_enrichment=True,
    )
    user_message = _last_user_message(messages)
    if getattr(core, "usesLlmPrimary", False):
        reply, _trace = await _foundation_llm_turn(
            provider=provider,
            chat_request=chat_request,
            user_message=user_message,
            core=core,
        )
        if project_id:
            try:
                from .conversation.deferred_enrichment import run_deferred_enrichment
                from .conversation.momentum import update_momentum_from_turn
                from .conversation.creative_confidence import update_confidence_from_turn

                run_deferred_enrichment(
                    db,
                    project_id=project_id,
                    user_message=user_message,
                    messages=list(messages),
                    request_id=chat_request.request_id,
                )
                update_momentum_from_turn(
                    db,
                    project_id=project_id,
                    user_message=user_message,
                    assistant_reply=reply,
                )
                update_confidence_from_turn(
                    db,
                    project_id=project_id,
                    user_message=user_message,
                    turn_id=chat_request.request_id,
                )
            except Exception:  # noqa: BLE001
                pass
        result = _ChatResult(
            request_id=chat_request.request_id,
            reply=reply,
            model_id=model or chat_request.model_id or "",
            provider_id=getattr(provider, "id", None) or active_provider_id(),
            raw={
                # Truthful degradation surface for the non-stream path (the stream
                # path already emits fallbackUsed on its completed event).
                "fallbackUsed": bool(_trace.get("fallback_used")),
                "fallbackReason": _trace.get("fallback_reason"),
                "providerError": _trace.get("provider_error"),
            },
        )
        if project_id:
            append_assistant_completion(
                db,
                project_id,
                request_id=chat_request.request_id,
                reply=reply,
                model=result.model_id,
                provider_id=result.provider_id,
                message_type="answer",
            )
        return result, None, None, None, manifest, []

    if _conversation_core_handles(core.plan, user_message=user_message):
        result = _ChatResult(
            request_id=chat_request.request_id,
            reply=core.reply,
            model_id=model or chat_request.model_id or "",
            provider_id=active_provider_id(),
        )
        if project_id:
            append_assistant_completion(
                db,
                project_id,
                request_id=chat_request.request_id,
                reply=core.reply,
                model=result.model_id,
                provider_id=result.provider_id,
                message_type="answer",
            )
        return result, None, None, None, manifest, []

    nudge = _plan_system_nudge(core.plan, core.snapshot.director)
    if chat_request.messages and chat_request.messages[0].get("role") == "system":
        chat_request.messages[0]["content"] = (chat_request.messages[0].get("content") or "") + "\n\n" + nudge
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
            if project_id:
                append_assistant_completion(
                    db,
                    project_id,
                    request_id=chat_request.request_id,
                    reply=result.reply,
                    model=result.model_id,
                    provider_id=result.provider_id,
                )
            return result, setup, suggested, proposal, manifest, invocations

        tools_used += 1
        follow_up = _follow_up_request(
            chat_request, assistant_reply=outcome.display, tool_prompt=outcome.follow_up_prompt
        )
        result = await run_cancellable(follow_up.request_id, provider.generate(follow_up))

    if fatal_error is not None:
        raise fatal_error
    if project_id:
        append_assistant_completion(
            db,
            project_id,
            request_id=chat_request.request_id,
            reply=result.reply,
            model=result.model_id,
            provider_id=result.provider_id,
        )
    return result, None, None, proposal, manifest, invocations


def _last_user_message(messages: list[dict[str, str]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return (message.get("content") or "").strip()
    return ""


async def _handle_approve_reject(
    db: Session,
    project_id: str,
    request_id: str,
    decision: RouteDecision,
) -> AsyncIterator[dict[str, Any]]:
    """Route APPROVE/REJECT to existing ProposalService."""
    from .routing.contracts import RouteActionClass

    pending = ProposalService.list(db, project_id, status="pending")
    if not pending:
        yield {
            "type": "route_clarify",
            "requestId": request_id,
            "message": "There is no pending proposal to approve or reject.",
        }
        return
    proposal_id = decision.target or pending[0].id
    try:
        if decision.actionClass == RouteActionClass.APPROVE:
            receipt = ProposalService.approve(db, project_id, proposal_id)
        else:
            receipt = ProposalService.reject(db, project_id, proposal_id, note="Creator rejected via router", decided_by="assistant")
        yield {
            "type": "proposal_resolved",
            "requestId": request_id,
            "proposalId": proposal_id,
            "action": decision.actionClass.value,
            "receipt": receipt.model_dump(mode="json") if hasattr(receipt, "model_dump") else {},
        }
    except Exception as exc:
        yield {
            "type": "proposal_error",
            "requestId": request_id,
            "proposalId": proposal_id,
            "error": str(exc),
        }


_NAVIGATE_TARGET_TO_TOOL: dict[str, str] = {
    "voice_studio": "voice_performance.open_workspace",
    "voicestudio": "voice_performance.open_workspace",
    "audio_studio": "audio.open_studio",
    "audiostudio": "audio.open_studio",
    "timeline": "timeline.focus_ui",
    "script_writer": "workspace.open_scriptwriter",
}

def _navigate_target_to_tool(target: Optional[str]) -> Optional[str]:
    if not target:
        return None
    return _NAVIGATE_TARGET_TO_TOOL.get(target)


_CONVERSATION_CORE_INTENTS = {
    "receive_information",
    "answer_question",
    "request_clarification",
    "recommend_next_step",
    "confirm_correction",
    "invite_continuation",
    "summarize",
    "execute_action",
}


_FOUNDATION_ANALYSIS_RE = re.compile(
    r"\b(critique|compare|suggest|staging|shot|audit|readiness|blocker|tradeoff|alternatives?)\b",
    re.I,
)


def _needs_foundation_intelligence(user_message: str) -> bool:
    """Creative/production analysis requests should use the foundation intelligence path."""

    text = (user_message or "").strip()
    if not text:
        return False
    return bool(_FOUNDATION_ANALYSIS_RE.search(text))


def _conversation_core_handles(plan: Any, user_message: str = "") -> bool:
    primary = str(getattr(plan, "primaryIntent", "") or "")
    mode = str(getattr(plan, "responseMode", "") or "")
    # Intro / correction / next-step / draft-plan stay on Conversation Core.
    if mode in {
        "intro",
        "invite_continuation",
        "recommend_next_step",
        "confirm_correction",
        "request_project",
        "draft_plan",
        "execute_action",
    }:
        return True
    if primary == "execute_action":
        return True
    if primary in {"confirm_correction", "invite_continuation", "recommend_next_step", "summarize"}:
        return True
    # Analysis requests that Conversation Core would only "track" must go to foundation intelligence.
    if _needs_foundation_intelligence(user_message):
        return False
    if primary in _CONVERSATION_CORE_INTENTS:
        return True
    return False


def _plan_system_nudge(plan: Any, director: Any | None = None) -> str:
    """Creator-safe, non-JSON system guidance derived from the conversation plan."""
    lines = [
        "Conversation guidance (internal — never quote as JSON or scores):",
        f"- Response mode: {getattr(plan, 'responseMode', 'conversation')}",
        f"- Creative stage: {getattr(plan, 'creativeStage', 'Project Creation')}",
    ]
    sub = getattr(plan, "creativeSubstate", None)
    if sub:
        lines.append(f"- Substate: {sub}")
    if getattr(plan, "shouldAskQuestion", False) and getattr(plan, "selectedQuestion", None):
        lines.append(f"- Ask at most this one question: {plan.selectedQuestion}")
    else:
        lines.append("- Do not ask a questionnaire; acknowledge or invite continuation when appropriate.")
    # DialoguePlan authority: never inject title/premise intake while workflow HOLD.
    director_ctx = getattr(plan, "directorContext", None) or {}
    workflow_hold = False
    if isinstance(director_ctx, dict):
        workflow_hold = str(director_ctx.get("workflowAdvancePolicy") or "").upper() == "HOLD"
    recommended = getattr(plan, "recommendedNextStep", None)
    if recommended and not workflow_hold:
        lines.append(f"- Recommended next step: {recommended}")
    if director is not None and not workflow_hold:
        goal = getattr(director, "currentGoal", None) or (director.get("currentGoal") if isinstance(director, dict) else None)
        if goal:
            lines.append(f"- Current production goal: {goal}")
    facts = list(getattr(plan, "acknowledgedFacts", None) or [])[:4]
    if facts:
        lines.append("- Known facts: " + "; ".join(facts))
    lines.append("- Never invent media perception. Never expose tool IDs, confidence scores, or raw JSON.")
    return "\n".join(lines)


def _estimate_tokens(text: str) -> int:
    return max(0, len(text or "") // 4)


_FOUNDATION_MIN_TIMEOUT_SEC = 600.0


def _prepare_foundation_request(
    *,
    provider: CoDirectorProvider,
    chat_request: ChatRequest,
    generation_messages: list[dict[str, str]],
) -> tuple[ChatRequest, Any]:
    """Resolve model + timeout for a foundation generation request."""
    model_id = chat_request.model_id
    previous_timeout = getattr(provider, "timeout_sec", None)
    if isinstance(previous_timeout, (int, float)) and float(previous_timeout) < _FOUNDATION_MIN_TIMEOUT_SEC:
        try:
            provider.timeout_sec = _FOUNDATION_MIN_TIMEOUT_SEC  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass
    request = ChatRequest(
        request_id=chat_request.request_id,
        messages=list(generation_messages),
        model_id=model_id,
        project_context=chat_request.project_context,
        temperature=chat_request.temperature,
        mode=chat_request.mode,
    )
    return request, previous_timeout


async def _generate_foundation_reply(
    *,
    provider: CoDirectorProvider,
    chat_request: ChatRequest,
    generation_messages: list[dict[str, str]],
) -> ChatResult:
    """Call the selected provider with DialoguePlan-grounded messages."""

    model_id = chat_request.model_id
    if not model_id:
        try:
            health = await provider.health()
            model_id = getattr(health, "selected_model", None) or model_id
        except Exception:  # noqa: BLE001
            model_id = getattr(provider, "default_model", None) or model_id
        chat_request.model_id = model_id

    request, previous_timeout = _prepare_foundation_request(
        provider=provider,
        chat_request=chat_request,
        generation_messages=generation_messages,
    )
    try:
        return await run_cancellable(request.request_id, provider.generate(request))
    finally:
        if previous_timeout is not None:
            try:
                provider.timeout_sec = previous_timeout  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001
                pass


async def _stream_foundation_tokens(
    *,
    provider: CoDirectorProvider,
    chat_request: ChatRequest,
    generation_messages: list[dict[str, str]],
) -> AsyncIterator[dict[str, Any]]:
    """True provider token stream for the foundation path."""
    model_id = chat_request.model_id
    if not model_id:
        try:
            health = await provider.health()
            model_id = getattr(health, "selected_model", None) or model_id
        except Exception:  # noqa: BLE001
            model_id = getattr(provider, "default_model", None) or model_id
        chat_request.model_id = model_id

    request, previous_timeout = _prepare_foundation_request(
        provider=provider,
        chat_request=chat_request,
        generation_messages=generation_messages,
    )
    try:
        if hasattr(provider, "supports_stream") and provider.supports_stream():
            async for event in provider.stream(request):
                yield event
        else:
            result = await run_cancellable(request.request_id, provider.generate(request))
            yield {"type": "request_started", "requestId": request.request_id}
            yield {
                "type": "provider_connected",
                "requestId": request.request_id,
                "providerId": getattr(provider, "id", None),
            }
            step = max(24, len(result.reply) // 8) if result.reply else 24
            for i in range(0, len(result.reply), step):
                yield {
                    "type": "token",
                    "requestId": request.request_id,
                    "content": result.reply[i : i + step],
                }
            yield {
                "type": "completed",
                "requestId": request.request_id,
                "content": result.reply,
                "modelId": result.model_id,
                "providerId": result.provider_id,
            }
    finally:
        if previous_timeout is not None:
            try:
                provider.timeout_sec = previous_timeout  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001
                pass


async def _foundation_llm_turn(
    *,
    provider: CoDirectorProvider,
    chat_request: ChatRequest,
    user_message: str,
    core: Any,
) -> tuple[str, dict[str, Any]]:
    """LLM-primary reply with grounding, one repair, then deterministic fallback.

    Returns (reply_text, inference_trace_dict).
    """

    from .conversation.foundation.grounding import evaluate_grounding
    from .conversation.foundation.response_generation import (
        SYSTEM_PROMPT_VERSION,
        build_generation_messages,
    )
    from .conversation.foundation.schemas import (
        CoDirectorInferenceTrace,
        ConversationState,
        DialoguePlan,
        IntentAnalysis,
    )

    started = datetime.utcnow()
    intent = IntentAnalysis.model_validate(core.intent or {})
    dialogue = DialoguePlan.model_validate(core.dialoguePlan or {})
    state = ConversationState.model_validate(core.conversationState or {})
    generation_messages = list(core.generationMessages or [])
    fallback = (core.fallbackReply or core.reply or "").strip()
    selected_provider = getattr(provider, "id", None) or active_provider_id()
    selected_model = chat_request.model_id or ""
    if not selected_model:
        try:
            health = await provider.health()
            selected_model = str(getattr(health, "selected_model", "") or "")
        except Exception:  # noqa: BLE001
            selected_model = str(getattr(provider, "default_model", "") or "")
    actual_model = selected_model
    actual_provider = selected_provider
    fallback_used = False
    fallback_reason: str | None = None
    provider_error: dict[str, Any] | None = None
    reply = ""
    repair_used = False
    grounding_passed = True
    companion_hints = dict(getattr(core, "companionGroundingHints", None) or {})

    def _refresh_evidence(text: str) -> dict:
        try:
            from .conversation.discovery.response_evidence import score_response_evidence

            evidence = score_response_evidence(
                text,
                wiki_summary=str(companion_hints.get("wiki_summary") or ""),
                discovery_question=str(companion_hints.get("discovery_question") or ""),
            )
            payload = evidence.model_dump(mode="json")
            companion_hints["response_evidence"] = payload
            return payload
        except Exception:  # noqa: BLE001
            return dict(companion_hints.get("response_evidence") or {})

    try:
        if not generation_messages:
            raise RuntimeError("missing_generation_messages")
        # Persist resolved model onto the request so repair uses the same selection.
        if selected_model and not chat_request.model_id:
            chat_request.model_id = selected_model
        result = await _generate_foundation_reply(
            provider=provider,
            chat_request=chat_request,
            generation_messages=generation_messages,
        )
        reply = (result.reply or "").strip()
        actual_model = result.model_id or actual_model
        actual_provider = result.provider_id or actual_provider
        _refresh_evidence(reply)
        grounding = evaluate_grounding(
            user_message=user_message,
            reply=reply,
            intent=intent,
            plan=dialogue,
            companion=companion_hints,
        )
        if not grounding.ok:
            repair_used = True
            repair_messages = build_generation_messages(
                user_message=user_message,
                intent=intent,
                plan=dialogue,
                state=state,
                context_block="(repair pass — prior draft failed grounding)",
                project_title=getattr(core.snapshot, "title", None) or "the project",
                recent_messages=[],
                repair_notes=list(grounding.notes) or ["Rewrite to satisfy DialoguePlan"],
            )
            # Keep system + user; inject prior draft for repair context.
            repair_messages.append({"role": "assistant", "content": reply})
            repair_messages.append(
                {
                    "role": "user",
                    "content": (
                        "Your previous draft violated the Dialogue Plan / companion grounding. Rewrite once. "
                        "Do not ask for a title or premise. Do not start production planning. "
                        "Do not use generic praise. Do not re-argue after a confirmed decision. "
                        "Do not claim canon updates for exploratory ideas."
                    ),
                }
            )
            repaired = await _generate_foundation_reply(
                provider=provider,
                chat_request=chat_request,
                generation_messages=repair_messages,
            )
            reply = (repaired.reply or "").strip()
            actual_model = repaired.model_id or actual_model
            actual_provider = repaired.provider_id or actual_provider
            _refresh_evidence(reply)
            grounding = evaluate_grounding(
                user_message=user_message,
                reply=reply,
                intent=intent,
                plan=dialogue,
                companion=companion_hints,
            )
            if not grounding.ok:
                fallback_used = True
                fallback_reason = "grounding_failed_after_repair"
                grounding_passed = False
                reply = fallback
                _refresh_evidence(reply)
            else:
                grounding_passed = True
        else:
            grounding_passed = True
    except Exception as exc:  # noqa: BLE001 — last-resort fallback path
        fallback_used = True
        fallback_reason = f"generation_failed:{type(exc).__name__}"
        grounding_passed = False
        reply = fallback
        # Truthful degradation: when the failure is a structured provider error,
        # preserve its envelope so the API response can tell the creator the model
        # turn failed (and why) instead of silently presenting the fallback reply.
        if isinstance(exc, CoDirectorError):
            fallback_reason = f"generation_failed:{exc.code}"
            provider_error = exc.to_dict()
        logger.warning("foundation LLM turn failed; using deterministic fallback: %s", exc)

    if not reply.strip():
        fallback_used = True
        fallback_reason = fallback_reason or "empty_reply"
        grounding_passed = False
        reply = fallback

    latency_ms = (datetime.utcnow() - started).total_seconds() * 1000.0
    input_text = "\n".join(m.get("content") or "" for m in generation_messages)
    trace = CoDirectorInferenceTrace(
        request_id=chat_request.request_id,
        project_id=getattr(core.snapshot, "projectId", "") or "",
        selected_provider=selected_provider,
        selected_model=selected_model or "",
        actual_provider=actual_provider or "",
        actual_model=actual_model or "",
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
        system_prompt_version=SYSTEM_PROMPT_VERSION,
        conversation_message_count=len(generation_messages),
        project_context_token_count=_estimate_tokens(chat_request.project_context or ""),
        memory_context_token_count=_estimate_tokens(
            str((core.conversationState or {}).get("active_goal") or "")
        ),
        tool_context_token_count=0,
        input_token_estimate=_estimate_tokens(input_text),
        output_token_estimate=_estimate_tokens(reply),
        latency_ms=round(latency_ms, 2),
        mode=str(dialogue.mode.value if hasattr(dialogue.mode, "value") else dialogue.mode),
        primary_intent=str(
            intent.primary_intent.value if hasattr(intent.primary_intent, "value") else intent.primary_intent
        ),
        evidence_spans=list(intent.evidence_spans or [])[:8],
        question_budget=int(dialogue.question_budget or 0),
        workflow_advance_policy=str(dialogue.workflow_advance_policy or ""),
    )
    payload = trace.model_dump(mode="json")
    support = getattr(core, "companionSupport", None) or {}
    advisory = getattr(core, "companionAdvisory", None) or {}
    evidence = companion_hints.get("response_evidence") or getattr(core, "responseEvidence", None) or {}
    documentation = getattr(core, "documentationResult", None) or {}
    temperature = getattr(core, "creativeTemperature", None) or {}
    payload.update(
        {
            "companion_need": support.get("support_needed"),
            "advisory_triggered": bool(advisory.get("should_advise")),
            "advisory_strength": advisory.get("advisory_strength"),
            "decision_state": getattr(core.snapshot, "advisoryDecisionState", None),
            "grounding_passed": grounding_passed,
            "repair_used": repair_used,
            "provider_error": provider_error,
            "specialist_policy": getattr(dialogue, "specialist_policy", "NONE"),
            "canon_write_attempted": bool(advisory.get("canon_write_allowed")),
            "canon_write_completed": False,
            "response_evidence": evidence,
            "documentation_reason": documentation.get("reason"),
            "documentation_candidate_count": documentation.get("candidate_count"),
            "creative_stage": temperature.get("stage"),
            "relationship_role": (getattr(core, "relationshipProfile", None) or {}).get("primary_role"),
        }
    )
    return reply, payload


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


async def _emit_completion_with_fence_handling(
    db: Session,
    *,
    project_id: Optional[str],
    scene_id: Optional[str],
    request_id: str,
    reply: str,
    model: str,
    provider_id: str,
    message_type: str,
    fallback_used: bool = False,
    fallback_reason: Optional[str] = None,
    provider_error: Optional[dict[str, Any]] = None,
    append_completion: bool = True,
    origin_session_id: Optional[str] = None,
) -> AsyncIterator[dict[str, Any]]:
    """Yield a final completion after interpreting any ```tool fence in the reply.

    Mirrors the post-stream interpretation path so that deterministic replies from the
    foundation LLM or conversation core still produce proposal/tool events when they
    contain a fenced tool call or mutation proposal.
    """

    structured = parse_structured_reply(reply)
    display = structured.display or reply

    outcome = _StructuredOutcome()
    outcome.display = display

    if structured.tool_call is not None or structured.response_type != "message":
        async for event in _interpret_reply(
            db,
            project_id=project_id,
            scene_id=scene_id,
            request_id=request_id,
            reply=reply,
            tools_used=0,
            outcome=outcome,
            origin_session_id=origin_session_id,
        ):
            yield event

    completed_event: dict[str, Any] = {
        "type": "completed",
        "requestId": request_id,
        "content": outcome.display or display,
        "model": model,
        "providerId": provider_id,
        "messageType": message_type,
        "messageId": f"asst-{request_id}",
    }
    if fallback_used or fallback_reason:
        completed_event["fallbackUsed"] = fallback_used
        if fallback_reason:
            completed_event["fallbackReason"] = fallback_reason
        if provider_error:
            completed_event["providerError"] = provider_error

    yield completed_event

    if outcome.bible_proposal is not None:
        yield {
            "type": "proposal_created",
            "requestId": request_id,
            "proposal": outcome.bible_proposal.model_dump(mode="json"),
        }

    for err in outcome.errors:
        yield {"type": "error", "requestId": request_id, "error": err.to_dict()}

    if append_completion and project_id:
        try:
            append_assistant_completion(
                db,
                project_id,
                request_id=request_id,
                reply=str(outcome.display or display or ""),
                model=model,
                provider_id=provider_id,
                message_type=message_type,
            )
        except Exception:
            pass


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
    conversation_locale: str | None = None,
    attachment_ids: list[str] | None = None,
    origin_session_id: Optional[str] = None,
    active_content_tab: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    from .inference_activity import begin_inference, end_inference

    begin_inference("stream_turn")
    try:
        async for event in _stream_for_project_inner(
            db,
            messages=messages,
            project_id=project_id,
            scene_id=scene_id,
            mode=mode,
            model=model,
            provider_id=provider_id,
            request_id=request_id,
            conversation_locale=conversation_locale,
            attachment_ids=attachment_ids,
            origin_session_id=origin_session_id,
            active_content_tab=active_content_tab,
        ):
            yield event
    finally:
        end_inference()


async def _stream_for_project_inner(
    db: Session,
    *,
    messages: list[dict[str, str]],
    project_id: str | None,
    scene_id: str | None,
    mode: str,
    model: str | None,
    provider_id: str | None = None,
    request_id: str | None = None,
    conversation_locale: str | None = None,
    attachment_ids: list[str] | None = None,
    origin_session_id: Optional[str] = None,
    active_content_tab: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    from .conversation import run_conversation_core_turn

    from .conversation.request_timing import CoDirectorRequestTiming, TokenBuckets, estimate_tokens
    from .conversation.complexity import classify_request_complexity

    # Honest early stage — do not leave the UI on a single frozen "Understanding" label.
    early_request_id = request_id or "pending"
    timing = CoDirectorRequestTiming(requestId=early_request_id, projectId=project_id)
    timing.start_stage("RECEIVING")
    yield {"type": "processing_stage", "requestId": early_request_id, "stage": "RECEIVING"}
    timing.end_stage("RECEIVING")
    timing.start_stage("CLASSIFYING_INTENT")
    yield {"type": "processing_stage", "requestId": early_request_id, "stage": "CLASSIFYING_INTENT"}

    provider, chat_request, manifest = await _prepare_chat_request(
        db,
        messages=messages,
        project_id=project_id,
        scene_id=scene_id,
        mode=mode,
        model=model,
        provider_id=provider_id,
        request_id=request_id,
        conversation_locale=conversation_locale,
        attachment_ids=attachment_ids,
        active_content_tab=active_content_tab,
    )
    timing.requestId = chat_request.request_id
    user_message = _last_user_message(messages)
    timing.complexity = classify_request_complexity(user_message, mode=mode)
    timing.end_stage("CLASSIFYING_INTENT")
    timing.start_stage("READING_PROJECT_CACHE")
    yield {
        "type": "processing_stage",
        "requestId": chat_request.request_id,
        "stage": "READING_PROJECT_CACHE",
    }
    cache_hit = False
    if project_id:
        try:
            from .conversation.project_cache import load_project_cache, warm_project_cache
            from .conversation.momentum import load_momentum, resume_greeting

            cache = load_project_cache(db, project_id)
            if cache is None:
                warm_project_cache(db, project_id, force=True, persist=True)
                cache_hit = False
            else:
                cache_hit = True
            timing.cacheHit = cache_hit
            mom = load_momentum(db, project_id)
            greeting = resume_greeting(mom)
            # Emit grounded resume on return turns (not only short transcripts).
            # Prefer when creator asks to resume / first messages after gap; still allow
            # hydration for established chats when greeting is fresh.
            msg_count = len(list(messages or []))
            user_lower = (user_message or "").lower()
            wants_resume = bool(
                re.search(r"\b(where we left off|pick up|resume|remind me)\b", user_lower)
            ) or msg_count <= 4
            if greeting and wants_resume:
                yield {
                    "type": "momentum_resume",
                    "requestId": chat_request.request_id,
                    "resume": greeting,
                    "momentum": mom.model_dump(mode="json") if mom else None,
                }
        except Exception:  # noqa: BLE001
            pass
    timing.end_stage("READING_PROJECT_CACHE", cache_hit=cache_hit)
    if manifest.bibleVersionId:
        yield {"type": "context_manifest", "requestId": chat_request.request_id, "manifest": manifest.model_dump(mode="json")}

    timing.start_stage("ASSEMBLING_PROMPT")
    yield {
        "type": "processing_stage",
        "requestId": chat_request.request_id,
        "stage": "ASSEMBLING_PROMPT",
    }
    # Phase 3 — canonical RouteDecision from message + production state
    route_decision: Optional[Any] = None
    route_event: Optional[dict[str, Any]] = None
    unified_intent: Optional[Any] = None
    try:
        text = _last_user_message(messages)
        if text and project_id:
            from .routing.orchestrator import route_turn_with_unified
            from .routing.contracts import RouteActionClass
            from .routing.unified_intent import DispatchStrategy, UnifiedIntent

            route_decision, unified_intent, route_event = await route_turn_with_unified(
                text,
                db,
                project_id,
                request_id=chat_request.request_id,
                active_workspace=None,
            )
    except Exception:
        logger.warning("Phase 3 router failed, falling back to legacy path", exc_info=True)
        route_decision = None
        unified_intent = None

    if route_event:
        yield route_event

    # Phase 3 — early NAVIGATE dispatch (before LLM)
    if route_decision and route_decision.actionClass == RouteActionClass.NAVIGATE:
        tool_id = _navigate_target_to_tool(route_decision.target)
        if tool_id and route_decision.capabilityAvailable:
            pass

    # Phase 3 — early APPROVE/REJECT dispatch (before LLM)
    if route_decision and route_decision.actionClass in (RouteActionClass.APPROVE, RouteActionClass.REJECT):
        async for event in _handle_approve_reject(
            db, project_id, chat_request.request_id, route_decision,
        ):
            yield event
        return

    # Workstream B — unified intent dispatch branches.
    # EXECUTION + DETERMINISTIC: bypass the LLM and dispatch directly to the
    # capability handler (Workstream C). When the dispatcher is not yet
    # available, fall back to CURATED_TOOLS.
    # EXECUTION + CURATED_TOOLS: pass curated tool IDs to build_generation_messages
    # so the model emits ```tool blocks.
    # All other intents: existing foundation LLM path (unchanged).
    unified_dispatch_handled = False
    if (
        feature_flags.codirector_operational_agent_v1
        and unified_intent is not None
        and getattr(unified_intent, "is_high_confidence_execution", False)
    ):
        dispatched = False
        # Workstream H — capture the execution_id yielded by the dispatcher so
        # we can emit an honest execution_status message with REAL job state
        # (never a fake "I've created your storyboard" claim). Agent Execution
        # Law: conversation alone is not fulfillment.
        dispatched_execution_id: str | None = None
        try:
            # Workstream C — ExecutionDispatcher may live in routing/ or
            # capabilities/. Try both; the ImportError falls back cleanly.
            try:
                from .routing.execution_dispatcher import ExecutionDispatcher  # type: ignore
            except ImportError:
                from .capabilities.execution_dispatcher import ExecutionDispatcher  # type: ignore

            dispatcher = ExecutionDispatcher()
            async for event in dispatcher.dispatch(unified_intent, {
                "db": db,
                "project_id": project_id,
                "request_id": chat_request.request_id,
                "messages": list(messages),
            }):
                # Capture execution_id from any event that carries it
                # (execution.started / execution.updated / execution.completed).
                eid = event.get("execution_id") if isinstance(event, dict) else None
                if eid and not dispatched_execution_id:
                    dispatched_execution_id = str(eid)
                yield event
            dispatched = True
        except ImportError:
            logger.info(
                "ExecutionDispatcher unavailable — falling back to CURATED_TOOLS dispatch"
            )
        except Exception:
            logger.warning(
                "ExecutionDispatcher failed — falling back to LLM path", exc_info=True
            )
        if dispatched:
            unified_dispatch_handled = True
            # Workstream H — honest completion. After the deterministic dispatch
            # has advanced the execution pack, emit an execution_status assistant
            # message with REAL job state from the pack store. This never claims
            # completion unless every child job is done. When the pack store is
            # unavailable (Workstream C not landed), this is a safe no-op.
            try:
                from .execution.status_messenger import emit_execution_status_events

                for _ev in list(
                    emit_execution_status_events(
                        db,
                        project_id=project_id,
                        request_id=chat_request.request_id,
                        execution_id=dispatched_execution_id,
                    )
                ):
                    yield _ev
            except Exception:  # noqa: BLE001
                logger.warning(
                    "execution_status emit failed (non-fatal)", exc_info=True
                )

    if unified_dispatch_handled:
        return

    # Carry the curated tool IDs into the conversation core turn so the
    # generation messages get a compact tool catalog (CURATED_TOOLS branch).
    curated_tool_ids_for_turn: list[str] = []
    if (
        feature_flags.codirector_operational_agent_v1
        and unified_intent is not None
        and unified_intent.intent.value == "EXECUTION"
        and unified_intent.dispatch == DispatchStrategy.CURATED_TOOLS
    ):
        curated_tool_ids_for_turn = list(unified_intent.curated_tool_ids or [])

    # Response-first: defer Wiki / Living Brief / pitch / research until after streaming begins.
    core = run_conversation_core_turn(
        db,
        project_id=project_id,
        messages=list(messages),
        user_message=user_message,
        mode=mode,
        defer_enrichment=True,
        curated_tool_ids=curated_tool_ids_for_turn or None,
    )
    timing.deferEnrichment = True
    gen_msgs = list(getattr(core, "generationMessages", None) or [])
    buckets = TokenBuckets()
    for m in gen_msgs:
        role = m.get("role")
        toks = estimate_tokens(str(m.get("content") or ""))
        buckets.total += toks
        if role == "system":
            buckets.system += toks
        elif role == "user":
            buckets.conversation += toks
        else:
            buckets.conversation += toks
    timing.tokenBuckets = buckets
    timing.end_stage(
        "ASSEMBLING_PROMPT",
        input_bytes=sum(len(str(m.get("content") or "")) for m in gen_msgs),
    )
    # Prefill-sensitive: dispatch model ASAP. Emit only lightweight pre-stream events;
    # bulky companion/marketing dumps wait until after first tokens when possible.
    _PRE_STREAM_EVENT_TYPES = {
        "request_complexity",
        "specialist_selection",
        "intent_analysis",
        "dialogue_plan",
        "momentum_resume",
    }
    deferred_core_events: list[dict[str, Any]] = []
    for event in core.events:
        payload = dict(event)
        payload["requestId"] = chat_request.request_id
        if payload.get("type") == "processing_stages":
            continue
        if payload.get("type") in _PRE_STREAM_EVENT_TYPES:
            yield payload
        else:
            deferred_core_events.append(payload)

    # Authoritative foundation path: Intent→DialoguePlan→LLM stream→fast grounding.
    if getattr(core, "usesLlmPrimary", False):
        cold_start = False
        model_load_started = time.perf_counter()
        try:
            probe = getattr(provider, "is_model_loaded", None)
            if callable(probe):
                loaded = await probe(chat_request.model_id)
                if loaded is False:
                    cold_start = True
                    yield {
                        "type": "processing_stage",
                        "requestId": chat_request.request_id,
                        "stage": "LOADING_MODEL",
                    }
                    timing.start_stage("LOADING_MODEL")
        except Exception:  # noqa: BLE001
            cold_start = False
        yield {
            "type": "processing_stage",
            "requestId": chat_request.request_id,
            "stage": "WAITING_FOR_MODEL",
        }
        yield {
            "type": "processing_stage",
            "requestId": chat_request.request_id,
            "stage": "RESPONSE_GENERATION",
        }
        reply_parts: list[str] = []
        stream_model = chat_request.model_id
        stream_provider = getattr(provider, "id", None) or active_provider_id()
        emitted_streaming_stage = False
        async for event in _stream_foundation_tokens(
            provider=provider,
            chat_request=chat_request,
            generation_messages=list(getattr(core, "generationMessages", None) or []),
        ):
            if is_cancelled(chat_request.request_id):
                yield {"type": "cancelled", "requestId": chat_request.request_id}
                return
            et = event.get("type")
            if et == "cancelled":
                yield {**event, "requestId": chat_request.request_id}
                return
            if et == "token":
                piece = str(event.get("content") or "")
                if piece:
                    if not emitted_streaming_stage:
                        emitted_streaming_stage = True
                        timing.streamed = True
                        timing.mark_first_token()
                        if cold_start:
                            try:
                                timing.end_stage("LOADING_MODEL")
                            except Exception:  # noqa: BLE001
                                pass
                        yield {
                            "type": "processing_stage",
                            "requestId": chat_request.request_id,
                            "stage": "STREAMING_RESPONSE",
                        }
                        # Emit the first token immediately — never buffer behind Core dumps.
                        reply_parts.append(piece)
                        yield {
                            "type": "token",
                            "requestId": chat_request.request_id,
                            "content": piece,
                        }
                        # Non-critical Core events after first token — never block TTFT.
                        for deferred in deferred_core_events:
                            yield deferred
                        if getattr(core, "intrigue", None):
                            yield {
                                "type": "intrigue",
                                "requestId": chat_request.request_id,
                                "assessment": core.intrigue,
                            }
                        ledger = timing.to_public_dict()
                        ledger["coldStart"] = cold_start
                        ledger["modelLoadMs"] = (
                            round((time.perf_counter() - model_load_started) * 1000, 1)
                            if cold_start
                            else 0.0
                        )
                        yield {
                            "type": "conversation_timings",
                            "requestId": chat_request.request_id,
                            "timings": {
                                **(core.timings or {}),
                                **{"ledger": ledger},
                            },
                        }
                    else:
                        reply_parts.append(piece)
                        yield {
                            "type": "token",
                            "requestId": chat_request.request_id,
                            "content": piece,
                        }
            elif et in {"request_started", "provider_connected"}:
                yield {**event, "requestId": chat_request.request_id}
            elif et == "completed":
                stream_model = event.get("modelId") or stream_model
                stream_provider = event.get("providerId") or stream_provider
                if not reply_parts and event.get("content"):
                    reply_parts.append(str(event.get("content") or ""))
        reply = "".join(reply_parts).strip() or (core.fallbackReply or core.reply or "").strip()
        if not emitted_streaming_stage:
            for deferred in deferred_core_events:
                yield deferred
            yield {
                "type": "conversation_timings",
                "requestId": chat_request.request_id,
                "timings": {**(core.timings or {}), **{"ledger": timing.to_public_dict()}},
            }
        # Fast grounding after stream (does not delay first token).
        yield {
            "type": "processing_stage",
            "requestId": chat_request.request_id,
            "stage": "GROUNDING",
        }
        try:
            from .conversation.foundation.grounding import evaluate_grounding
            from .conversation.foundation.schemas import DialoguePlan, IntentAnalysis

            intent = IntentAnalysis.model_validate(core.intent or {})
            dialogue = DialoguePlan.model_validate(core.dialoguePlan or {})
            grounding = evaluate_grounding(
                user_message=user_message,
                reply=reply,
                intent=intent,
                plan=dialogue,
                companion=dict(getattr(core, "companionGroundingHints", None) or {}),
            )
            if not grounding.ok and (core.fallbackReply or "").strip():
                # Prefer streamed reply; only substitute when empty.
                if not reply.strip():
                    reply = (core.fallbackReply or "").strip()
        except Exception:  # noqa: BLE001
            pass
        started = datetime.utcnow()
        latency_ms = 0.0
        try:
            latency_ms = float((core.timings or {}).get("compose_reply") or 0)
        except Exception:  # noqa: BLE001
            latency_ms = 0.0
        trace = {
            "request_id": chat_request.request_id,
            "project_id": project_id or "",
            "selected_provider": stream_provider,
            "selected_model": chat_request.model_id or "",
            "actual_provider": stream_provider,
            "actual_model": stream_model or "",
            "fallback_used": False,
            "streamed": True,
            "defer_enrichment": True,
            "latency_ms": latency_ms,
        }
        yield {
            "type": "inference_trace",
            "requestId": chat_request.request_id,
            "trace": trace,
        }
        if getattr(core, "responseEvidence", None) or (trace or {}).get("response_evidence"):
            yield {
                "type": "response_evidence",
                "requestId": chat_request.request_id,
                "evidence": (trace or {}).get("response_evidence") or core.responseEvidence,
            }
        if getattr(core, "whatChanged", None):
            yield {
                "type": "what_changed",
                "requestId": chat_request.request_id,
                "lines": core.whatChanged,
            }
        if getattr(core, "projectPulse", None):
            yield {
                "type": "project_pulse",
                "requestId": chat_request.request_id,
                "pulse": core.projectPulse,
            }
        if getattr(core, "discoveryQuestions", None):
            yield {
                "type": "discovery_questions",
                "requestId": chat_request.request_id,
                "questions": core.discoveryQuestions,
            }
        if getattr(core, "conversationActions", None):
            yield {
                "type": "conversation_actions",
                "requestId": chat_request.request_id,
                "actions": core.conversationActions,
            }
        if getattr(core, "artifactReadiness", None):
            yield {
                "type": "artifact_readiness",
                "requestId": chat_request.request_id,
                "assessments": core.artifactReadiness,
            }
        if getattr(core, "activeDeliverable", None):
            yield {
                "type": "deliverable",
                "requestId": chat_request.request_id,
                "deliverable": core.activeDeliverable,
            }
        if getattr(core, "journeyState", None):
            yield {
                "type": "journey_state",
                "requestId": chat_request.request_id,
                "journey": core.journeyState,
            }
        if getattr(core, "visionProfile", None):
            yield {
                "type": "vision_profile",
                "requestId": chat_request.request_id,
                "vision": core.visionProfile,
            }
        if getattr(core, "pitchPackage", None):
            yield {
                "type": "pitch_package",
                "requestId": chat_request.request_id,
                "pitch": core.pitchPackage,
            }
        if getattr(core, "marketingStrategy", None):
            yield {
                "type": "marketing_strategy",
                "requestId": chat_request.request_id,
                "marketing": core.marketingStrategy,
            }
        if getattr(core, "collaborationProfile", None):
            yield {
                "type": "collaboration_profile",
                "requestId": chat_request.request_id,
                "collaboration": core.collaborationProfile,
            }
        support = getattr(core, "companionSupport", None) or {}
        advisory = getattr(core, "companionAdvisory", None) or {}
        relationship = getattr(core, "relationshipProfile", None) or {}
        temperature = getattr(core, "creativeTemperature", None) or {}
        documentation = getattr(core, "documentationResult", None) or {}
        yield {
            "type": "conversation_state",
            "requestId": chat_request.request_id,
            "state": {
                "mode": getattr(core.snapshot, "cognitiveMode", None),
                "activeGoal": getattr(core.snapshot, "activeGoal", None),
                "workflowHold": getattr(core.snapshot, "workflowHold", False),
                "preferenceExplainBeforeProduction": getattr(
                    core.snapshot, "preferenceExplainBeforeProduction", False
                ),
                "evidenceSpans": list(getattr(core.snapshot, "lastEvidenceSpans", None) or []),
                "companionNeed": support.get("support_needed") or getattr(core.snapshot, "companionNeed", None),
                "creativePosture": support.get("support_needed"),
                "advisoryDecision": getattr(core.snapshot, "advisoryDecisionState", None),
                "advisoryStrength": advisory.get("advisory_strength"),
                "changeStatus": "Exploratory"
                if advisory.get("preserve_as_variant")
                else getattr(core.snapshot, "advisoryDecisionState", None),
                "waitingForConfirmation": bool(advisory.get("request_confirmation")),
                "canonUpdated": False,
                "toolsSummary": "None this turn",
                "roleEmphasis": relationship.get("primary_role"),
                "assistantName": relationship.get("assistant_preferred_name"),
                "userPreferredName": relationship.get("user_preferred_name"),
                "creativeStage": temperature.get("stage"),
                "wikiCandidates": documentation.get("candidate_count"),
                "confirmedWrites": documentation.get("confirmed_writes"),
                "discoveryQuestions": len(getattr(core, "discoveryQuestions", None) or []),
                "researchStatus": relationship.get("research_permission"),
                "documentationReason": documentation.get("reason"),
                "whatChanged": list(getattr(core, "whatChanged", None) or []),
                "projectPulse": getattr(core, "projectPulse", None) or {},
                "processingStages": list(getattr(core, "processingStages", None) or []),
                "onboardingNeeded": not bool(relationship.get("onboarding_completed")),
            },
        }
        # Tokens already streamed above — do not fake-chunk after completion.
        wiki_result: dict = {}
        if project_id:
            yield {
                "type": "processing_stage",
                "requestId": chat_request.request_id,
                "stage": "UPDATING_WIKI",
            }
            try:
                from .conversation.deferred_enrichment import run_deferred_enrichment

                wiki_result = run_deferred_enrichment(
                    db,
                    project_id=project_id,
                    user_message=user_message,
                    messages=list(messages),
                    request_id=chat_request.request_id,
                )
                verification = dict(wiki_result.get("verification") or {})
                verification["wikiEventEmitted"] = True
                verification["presentationState"] = "EVENT_EMITTED"
                wiki_result = {**wiki_result, "verification": verification}
                # Detect premature wiki-success language in already-streamed reply (do not rewrite tokens).
                import re as _re

                premature = bool(
                    _re.search(
                        r"\b(?:added to (?:the )?wiki|updated (?:the )?wiki|saved to (?:the )?wiki)\b",
                        reply or "",
                        _re.I,
                    )
                ) and verification.get("persistenceState") != "VERIFIED"
                job_ok = bool(wiki_result.get("ok") and wiki_result.get("readBackOk"))
                yield {
                    "type": "documentation_result",
                    "requestId": chat_request.request_id,
                    "result": wiki_result,
                }
                yield {
                    "type": "wiki_status",
                    "requestId": chat_request.request_id,
                    "verification": verification,
                    "prematureClaim": premature,
                    "message": (
                        "Wiki update still processing…"
                        if verification.get("finalState") == "QUEUED"
                        else None
                    ),
                }
                # c2/D7: general premature tool-success claim detection. The
                # foundation stream path never executes mutating tools, so any
                # mutation-success claim in the streamed reply is a false-success
                # claim. Emit a visible creator-facing correction event (the
                # streamed tokens cannot be retracted, but the creator must not be
                # left with a false impression that a change was applied).
                # c2/D18: verified-operator grounding (contract §1.6) — an operator
                # success claim is only grounded when an ack exists. On this path no
                # operator tool has executed yet this turn (tools run after the
                # streamed reply), so the executed set is empty and this gate stays
                # conservative (never fires without a real executed operator tool).
                tool_premature, tool_match = _detect_premature_tool_success_claim(
                    reply or "", mutating_tool_executed=False
                )
                operator_premature, operator_match = _operator_premature_success_claim(
                    reply or "",
                    executed_operator_tool_ids=frozenset(),
                    has_ack=bool(
                        project_id
                        and has_operator_ack(db, project_id=project_id, request_id=chat_request.request_id)
                    ),
                )
                if tool_premature or operator_premature:
                    yield {
                        "type": "premature_tool_success",
                        "requestId": chat_request.request_id,
                        "matchedPhrase": tool_match or operator_match,
                        "message": (
                            "Correction: no change has been applied yet. The assistant's "
                            "message described a completed edit, but no editing tool ran this "
                            "turn. Nothing in your project was modified. Ask the Co-Director to "
                            "propose the change so you can review and approve it."
                        ),
                    }
                yield {
                    "type": "background_job",
                    "requestId": chat_request.request_id,
                    "jobType": "wiki_enrichment",
                    "status": "COMPLETE" if job_ok else "FAILED",
                    "result": wiki_result,
                    "prematureClaim": premature,
                }
            except Exception as wiki_exc:  # noqa: BLE001
                yield {
                    "type": "background_job",
                    "requestId": chat_request.request_id,
                    "jobType": "wiki_enrichment",
                    "status": "FAILED",
                    "error": str(wiki_exc)[:200],
                    "result": {
                        "verification": {
                            "persistenceState": "FAILED",
                            "presentationState": "EVENT_EMITTED",
                            "finalState": "FAILED",
                            "error": str(wiki_exc)[:200],
                        }
                    },
                }

            # Background momentum + creative confidence (never blocked TTFT).
            try:
                from .conversation.momentum import update_momentum_from_turn
                from .conversation.creative_confidence import (
                    confidence_insight,
                    update_confidence_from_turn,
                )

                mom = update_momentum_from_turn(
                    db,
                    project_id=project_id,
                    user_message=user_message,
                    assistant_reply=reply,
                    development_stage=str(
                        (getattr(core, "creativeTemperature", None) or {}).get("stage") or ""
                    )
                    or None,
                )
                yield {
                    "type": "creative_momentum",
                    "requestId": chat_request.request_id,
                    "momentum": mom.model_dump(mode="json"),
                }
                conf = update_confidence_from_turn(
                    db,
                    project_id=project_id,
                    user_message=user_message,
                    turn_id=chat_request.request_id,
                )
                insight = confidence_insight(conf)
                if conf:
                    yield {
                        "type": "creative_confidence",
                        "requestId": chat_request.request_id,
                        "confidence": conf.model_dump(mode="json"),
                        "insight": insight,
                    }
            except Exception:  # noqa: BLE001
                pass

            try:
                from .conversation.next_steps import build_next_step_options

                listen_only = bool(
                    getattr(core.snapshot, "workflowHold", False)
                    and "just listen" in (user_message or "").lower()
                )
                options = build_next_step_options(
                    db,
                    project_id=project_id,
                    user_message=user_message,
                    relationship_role=str(
                        (getattr(core, "relationshipProfile", None) or {}).get("primary_role") or "BALANCED"
                    ),
                    primary_intent=str((getattr(core, "intent", None) or {}).get("primary_intent") or ""),
                    workflow_hold=bool(getattr(core.snapshot, "workflowHold", False)),
                    creative_stage=str((getattr(core, "creativeTemperature", None) or {}).get("stage") or ""),
                    wiki_candidate_count=int(
                        wiki_result.get("candidateCount")
                        or documentation.get("candidate_count")
                        or 0
                    ),
                    listen_only=listen_only,
                )
                if options:
                    yield {
                        "type": "next_step_options",
                        "requestId": chat_request.request_id,
                        "options": [o.model_dump(mode="json") for o in options],
                        "intro": (
                            "Keep going if you want to stay in story mode — "
                            "or choose a useful next path when you're ready."
                        ),
                    }
            except Exception as next_exc:  # noqa: BLE001
                logger = __import__("logging").getLogger(__name__)
                logger.warning("next_step_options failed: %s", next_exc)

        message_type = "answer"
        if project_id:
            try:
                append_assistant_completion(
                    db,
                    project_id,
                    request_id=chat_request.request_id,
                    reply=reply,
                    model=trace.get("actual_model") or model or chat_request.model_id,
                    provider_id=trace.get("actual_provider")
                    or getattr(provider, "id", None)
                    or active_provider_id(),
                    message_type=message_type,
                )
            except Exception:
                pass
        yield {
            "type": "conversation_timings",
            "requestId": chat_request.request_id,
            "timings": timing.to_public_dict(),
        }
        yield {
            "type": "processing_stage",
            "requestId": chat_request.request_id,
            "stage": "COMPLETE",
        }
        async for event in _emit_completion_with_fence_handling(
            db,
            project_id=project_id,
            scene_id=scene_id,
            request_id=chat_request.request_id,
            reply=reply,
            model=trace.get("actual_model") or model or chat_request.model_id,
            provider_id=trace.get("actual_provider")
            or getattr(provider, "id", None)
            or active_provider_id(),
            message_type=message_type,
            fallback_used=bool(trace.get("fallback_used")),
            fallback_reason=trace.get("fallback_reason"),
            provider_error=trace.get("provider_error"),
            append_completion=False,  # already appended above
            origin_session_id=origin_session_id,
        ):
            yield event
        return

    if _conversation_core_handles(core.plan, user_message=user_message):
        # Deterministic conversation-core reply for residual non-LLM-primary turns.
        # Strip any tool/proposal fence from the streamed token so the creator never
        # sees raw markdown, then interpret the fence for proposal/tool events.
        structured = parse_structured_reply(core.reply)
        message_type = (
            "clarification"
            if core.plan.primaryIntent == "request_clarification"
            else "recommendation"
            if core.plan.primaryIntent == "recommend_next_step"
            else "answer"
        )
        yield {
            "type": "token",
            "requestId": chat_request.request_id,
            "content": structured.display or core.reply,
        }
        async for event in _emit_completion_with_fence_handling(
            db,
            project_id=project_id,
            scene_id=scene_id,
            request_id=chat_request.request_id,
            reply=core.reply,
            model=model or chat_request.model_id,
            provider_id=getattr(provider, "id", None) or active_provider_id(),
            message_type=message_type,
            append_completion=False,  # already appended above
        ):
            yield event
        return

    # Production specialist / provider path — inject plan nudge + recent transcript already in request.
    nudge = _plan_system_nudge(core.plan, core.snapshot.director)
    if chat_request.messages and chat_request.messages[0].get("role") == "system":
        chat_request.messages[0]["content"] = (chat_request.messages[0].get("content") or "") + "\n\n" + nudge
    else:
        chat_request.messages = [{"role": "system", "content": nudge}, *chat_request.messages]

    # Phase 7 — zero-specialist guard for NAVIGATE/READ/APPROVE/REJECT
    _zero_specialist_actions = frozenset({"NAVIGATE", "READ_INSPECT", "APPROVE", "REJECT"})
    if route_decision is not None and getattr(route_decision, "actionClass", None) is not None:
        action = route_decision.actionClass
        action_name = action.value if hasattr(action, "value") else str(action)
        if action_name in _zero_specialist_actions:
            wants_consult = False  # zero specialists for these action classes

    # Intelligence v2 specialists are subordinate consultants only.
    # They must not become an independent creator-facing speaker that bypasses DialoguePlan.
    # When analysis is requested, fold findings into the foundation LLM path instead of returning here.
    if (
        getattr(core, "wantsSpecialistConsult", False)
        and _intelligence_enabled_for_turn(project_id=project_id, messages=messages, mode=mode)
        and IntelligenceService is not None
    ):
        yield {
            "type": "intelligence_progress",
            "requestId": chat_request.request_id,
            "stage": "specialist_consult_subordinate",
            "message": "Gathering specialist evidence under DialoguePlan authority…",
        }
        # Fall through to foundation / provider paths — specialist synthesis is not the final speaker.

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
                origin_session_id=origin_session_id,
            ):
                yield tool_event

            if outcome.follow_up_prompt is not None:
                follow_up_prompt = outcome.follow_up_prompt
                follow_up_reply = outcome.display
                continue

            yield {
                **event,
                "content": outcome.display or content,
                "sceneSetup": setup.model_dump() if setup else None,
                "suggestedPrompt": suggested,
                "messageId": f"asst-{chat_request.request_id}",
            }
            if outcome.bible_proposal is not None:
                yield {
                    "type": "proposal_created",
                    "requestId": chat_request.request_id,
                    "proposal": outcome.bible_proposal.model_dump(mode="json"),
                }
            for err in outcome.errors:
                yield {"type": "error", "requestId": chat_request.request_id, "error": err.to_dict()}
            # c2/D7: general premature tool-success claim detection for the legacy
            # stream path. A mutation "completed" claim is only legitimate if an
            # audited mutating tool actually executed and succeeded this turn. A
            # proposal alone does not complete the change, so it does not count.
            _mutating_executed = any(
                getattr(inv, "kind", None) == "mutating"
                and getattr(inv, "status", None) == "succeeded"
                for inv in (outcome.invocations or [])
            )
            _tool_premature, _tool_match = _detect_premature_tool_success_claim(
                outcome.display or content or "", mutating_tool_executed=_mutating_executed
            )
            # c2/D18: verified-operator grounding (contract §1.6). An operator
            # success claim ("opened X" / "focused the timeline") is only grounded
            # when an `operator_acknowledged` event exists for this request id.
            # All executed operator tools this turn must be acked; a single
            # unacknowledged operator request keeps the gate active.
            _operator_tool_ids = frozenset(
                getattr(inv, "toolId", None)
                for inv in (outcome.invocations or [])
                if getattr(inv, "toolId", None) in OPERATOR_TOOLS
            )
            _operator_has_ack = bool(
                project_id
                and _operator_tool_ids
                and all(
                    has_operator_ack(db, project_id=project_id, request_id=chat_request.request_id)
                    for _ in _operator_tool_ids
                )
            )
            _operator_premature, _operator_match = _operator_premature_success_claim(
                outcome.display or content or "",
                executed_operator_tool_ids=_operator_tool_ids,
                has_ack=_operator_has_ack,
            )
            _script_saved = any(
                "save" in (getattr(inv, "toolId", "") or "")
                for inv in (outcome.invocations or [])
            )
            _script_premature, _script_match = _detect_premature_script_save_claim(
                outcome.display or content or "", script_saved=_script_saved
            )
            if _tool_premature or _operator_premature or _script_premature:
                yield {
                    "type": "premature_tool_success",
                    "requestId": chat_request.request_id,
                    "matchedPhrase": _tool_match or _operator_match or _script_match,
                    "message": (
                        "Correction: that change has not been confirmed yet. The assistant's "
                        "message described a completed action, but no edit completed this turn "
                        "and no operator request was acknowledged. Nothing in your project was "
                        "modified. Confirm the on-screen prompt or ask the Co-Director to "
                        "propose the change for your review."
                    ),
                }
            # Server owns the assistant reply event: append it once the turn
            # is final so a client that disconnects mid-stream still has the
            # authoritative transcript on reload. Idempotent on
            # `asst-{request_id}` so a retried stream cannot duplicate.
            if project_id:
                try:
                    append_assistant_completion(
                        db,
                        project_id,
                        request_id=chat_request.request_id,
                        reply=str(outcome.display or content or ""),
                        model=model or chat_request.model_id,
                        provider_id=getattr(provider, "id", None) or active_provider_id(),
                    )
                except Exception:
                    pass

        if follow_up_prompt is None:
            return
        tools_used += 1
        active_request = _follow_up_request(
            active_request, assistant_reply=follow_up_reply, tool_prompt=follow_up_prompt
        )


# --------------------------------------------------------------------------
# Conversation persistence (project-scoped) — Wave A persistent memory.
#
# The append-only `codirector_conversation_events` table is the source of
# truth. The legacy `messages_json` column is retained only for the reversible
# migration backfill; it is no longer read or written by the live path. The
# server owns BOTH creator and assistant/tool events — chat/stream completion
# appends the assistant reply (and any tool call/result) server-side, so the
# client never has to replace the authoritative transcript after generation.
# --------------------------------------------------------------------------


def _conversation_to_dict(db: Session, row: CoDirectorConversation) -> dict[str, Any]:
    return events_conversation_to_dict(db, row)


def get_conversation(db: Session, project_id: str) -> dict[str, Any] | None:
    row = db.get(CoDirectorConversation, project_id)
    if not row:
        return None
    return _conversation_to_dict(db, row)


def get_conversation_revision(db: Session, project_id: str) -> int:
    return current_revision(db, project_id)


def append_conversation_events(
    db: Session,
    project_id: str,
    events: list[EventInput],
    *,
    expected_revision: int | None = None,
    model: str | None = None,
    provider_id: str | None = None,
) -> AppendBatchResult:
    """Append creator (or server) events with idempotency + optimistic concurrency."""

    return append_events(
        db,
        project_id,
        events,
        expected_revision=expected_revision,
        model=model,
        provider_id=provider_id,
    )


def save_conversation(
    db: Session,
    project_id: str,
    *,
    messages: list[dict[str, Any]],
    model: str | None,
    provider_id: str | None,
    expected_revision: int | None = None,
    allow_admin_replace: bool = False,
) -> dict[str, Any]:
    """DEPRECATED as a *blind* full-replace. Now an idempotent append-merge by id.

    The creator client must NOT use this as its primary persistence path — it
    must append via `POST /conversations/{project_id}/events` instead. This
    endpoint is retained for (a) the reversible migration's backfill, (b) test
    seeding, and (c) explicit admin/repair tooling that needs to rewrite the
    whole transcript. It can NEVER truncate the event log: posted messages
    are reconciled by `message_id` and only appended if missing. A revision
    mismatch yields a 409 (signalled via the router). When
    `allow_admin_replace=True` the supplied messages fully replace the event
    log (repair path) and require a matching `expected_revision`.
    """

    header = db.get(CoDirectorConversation, project_id)
    if header is None:
        header = CoDirectorConversation(project_id=project_id, revision=0)
        db.add(header)
        db.flush()

    if allow_admin_replace:
        if expected_revision is not None and expected_revision != header.revision:
            raise CoDirectorError(
                "CONFLICT",
                "Conversation revision mismatch — reload and retry the admin replace.",
                details={"expected": expected_revision, "actual": header.revision},
                recoverable=True,
                recommended_action="reload",
            )
        # Admin repair path: rebuild the event log from the supplied messages.
        delete_all_events(db, project_id)
        inputs: list[EventInput] = []
        for m in messages:
            inputs.append(
                EventInput(
                    role=str(m.get("role") or "user"),
                    content=str(m.get("content") or ""),
                    message_id=m.get("id"),
                    message_type=m.get("messageType") or m.get("message_type"),
                    status=m.get("status"),
                    attachments=m.get("attachments") or m.get("attachment_ids"),
                    actor="user" if m.get("role") == "user" else "assistant",
                    created_at=datetime.utcnow(),
                )
            )
        append_events(db, project_id, inputs, expected_revision=0, model=model, provider_id=provider_id)
    else:
        # Legacy creator/test seeding path: append-merge by id. Never truncates.
        if expected_revision is not None and expected_revision != header.revision:
            raise CoDirectorError(
                "CONFLICT",
                "Conversation revision mismatch — reload and reconcile by id before retrying.",
                details={"expected": expected_revision, "actual": header.revision},
                recoverable=True,
                recommended_action="reload",
            )
        inputs = []
        for m in messages:
            inputs.append(
                EventInput(
                    role=str(m.get("role") or "user"),
                    content=str(m.get("content") or ""),
                    message_id=m.get("id"),
                    message_type=m.get("messageType") or m.get("message_type"),
                    status=m.get("status"),
                    attachments=m.get("attachments") or m.get("attachment_ids"),
                    actor="user" if m.get("role") == "user" else "assistant",
                    created_at=datetime.utcnow(),
                )
            )
        append_events(db, project_id, inputs, model=model, provider_id=provider_id)

    header = db.get(CoDirectorConversation, project_id)
    if header is None:
        raise CoDirectorError("CONFLICT", "Conversation header vanished during save.")
    return _conversation_to_dict(db, header)


def delete_conversation(db: Session, project_id: str) -> bool:
    row = db.get(CoDirectorConversation, project_id)
    if row is None:
        # Still clear any orphan events (defensive).
        delete_all_events(db, project_id)
        return False
    delete_all_events(db, project_id)
    row = db.get(CoDirectorConversation, project_id)
    if row is not None:
        db.delete(row)
        db.commit()
    return True


# --------------------------------------------------------------------------
# Server-side assistant/tool event append (used by chat/stream completion).
# --------------------------------------------------------------------------


def _assistant_event_from_completion(
    *,
    request_id: str,
    reply: str,
    message_id: str | None,
    message_type: str | None,
    model: str | None,
    provider_id: str | None,
    status: str | None = None,
) -> tuple[EventInput, str, str | None]:
    """Build an assistant message event for a completed turn.

    Returns (event, role, message_type). A stable message_id is generated when
    the caller does not supply one so a retried completion cannot duplicate.
    """

    mid = message_id or f"asst-{request_id}"
    ev = EventInput(
        role="assistant",
        content=reply or "",
        event_type="message",
        message_id=mid,
        client_request_id=None,
        message_type=message_type,
        status=status,
        actor="assistant",
        request_id=request_id,
    )
    return ev, "assistant", message_type


def append_assistant_completion(
    db: Session,
    project_id: str,
    *,
    request_id: str,
    reply: str,
    model: str | None,
    provider_id: str | None,
    message_id: str | None = None,
    message_type: str | None = None,
    status: str | None = None,
) -> str:
    """Append the assistant reply event for a finished chat/stream turn.

    Idempotent on `message_id` (defaults to `asst-{request_id}`), so a retried
    completion or a stream that re-emits its final event does not duplicate.
    Returns the message id used.
    """

    ev, _role, _mt = _assistant_event_from_completion(
        request_id=request_id,
        reply=reply,
        message_id=message_id,
        message_type=message_type,
        model=model,
        provider_id=provider_id,
        status=status,
    )
    append_events(db, project_id, [ev], model=model, provider_id=provider_id)
    return ev.message_id or ""


def _safe_append_tool_event(
    db: Session,
    project_id: str,
    *,
    request_id: str,
    tool_id: str,
    arguments: dict[str, Any] | None,
    result: dict[str, Any] | None,
) -> None:
    """Persist tool call/result events; never break chat on failure."""

    if not project_id:
        return
    try:
        append_tool_event(
            db,
            project_id,
            request_id=request_id,
            tool_id=tool_id,
            arguments=arguments,
            result=result,
        )
    except Exception:
        logger.exception(
            "Failed to append tool event project=%s request=%s tool=%s",
            project_id,
            request_id,
            tool_id,
        )


def append_tool_event(
    db: Session,
    project_id: str,
    *,
    request_id: str,
    tool_id: str,
    arguments: dict[str, Any] | None,
    result: dict[str, Any] | None,
    role: str = "tool",
) -> None:
    """Append a tool_call/tool_result event pair (or a single tool event)."""

    call = EventInput(
        role=role,
        content="",
        event_type="tool_call",
        message_id=f"tool-call-{request_id}-{tool_id}",
        tool_id=tool_id,
        tool_arguments=arguments,
        actor="assistant",
        request_id=request_id,
    )
    res = EventInput(
        role=role,
        content="",
        event_type="tool_result",
        message_id=f"tool-result-{request_id}-{tool_id}",
        tool_id=tool_id,
        tool_result=result,
        actor="assistant",
        request_id=request_id,
    )
    append_events(db, project_id, [call, res])
