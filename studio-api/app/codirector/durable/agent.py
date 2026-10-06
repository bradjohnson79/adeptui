"""The one Co-Director agent. Reasoning only; tools own side effects."""

from __future__ import annotations

import json
import re
from contextvars import ContextVar
from typing import Any, Callable

from pydantic_ai import Agent
from pydantic_ai.durable_exec.dbos import DBOSDurability
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import FunctionModel

from .deps import TurnDeps
from .prompt import SYSTEM_PROMPT
from .toolset import build_toolset

AGENT_NAME = "adept_codirector"

_DEPS: ContextVar[TurnDeps | None] = ContextVar("adept_cd_deps", default=None)
_OVERRIDE: ContextVar[Callable[..., Any] | None] = ContextVar("adept_cd_model_override", default=None)


def set_turn_deps(deps: TurnDeps | None) -> None:
    _DEPS.set(deps)


def set_model_override(func: Callable[..., Any] | None) -> None:
    """Test hook. Production turns leave this empty and use the selected provider."""

    _OVERRIDE.set(func)


def _last_user_text(messages) -> str:
    text = ""
    for message in messages:
        for part in getattr(message, "parts", []) or []:
            content = getattr(part, "content", None)
            if isinstance(content, str) and content.strip():
                text = content
    return text


def _parse_decision(reply: str) -> dict[str, Any] | None:
    """Use the first JSON object. A second copy or a markdown fence must not swallow it."""

    text = reply or ""
    start = 0
    while True:
        index = text.find("{", start)
        if index < 0:
            return None
        depth = 0
        in_string = False
        escaped = False
        for end in range(index, len(text)):
            char = text[end]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    try:
                        parsed = json.loads(text[index : end + 1])
                    except json.JSONDecodeError:
                        break
                    if isinstance(parsed, dict) and ("tool_id" in parsed or "reply" in parsed or "mode" in parsed):
                        return parsed
                    break
        start = index + 1


def _tool_already_returned(messages) -> bool:
    for message in messages:
        for part in getattr(message, "parts", []) or []:
            if type(part).__name__ == "ToolReturnPart":
                return True
    return False


def _tool_returns(messages) -> list[str]:
    found: list[str] = []
    for message in messages:
        for part in getattr(message, "parts", []) or []:
            if type(part).__name__ == "ToolReturnPart":
                found.append(str(getattr(part, "content", "") or ""))
    return found


def _production_source(envelope: dict, name: str) -> str:
    """The scene request on this turn, or the one the creator just had to repeat."""

    user_text = str(envelope.get("user_text") or "")
    history = envelope.get("conversation_for_model") or []
    candidates = [user_text]
    for item in reversed(history):
        if isinstance(item, dict) and str(item.get("role") or "") == "user":
            candidates.append(str(item.get("content") or ""))
    probe = {"create_scene", "timeline.propose_add_prompt_segment"}
    for text in candidates:
        if not text.strip():
            continue
        if text != user_text and name.casefold() not in text.casefold():
            continue
        if _operation_tool(text, probe):
            return text
    return ""


def _continue_after_lookup(messages) -> ModelResponse | None:
    """A successful lookup is a step. The original production request still runs."""

    returns = _tool_returns(messages)
    if len(returns) != 1:
        return None
    from .bind import visible_character_matches

    matches = visible_character_matches(returns[0])
    if len(matches) != 1:
        return None
    deps = _DEPS.get()
    if deps is None:
        return None
    name = matches[0]["displayName"]
    source = _production_source(deps.envelope, name)
    if not source:
        return None
    allowed = set(deps.exposed_tool_ids)
    tool_id = _operation_tool(source, allowed | {"create_scene", "timeline.propose_add_prompt_segment"})
    if not tool_id:
        return None
    exposed = list(deps.exposed_tool_ids)
    if tool_id not in exposed:
        exposed.append(tool_id)
        deps.exposed_tool_ids = tuple(exposed)
    admitted = list(deps.envelope.get("exposed_tool_ids") or [])
    if tool_id not in admitted:
        admitted.append(tool_id)
        deps.envelope["exposed_tool_ids"] = admitted
    deps.envelope["turn_mode"] = "MUTATE"
    return ModelResponse(parts=[ToolCallPart(tool_name=tool_id, args={"characterName": name})])


def _tool_return_text(messages) -> str:
    from .wording import project_creator_reply

    found = _tool_returns(messages)
    raw = found[-1] if found else ""
    return project_creator_reply(raw)


