"""Deterministic Co-Director provider for E2E / offline tests."""

from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any, AsyncIterator

from app.codirector.errors import (
    CONNECTION_REFUSED,
    MODEL_NOT_FOUND,
    NO_MODELS_INSTALLED,
    REQUEST_TIMEOUT,
    CoDirectorError,
)
from app.codirector.providers.base import ChatRequest, ChatResult, ProviderHealthResult, ProviderModel


def _scenario() -> str:
    return (os.environ.get("ADEPT_CODIRECTOR_MOCK_SCENARIO") or "healthy").strip().lower()


# ---------------------------------------------------------------------------
# Scripted mode (test-only)
# ---------------------------------------------------------------------------
# A script is an ordered list of steps. When the ``scripted`` scenario is
# active AND a script is installed, ``generate`` matches the last user message
# against each step's ``match`` regex (first match wins) and emits the step's
# reply and/or a ```tool fence built from the step's tool spec. On follow-up
# turns (post-tool) the matched step's ``followUpReply`` is emitted if given,
# else a neutral prose acknowledgment. Unknown/missing script = ordinary chat
# reply (never silently emit fences). The store is module-level so the e2e
# router can install/clear it for the running process; it is unreachable when
# e2e is disabled because the e2e router itself is gated.

_SCRIPTED_STEPS: list[dict[str, Any]] = []


class ScriptValidationError(ValueError):
    """Raised when a scripted step fails validation on install."""


def _validate_scripted_step(step: Any) -> dict[str, Any]:
    if not isinstance(step, dict):
        raise ScriptValidationError(f"each step must be an object, got {type(step).__name__}")
    match = step.get("match")
    if not isinstance(match, str) or not match:
        raise ScriptValidationError("step.match must be a non-empty regex string")
    try:
        re.compile(match)
    except re.error as exc:
        raise ScriptValidationError(f"step.match regex is invalid: {exc}") from exc
    reply = step.get("reply")
    if reply is not None and not isinstance(reply, str):
        raise ScriptValidationError("step.reply must be a string when provided")
    follow_up = step.get("followUpReply")
    if follow_up is not None and not isinstance(follow_up, str):
        raise ScriptValidationError("step.followUpReply must be a string when provided")
    tool = step.get("tool")
    if tool is not None:
        if not isinstance(tool, dict):
            raise ScriptValidationError("step.tool must be an object when provided")
        tool_id = tool.get("toolId")
        if not isinstance(tool_id, str) or not tool_id.strip():
            raise ScriptValidationError("step.tool.toolId must be a non-empty string")
        arguments = tool.get("arguments")
        if not isinstance(arguments, dict):
            raise ScriptValidationError("step.tool.arguments must be an object")
        response_type = tool.get("responseType")
        if response_type is not None and not isinstance(response_type, str):
            raise ScriptValidationError("step.tool.responseType must be a string when provided")
    return step


def set_scripted_steps(steps: list[dict[str, Any]] | None) -> int:
    """Install a validated script for the ``scripted`` scenario.

    Returns the number of installed steps. Passing ``None`` or an empty list
    clears the script (equivalent to ``clear_scripted_steps``).
    """

    if not steps:
        _SCRIPTED_STEPS.clear()
        return 0
    if not isinstance(steps, list):
        raise ScriptValidationError(f"steps must be a list, got {type(steps).__name__}")
    validated = [_validate_scripted_step(step) for step in steps]
    _SCRIPTED_STEPS.clear()
    _SCRIPTED_STEPS.extend(validated)
    return len(_SCRIPTED_STEPS)


def clear_scripted_steps() -> None:
    _SCRIPTED_STEPS.clear()


def get_scripted_steps() -> list[dict[str, Any]]:
    return [dict(step) for step in _SCRIPTED_STEPS]


def _scripted_reply(request: ChatRequest) -> str | None:
    """Return the scripted reply for the last user message, or None to fall through."""

    if not _SCRIPTED_STEPS:
        return None
    user_messages = [m for m in request.messages if m.get("role") == "user"]
    follow_up = _is_follow_up_turn(request)
    if follow_up:
        # On a follow-up turn the last user message is the tool result, not the
        # original request — re-derive the matched step from the original (first)
        # user message so the followUpReply stays tied to the request that started
        # the tool loop.
        target = ((user_messages[0].get("content") or "").strip() if user_messages else "")
    else:
        target = ((user_messages[-1].get("content") or "").strip() if user_messages else "")
    for step in _SCRIPTED_STEPS:
        if re.search(step["match"], target):
            if follow_up:
                fu = step.get("followUpReply")
                if fu:
                    return fu
                return "[mock-scripted] Noted — moving on from that lookup."
            parts: list[str] = []
            reply = step.get("reply")
            if reply:
                parts.append(reply)
            tool = step.get("tool")
            if tool is not None:
                response_type = tool.get("responseType") or "read_tool_call"
                parts.append(_tool_fence(response_type, tool["toolId"], tool.get("arguments") or {}))
            if not parts:
                return "[mock-scripted] (scripted step matched but emitted nothing.)"
            return "\n\n".join(parts)
    return None