def _operation_tool(user_text: str, allowed: set[str]) -> str:
    """When the model returns no tool, use the one operation that the request uniquely needs."""

    from .admission import classify_turn_mode, is_open_discussion, is_timed_instruction, named_surface

    if is_open_discussion(user_text):
        return ""
    surface = named_surface(user_text)
    folded = " ".join((user_text or "").lower().split())
    if (
        is_timed_instruction(user_text)
        and classify_turn_mode(user_text) in {"PROPOSE", "MUTATE"}
        and "timeline.propose_add_prompt_segment" in allowed
    ):
        return "timeline.propose_add_prompt_segment"
    explicit_still = any(
        phrase in folded
        for phrase in (
            "create a still",
            "generate a still",
            "still image",
            "create an image",
            "generate an image",
            "create a cinematic",
        )
    )
    if surface == "image" and explicit_still and "propose_image_generate" in allowed:
        return "propose_image_generate"
    from .bind import is_new_character_request, is_reference_sheet_request

    if is_reference_sheet_request(user_text) and "character_creator.propose_visual_sheet" in allowed:
        return "character_creator.propose_visual_sheet"
    if (
        is_new_character_request(user_text)
        and classify_turn_mode(user_text) in {"PROPOSE", "MUTATE"}
        and "character_creator.create_from_brief" in allowed
    ):
        return "character_creator.create_from_brief"
    from .bind import is_environment_generation_request, is_prop_generation_request, ordered_execution_plan

    plan = ordered_execution_plan(user_text)
    if plan:
        first = str(plan[0].get("toolId") or "")
        if first in allowed:
            return first
    if is_prop_generation_request(user_text) and "prop_creator.generate_view" in allowed:
        return "prop_creator.generate_view"
    if is_environment_generation_request(user_text) and "ers.generate" in allowed:
        return "ers.generate"
    if "film_timeline.send_to_magi" in allowed and re.search(r"\bsend\b", user_text or "", re.I) and re.search(
        r"\bmagi\b", user_text or "", re.I
    ):
        return "film_timeline.send_to_magi"
    if "timeline.publish_scene" in allowed and re.search(r"\bpublish\b", user_text or "", re.I) and re.search(
        r"\bscene\b", user_text or "", re.I
    ):
        return "timeline.publish_scene"
    if "timeline.prepend_shot" in allowed and re.search(r"\bshot\b", user_text or "", re.I) and re.search(
        r"\b(?:before|opening|prequel|prepend)\b", user_text or "", re.I
    ):
        return "timeline.prepend_shot"
    if "timeline.continue_shot" in allowed and re.search(r"\bshot\b", user_text or "", re.I) and re.search(
        r"\b(?:after|continue|extend)\b", user_text or "", re.I
    ):
        return "timeline.continue_shot"
    if "timeline.generate_shot" in allowed and re.search(
        r"\b(?:generate|render)\s+(?:this\s+|that\s+|the\s+)?shot\b",
        user_text or "",
        re.I,
    ):
        return "timeline.generate_shot"
    if "create_scene" in allowed and any(
        phrase in folded
        for phrase in ("create a scene", "create a new scene", "create a timeline scene", "timeline scene")
    ):
        return "create_scene"
    from .admission import (
        audio_operation,
        magi_final_render_request,
        voice_identity_requested,
        voice_status_question,
    )

    if magi_final_render_request(user_text) and "magi.render" in allowed:
        return "magi.render"
    if re.search(r"\brecipe\b", user_text or "", re.I) and "magi.recipe.apply" in allowed:
        return "magi.recipe.apply"
    if re.search(r"\b(dissolve|wipe|fade)\b", user_text or "", re.I) and "magi.transition.apply" in allowed:
        return "magi.transition.apply"
    if (
        re.search(r"\b(lighting|warmer|cooler|brightness|highlights|shadows)\b", user_text or "", re.I)
        and "magi.color.apply" in allowed
    ):
        return "magi.color.apply"
    if re.search(r"\bcompare\b", user_text or "", re.I) and "magi.compare" in allowed:
        return "magi.compare"

    if voice_status_question(user_text) and "character_creator.get_voice_status" in allowed:
        return "character_creator.get_voice_status"
    if (
        voice_identity_requested(user_text)
        and not voice_status_question(user_text)
        and "character_creator.generate_voice_candidates" in allowed
    ):
        return "character_creator.generate_voice_candidates"
    operation = audio_operation(user_text)
    if operation:
        magi_audio = "magi.audio.generate"
        audio_tool = f"audio.generate_{operation}"
        if operation in {"music", "sfx"} and magi_audio in allowed and audio_tool not in allowed:
            return magi_audio
        if audio_tool in allowed:
            return audio_tool
    return ""


async def _decision_retry(provider, workflow_id: str, model_id: str | None, catalog: str, user_text: str) -> str:
    from ..providers.base import ChatRequest

    prompt = (
        "Return one JSON object only. Do not ask a question. "
        "The server already knows the open scene and binds the creator's text, duration, ratio, reference, and brief. "
        '{"reply":"Awaiting approval.","tool_id":"<one admitted tool>","arguments":{}}\n'
        f"Creator request: {user_text[:2000]}\nTools:\n{catalog}"
    )
    try:
        generated = await provider.generate(
            ChatRequest(
                request_id=f"{workflow_id}:decision",
                messages=[{"role": "user", "content": prompt}],
                model_id=model_id,
            )
        )
    except Exception:
        return ""
    return generated.reply or ""