# Scenarios that exercise the M2.2 tool registry. Kept explicit so an unknown scenario name
# falls through to the ordinary chat reply instead of silently emitting a tool fence.
_TOOL_SCENARIOS = frozenset(
    {
        "read_tool_success",
        "read_tool_blocked_capability",
        "capability_not_configured",
        "mutation_tool_proposal",
        "mutation_tool_stale",
        "mutation_tool_execution_success",
        "mutation_tool_execution_failure",
        "tool_loop_limit",
        "intelligence_storyboard",
        "intelligence_simple_qa",
        # c2-routing: audited-write routing drift regression scenarios. Each
        # emits a fence for one of the four audited (requires_approval=False)
        # mutating tools so the chat path can be proven to route via
        # execute_audited (tool_completed/tool_failed) instead of being
        # silently re-gated as an approval proposal (tool_proposal_created).
        "audited_create_draft",
        "audited_audio_cancel",
        "audited_minimax_fallback",
        "audited_minimax_cancel",
    }
)


def _tool_fence(response_type: str, tool_id: str, arguments: dict[str, Any] | None = None) -> str:
    return (
        "```tool\n"
        + json.dumps({"responseType": response_type, "toolId": tool_id, "arguments": arguments or {}})
        + "\n```"
    )


def _is_follow_up_turn(request: ChatRequest) -> bool:
    """True when this turn is the follow-up after a tool ran.

    The gateway appends the tool's outcome as the last user message, so a real model would see
    it and answer in prose. The mock mirrors that so E2E scenarios terminate after one tool
    instead of re-requesting the same tool forever.
    """

    for message in reversed(request.messages):
        if message.get("role") == "user":
            content = message.get("content") or ""
            return "Tool result for" in content or "could not run" in content
    return False