def _transcript(messages) -> str:
    lines: list[str] = []
    for message in messages:
        for part in getattr(message, "parts", []) or []:
            name = type(part).__name__
            if name in {"UserPromptPart", "TextPart"}:
                content = getattr(part, "content", "")
                if isinstance(content, str) and content.strip():
                    lines.append(content.strip()[:2000])
            elif name == "ToolReturnPart":
                lines.append(
                    f"Tool result {getattr(part, 'tool_name', '')}: {getattr(part, 'content', '')}"[:2000]
                )
    return "\n".join(lines[-8:])


def _catalog_for_mode(catalog_tools: list, mode: str) -> list:
    """Show the tools that mode may call. A hint does not hide a tool the model still has to judge."""

    from ..tools.registry import find

    read_tools = []
    navigation = []
    mutating = []
    for tool in catalog_tools:
        try:
            definition = find(tool.name)
        except Exception:
            definition = None
        kind = definition.kind if definition is not None else ""
        if "open" in tool.name and kind != "mutating":
            navigation.append(tool)
        elif kind == "read":
            read_tools.append(tool)
        elif kind == "mutating":
            mutating.append(tool)
    if mode == "READ":
        return read_tools or catalog_tools
    if mode == "NAVIGATE":
        return navigation or catalog_tools
    if mode in {"PROPOSE", "MUTATE"}:
        return mutating or catalog_tools
    return catalog_tools