class MockCoDirectorProvider:
    id = "mock"
    display_name = "Mock Co-Director"

    def __init__(self) -> None:
        self.endpoint = "mock://codirector"

    async def list_models(self) -> list[ProviderModel]:
        scenario = _scenario()
        if scenario in ("no_models", "connection_refused"):
            return []
        return [
            ProviderModel(
                id="mock-model",
                name="mock-model",
                size_bytes=1_000_000,
                family="mock",
                parameter_size="1B",
                quantization="Q4",
            ),
            ProviderModel(
                id="mock-vision",
                name="mock-vision",
                size_bytes=2_000_000,
                family="mock",
                parameter_size="2B",
            ),
        ]

    async def health(self) -> ProviderHealthResult:
        scenario = _scenario()
        models = await self.list_models()
        selected = "mock-model"
        # Always mark mock health as test-only so UI never treats it as production Ready.
        mock_flags = {"test_only": True, "honesty": "mocked"}

        if scenario == "connection_refused":
            return ProviderHealthResult(
                provider_id=self.id,
                display_name=self.display_name,
                status="Not Running",
                reachable=False,
                endpoint=self.endpoint,
                selected_model=selected,
                model_available=False,
                models=[],
                message="Co-Director could not reach the mock provider (simulated connection refused).",
                code=CONNECTION_REFUSED,
                recommended_action="retry_or_check_service",
                **mock_flags,
            )
        if scenario == "no_models":
            return ProviderHealthResult(
                provider_id=self.id,
                display_name=self.display_name,
                status="No Models",
                reachable=True,
                endpoint=self.endpoint,
                selected_model=None,
                model_available=False,
                models=[],
                message="Provider is running, but no compatible models are installed.",
                code=NO_MODELS_INSTALLED,
                recommended_action="install_or_select_model",
                **mock_flags,
            )
        if scenario == "model_missing":
            return ProviderHealthResult(
                provider_id=self.id,
                display_name=self.display_name,
                status="Model Missing",
                reachable=True,
                endpoint=self.endpoint,
                selected_model="missing-model",
                model_available=False,
                models=models,
                message="The selected model 'missing-model' is not installed.",
                code=MODEL_NOT_FOUND,
                recommended_action="select_model",
                **mock_flags,
            )
        return ProviderHealthResult(
            provider_id=self.id,
            display_name=self.display_name,
            status="Ready",
            reachable=True,
            endpoint=self.endpoint,
            selected_model=selected,
            model_available=True,
            models=models,
            message="Mock Co-Director is ready (test-only).",
            **mock_flags,
        )

    async def generate(self, request: ChatRequest) -> ChatResult:
        scenario = _scenario()
        if scenario == "connection_refused":
            raise CoDirectorError(
                CONNECTION_REFUSED,
                "Co-Director could not reach Ollama at mock://codirector.",
                details={"provider": "mock", "endpoint": self.endpoint},
                recommended_action="retry_or_check_service",
            )
        if scenario == "timeout":
            await asyncio.sleep(0.05)
            raise CoDirectorError(
                REQUEST_TIMEOUT,
                "The model took too long to respond. You can retry or choose another model.",
                details={"provider": "mock"},
                recommended_action="retry",
            )
        if scenario == "no_models":
            raise CoDirectorError(
                NO_MODELS_INSTALLED,
                "Provider is running, but no compatible models are installed.",
                details={"provider": "mock"},
                recommended_action="install_or_select_model",
            )
        if scenario == "model_missing":
            raise CoDirectorError(
                MODEL_NOT_FOUND,
                "The selected model is not installed. Choose an available model in Co-Director Options.",
                details={"provider": "mock", "model": request.model_id or "missing-model"},
                recommended_action="select_model",
            )

        model = request.model_id or "mock-model"
        models = {m.id for m in await self.list_models()}
        if model not in models:
            raise CoDirectorError(
                MODEL_NOT_FOUND,
                f"The selected model '{model}' is not installed.",
                details={"provider": "mock", "model": model},
                recommended_action="select_model",
            )

        # Scripted scenario: emit a script-driven reply/fence when a script is
        # installed; otherwise fall through to the ordinary chat reply so an
        # unknown/missing script never silently emits a tool fence.
        if scenario == "scripted":
            scripted = _scripted_reply(request)
            if scripted is not None:
                if scenario == "slow":
                    await asyncio.sleep(0.35)
                return ChatResult(
                    request_id=request.request_id,
                    reply=scripted,
                    model_id=model,
                    provider_id=self.id,
                    raw={"mock": True, "scenario": scenario, "scripted": True},
                )

        last_user = ""
        for m in reversed(request.messages):
            if m.get("role") == "user":
                last_user = (m.get("content") or "").strip()
                break

        reply = (
            f"[mock] Co-Director received your note about: {last_user[:160] or '(empty)'}. "
            "I can help with scene planning, prompt writing, or a short screenplay outline."
        )
        if "script" in last_user.lower():
            reply = (
                "[mock] To write a script here: start a scene, define characters, "
                "outline acts, then draft in screenplay format. Want me to start an outline?"
            )

        if scenario == "proposal_character_update":
            reply = (
                "[mock] Based on this scene, I'd like to update the character's established "
                "appearance in the Production Bible. Review the proposal below before it's "
                "applied — nothing changes until you approve it.\n\n"
                "```proposal\n"
                + json.dumps(
                    {
                        "proposalType": "entity_update",
                        "title": "Update Ava's appearance",
                        "summary": "Add a scar detail established in this scene to Ava's character entry.",
                        "entityMutations": [
                            {
                                "entityType": "character",
                                "entityKey": "ava",
                                "displayName": "Ava",
                                # Field names must match CharacterData exactly: it forbids
                                # extras, so an invented key ("appearance") makes the whole
                                # approval fail at apply time instead of at parse time.
                                "data": {
                                    "description": "Protagonist, mid-20s, short dark hair.",
                                    "appearanceSummary": (
                                        "Has a small scar above her left eyebrow, "
                                        "established in this scene."
                                    ),
                                    "distinguishingFeatures": "Small scar above the left eyebrow.",
                                },
                            }
                        ],
                        "factMutations": [],
                        "changeReason": "Continuity detail introduced in chat",
                    }
                )
                + "\n```"
            )
        elif scenario == "malformed_proposal":
            reply = (
                "[mock] I want to propose a Bible update, but this response is intentionally "
                "broken for testing.\n\n```proposal\n{ this is not valid json,,, \n```"
            )
        elif scenario == "intelligence_simple_qa":
            reply = (
                "[mock-intelligence] A standard project uses scenes on the timeline, assets for "
                "references, and the Production Bible for locked continuity."
            )
        elif scenario == "intelligence_storyboard":
            reply = (
                "[mock-intelligence] Use a locked medium two-shot with subtle movement. "
                "Primary character references and corridor architecture should drive the frame."
            )
        else:
            reply = self._tool_scenario_reply(scenario, request) or reply

        if scenario == "slow":
            await asyncio.sleep(0.35)

        return ChatResult(
            request_id=request.request_id,
            reply=reply,
            model_id=model,
            provider_id=self.id,
            raw={"mock": True, "scenario": scenario},
        )

    def _tool_scenario_reply(self, scenario: str, request: ChatRequest) -> str | None:
        """Deterministic replies for the M2.2 tool scenarios.

        Each scenario models one contractual behavior of the registry rather than a happy path:
        a read tool that succeeds, one blocked by a missing capability, a mutating tool that
        must become a proposal, and a model that ignores the one-tool-per-turn bound.
        """

        if scenario not in _TOOL_SCENARIOS:
            return None

        follow_up = _is_follow_up_turn(request)

        if scenario == "tool_loop_limit":
            # Deliberately keeps asking, including on the follow-up turn, so the gateway's bound
            # is what stops it.
            return (
                "[mock] Let me check the project's scenes.\n\n"
                + _tool_fence("read_tool_call", "list_scenes", {})
            )

        if follow_up:
            return (
                "[mock] Based on that lookup, here's what I found: the project is set up and I "
                "can keep going from here."
            )

        if scenario == "read_tool_success":
            return (
                "[mock] Let me check the current scene list before I answer.\n\n"
                + _tool_fence("read_tool_call", "list_scenes", {"limit": 10})
            )
        if scenario in ("read_tool_blocked_capability", "capability_not_configured"):
            tool_id = "get_comfyui_health" if scenario == "read_tool_blocked_capability" else "get_reference_capabilities"
            return (
                "[mock] Let me check whether the render backend is ready.\n\n"
                + _tool_fence("read_tool_call", tool_id, {})
            )
        if scenario in (
            "mutation_tool_proposal",
            "mutation_tool_stale",
            "mutation_tool_execution_success",
            "mutation_tool_execution_failure",
        ):
            return (
                "[mock] I'd like to add a scene for that beat. Nothing changes until you "
                "approve it.\n\n"
                + _tool_fence(
                    "mutation_proposal",
                    "create_scene",
                    {"name": "Rooftop Standoff", "prompt": "Slow push-in on the rooftop at dusk.", "durationSec": 6.0},
                )
            )
        # c2-routing: audited-write scenarios. These emit a mutation_proposal
        # fence whose tool is an audited (requires_approval=False) mutating tool.
        # The chat path must route them through execute_audited (immediate execute)
        # rather than re-gating them as an approval proposal.
        if scenario == "audited_create_draft":
            return (
                "[mock] I'll draft a production plan now. This creates an unapproved draft only.\n\n"
                + _tool_fence(
                    "mutation_proposal",
                    "production_plan.create_draft",
                    {"title": "Mock Draft", "objective": "Exercise the audited routing path."},
                )
            )
        if scenario == "audited_audio_cancel":
            return (
                "[mock] I'll cancel the audio batch now.\n\n"
                + _tool_fence("mutation_proposal", "audio.cancel_batch", {"batchId": "mock-batch"})
            )
        if scenario == "audited_minimax_fallback":
            return (
                "[mock] I'll offer the LTX fallback for the MiniMax H3 plan.\n\n"
                + _tool_fence(
                    "mutation_proposal", "minimax_h3.offer_ltx_fallback", {"planId": "mock-plan"}
                )
            )
        if scenario == "audited_minimax_cancel":
            return (
                "[mock] I'll cancel the MiniMax H3 request now.\n\n"
                + _tool_fence("mutation_proposal", "minimax_h3.cancel", {"requestId": "mock-req"})
            )
        return None

    def supports_stream(self) -> bool:
        return True

    async def stream(self, request: ChatRequest) -> AsyncIterator[dict[str, Any]]:
        result = await self.generate(request)
        yield {"type": "request_started", "requestId": request.request_id}
        yield {"type": "provider_connected", "requestId": request.request_id, "providerId": self.id}
        # Tokenize roughly by words for Playwright incremental rendering
        parts = result.reply.split(" ")
        buf = ""
        for i, part in enumerate(parts):
            piece = part if i == 0 else f" {part}"
            buf += piece
            yield {"type": "token", "requestId": request.request_id, "content": piece}
            if _scenario() == "slow":
                await asyncio.sleep(0.05)
        yield {
            "type": "completed",
            "requestId": request.request_id,
            "content": result.reply,
            "modelId": result.model_id,
            "providerId": self.id,
        }