async def call_selected_provider(messages, info) -> ModelResponse:
    override = _OVERRIDE.get()
    if override is not None:
        result = override(messages, info)
        if hasattr(result, "__await__"):
            result = await result
        return result

    if _tool_already_returned(messages):
        continued = _continue_after_lookup(messages)
        if continued is not None:
            return continued
        return ModelResponse(parts=[TextPart(content=_tool_return_text(messages) or "I'll keep going with what you asked.")])

    deps = _DEPS.get()
    envelope = {} if deps is None else deps.envelope
    provider_id = str(envelope.get("provider_id") or "")
    model_id = str(envelope.get("model_id") or "") or None
    workflow_id = str(envelope.get("workflow_id") or "turn")
    mode = str(envelope.get("turn_mode") or "CONVERSATION")
    catalog_tools = _catalog_for_mode(list(info.function_tools), mode)
    catalog = "\n".join(f"- {tool.name}: {tool.description}" for tool in catalog_tools[:40])
    history = envelope.get("conversation_for_model") or []
    history_lines = []
    for item in history[-12:]:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "").strip()
        if content:
            history_lines.append(f"{item.get('role') or 'user'}: {content[:1500]}")
    transcript = "\n".join(history_lines) or _transcript(messages) or _last_user_text(messages)
    prompt = (
        f"{SYSTEM_PROMPT}\nAdmitted mode: {mode}\n"
        f"Project id: {envelope.get('project_id') or ''}\n"
        f"Scene id: {envelope.get('scene_id') or ''}\n"
        f"Open workspace: {envelope.get('surface') or 'none'}\n"
        "The admitted mode is a hint from explicit wording. You decide what the latest sentence means, using the conversation above it.\n"
        "CONVERSATION is discussion, brainstorming, or a correction of an idea. tool_id must be null.\n"
        "READ is a question about the live project. You may call one admitted read-only tool.\n"
        "NAVIGATE opens or shows a studio. You may call one admitted navigation tool. Do not change the project.\n"
        "PROPOSE prepares a draft or the creator said not to apply it yet. You may call one proposal tool.\n"
        "MUTATE is an explicit request to create, place, or generate. You may call one admitted tool. Approval still happens before anything is saved.\n"
        "Do not treat the words change, use, add, scene, or character as a command by themselves.\n"
        "A named studio limits which tool you may call. It does not choose the tool for you.\n"
        "If you are unsure, stay in CONVERSATION or ask one short question. Do not call a tool.\n"
        "If they explicitly asked to prepare a timed prompt, call timeline.propose_add_prompt_segment. "
        "Do not call set_scene_prompt for that request. The server binds the scene and the text.\n"
        "If they explicitly asked Image Generator for a still image, call propose_image_generate. Do not call a video tool.\n"
        "If they explicitly asked Character Creator to create a new character, call character_creator.create_from_brief. "
        "Do not update an existing character.\n"
        "If they explicitly asked for a Character Reference Sheet, call character_creator.propose_visual_sheet. "
        "The server binds characterId and creates one front reference. "
        "Do not create a new character for that request. "
        "Do not say the sheet is a multi-view sheet.\n"
        "If they explicitly asked Prop Creator to create a prop, call prop_creator.generate_view. "
        "The server binds the prop and the Prop Creator generator plan.\n"
        "If they ask what voice a character has, call character_creator.get_voice_status.\n"
        "If they ask Voice Studio to give a character a voice, or to have a character say a line, "
        "call character_creator.generate_voice_candidates. The server binds the character, the line, and the tone.\n"
        "If they ask Audio Studio for ambience, call audio.generate_ambience. "
        "For a sound effect in Audio Studio, call audio.generate_sfx. For music or a score in Audio Studio, call audio.generate_music. "
        "When the open workspace is magi, a request to add music or a sound effect to the current scene calls magi.audio.generate. "
        "Do not call Audio Studio for that request. "
        "When the open workspace is magi and they ask for a final render, call magi.render. "
        "Do not grade or upscale unless they asked for that. "
        "When they ask to apply a MAGI recipe, call magi.recipe.apply. "
        "When they ask to change lighting, brightness, or temperature, call magi.color.apply. "
        "When they ask for a dissolve, fade, or wipe between clips, call magi.transition.apply. "
        "When they ask to compare the grade with the original, call magi.compare. "
        "The server binds the sound description. "
        "If they also ask to place that sound in Audio Studio, create it first. Placement waits until the clip exists.\n"
        "When Voice Studio or Audio Studio tools are listed, do not say you lack access to them.\n"
        "Use an empty arguments object. The server binds the creator's request.\n"
        "Never ask for a characterId, asset id, project id, or workflow id. "
        "Resolve a character by name. If the name is missing or ambiguous, say so in plain language.\n"
        "When a tool result is already in the transcript, or no action is needed, set tool_id to null.\n"
        "If a tool result is proposed or not verified, say it is awaiting approval and not saved. "
        "Do not say it was set, added, placed, or created.\n"
        "Reply with one JSON object only: "
        '{"mode":"CONVERSATION","surface":"NONE","action":"","entities":{"characters":[],"props":[],"environments":[],"scenes":[]},'
        '"constraints":{"duration":null,"aspect_ratio":null,"no_execute":false},"confidence":"high",'
        '"reply":"...","tool_id":null,"arguments":{}}\n'
        f"Tools:\n{catalog}\n\nConversation:\n{transcript}"
    )
    try:
        from ..providers.base import ChatRequest
        from ..service import get_provider

        provider = get_provider(provider_id or None)
        generated = await provider.generate(
            ChatRequest(
                request_id=workflow_id,
                messages=[{"role": "user", "content": prompt}],
                model_id=model_id,
            )
        )
        reply = generated.reply or ""
    except Exception as exc:
        reply = f"I couldn't reach the selected model ({exc}). No project data was changed."
        return ModelResponse(parts=[TextPart(content=reply)])

    allowed = {tool.name for tool in info.function_tools}
    parsed = _parse_decision(reply)
    user_text = str(envelope.get("user_text") or _last_user_text(messages))
    hinted = str(envelope.get("turn_mode") or "CONVERSATION")
    if parsed is None or not str(parsed.get("tool_id") or ""):
        if hinted in {"PROPOSE", "MUTATE"}:
            retry = await _decision_retry(
                provider, workflow_id, model_id, catalog, user_text
            )
            parsed = _parse_decision(retry) or parsed
            if retry and not (parsed and parsed.get("tool_id")):
                reply = retry
    from .admission import resolve_admitted_tool
    from .authority import mode_allows_tool
    from ..tools.registry import find

    decision = resolve_admitted_tool(
        user_text,
        parsed,
        allowed=allowed,
        fallback=_operation_tool(user_text, allowed),
    )
    tool_id = str(decision.tool_id or "")
    if deps is not None:
        deps.envelope["turn_mode"] = decision.mode
    if tool_id and tool_id in allowed:
        try:
            definition = find(tool_id)
            kind = definition.kind
        except Exception:
            kind = ""
        if mode_allows_tool(decision.mode, kind=kind, tool_id=tool_id):
            return ModelResponse(parts=[ToolCallPart(tool_name=tool_id, args=decision.arguments or {})])
    text = decision.reply or (str(parsed.get("reply")) if parsed and parsed.get("reply") else reply)
    return ModelResponse(parts=[TextPart(content=text)])


def build_agent() -> Agent[TurnDeps, str]:
    model = FunctionModel(call_selected_provider, model_name="adept-selected-provider")
    return Agent(
        model,
        name=AGENT_NAME,
        deps_type=TurnDeps,
        instructions=SYSTEM_PROMPT,
        toolsets=[build_toolset()],
        capabilities=[DBOSDurability(parallel_execution_mode="sequential")],
        defer_model_check=True,
    )
