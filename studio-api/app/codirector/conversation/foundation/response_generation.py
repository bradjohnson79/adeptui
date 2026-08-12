"""Build LLM generation inputs from DialoguePlan; deterministic fallback last resort."""

from __future__ import annotations

import re
from typing import Any

from .personality import default_personality, personality_guidance
from .schemas import (
    CoDirectorPersonality,
    ConversationState,
    DialoguePlan,
    IntentAnalysis,
    IntentType,
)

SYSTEM_PROMPT_VERSION = "codirector-foundation-response-v1"


def _compact_tool_catalog(curated_tool_ids: list[str]) -> str:
    """Render a compact tool catalog (name + parameters + purpose).

    Resolves the curated IDs through the closed tool registry and emits one
    line per tool. Unknown IDs are skipped — the catalog must never crash a
    turn because a curated ID drifted.
    """
    if not curated_tool_ids:
        return ""
    try:
        from ...tools import registry as tool_registry

        definitions = tool_registry.get_definitions(curated_tool_ids)
    except Exception:  # noqa: BLE001
        return ""
    if not definitions:
        return ""
    lines: list[str] = []
    for d in definitions:
        params = ", ".join(
            f"{p.name}{'?' if not p.required else ''}:{p.type}"
            for p in d.parameters
        )
        purpose = (d.description or "").strip().splitlines()[0][:140]
        lines.append(f"- {d.tool_id} ({d.kind}) [{params}] — {purpose}")
    return "\n".join(lines)


def _trim_messages_to_budget(
    messages: list[dict[str, str]], *, max_tokens: int | None
) -> list[dict[str, str]]:
    if not max_tokens or max_tokens <= 0:
        return messages
    from ..request_timing import estimate_tokens

    total = sum(estimate_tokens(m.get("content") or "") for m in messages)
    if total <= max_tokens:
        return messages
    # Keep system + latest user; drop oldest middle turns first.
    system = [m for m in messages if m.get("role") == "system"][:1]
    rest = [m for m in messages if m.get("role") != "system"]
    while rest and sum(estimate_tokens(m.get("content") or "") for m in system + rest) > max_tokens:
        if len(rest) <= 1:
            # Hard-trim system context block if still oversized.
            if system:
                content = system[0].get("content") or ""
                keep = max(800, max_tokens * 3)
                system[0] = {**system[0], "content": content[:keep]}
            break
        rest.pop(0)
    return [*system, *rest]


def build_generation_messages(
    *,
    user_message: str,
    intent: IntentAnalysis,
    plan: DialoguePlan,
    state: ConversationState,
    context_block: str,
    project_title: str,
    recent_messages: list[dict[str, Any]] | None = None,
    personality: CoDirectorPersonality | None = None,
    repair_notes: list[str] | None = None,
    max_context_tokens: int | None = None,
    curated_tool_ids: list[str] | None = None,
) -> list[dict[str, str]]:
    """Role-separated messages for the selected LLM.

    When ``curated_tool_ids`` is provided (Workstream B, dispatch ==
    CURATED_TOOLS), inject a compact tool catalog (name + parameters +
    purpose) into the system message so the model can emit ```` ```tool ````
    `` blocks. The catalog is intentionally compact — only the curated
    definitions, never the full registry.
    """

    personality = personality or default_personality()
    compact = bool(max_context_tokens and max_context_tokens <= 3000)
    # Bound context injection — full Wiki/Bible dumps must not land here.
    context_cap = 900 if compact else 6000
    bounded_context = (context_block or "")[:context_cap]
    if compact:
        # Prefill-sensitive path: keep warmth + plan, drop verbose dumps.
        system = "\n".join(
            [
                "You are Co-Director — a warm, attentive creative partner. Never sound canned or procedural.",
                "Follow the Dialogue Plan. Do not invent tools or facts. Specialists never speak for you.",
                f"Project: {project_title}",
                f"Intent: {intent.primary_intent.value} — {intent.user_goal_summary}",
                f"Purpose: {plan.response_purpose}",
                f"Posture: {', '.join(p.value for p in plan.posture)}",
                f"Question budget: {plan.question_budget}",
                "Required:",
                *[f"- {item}" for item in plan.required_elements[:4]],
                "Avoid:",
                *[f"- {item}" for item in plan.prohibited_elements[:4]],
                bounded_context,
            ]
        )
        history_n, history_chars = 2, 400
    else:
        system = "\n".join(
            [
                "You are Co-Director inside Adept UI — an attentive creative production partner.",
                "Generate a natural reply from the Dialogue Plan below. Do not invent tools or facts.",
                f"System prompt version: {SYSTEM_PROMPT_VERSION}",
                personality_guidance(personality),
                "",
                f"Project: {project_title}",
                f"Cognitive mode: {plan.mode.value}",
                f"Active goal: {state.active_goal or intent.user_goal_summary}",
                "",
                "=== Intent analysis ===",
                f"Primary: {intent.primary_intent.value}",
                f"Secondary: {', '.join(i.value for i in intent.secondary_intents) or '(none)'}",
                f"Goal summary: {intent.user_goal_summary}",
                f"Evidence: {'; '.join(intent.evidence_spans) or '(none)'}",
                "",
                "=== Dialogue plan (AUTHORITATIVE — do not contradict) ===",
                f"Purpose: {plan.response_purpose}",
                f"Posture: {', '.join(p.value for p in plan.posture)}",
                f"Question budget: {plan.question_budget}",
                f"Tool policy: {plan.tool_policy}",
                f"Memory policy: {plan.memory_policy}",
                f"Workflow advance: {plan.workflow_advance_policy}",
                "Required elements:",
                *[f"- {item}" for item in plan.required_elements[:8]],
                "Prohibited elements:",
                *[f"- {item}" for item in plan.prohibited_elements[:8]],
                "",
                bounded_context,
            ]
        )
        history_n, history_chars = 6, 1200
    if repair_notes:
        system += "\n\n=== Repair instructions (previous draft failed grounding) ===\n"
        system += "\n".join(f"- {n}" for n in repair_notes)
        system += "\nRewrite the reply so it satisfies the Dialogue Plan."

    # Compact curated tool catalog (Workstream B — CURATED_TOOLS dispatch).
    # Only the curated tool definitions land in the prompt, never the full
    # 485-tool registry. The model may emit ```tool blocks referencing these.
    if curated_tool_ids:
        catalog = _compact_tool_catalog(curated_tool_ids)
        if catalog:
            system += "\n\n=== Curated tool catalog ===\n"
            system += (
                "You may emit a tool call by writing a fenced ```tool block with "
                "a JSON object containing `toolId` and `parameters`. Only call "
                "tools listed below. Do not invent tool IDs.\n\n"
            )
            system += catalog

    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    for m in (recent_messages or [])[-history_n:]:
        role = str(m.get("role") or "user")
        if role not in {"user", "assistant", "system"}:
            role = "user"
        content = str(m.get("content") or "").strip()
        if content:
            messages.append({"role": role, "content": content[:history_chars]})
    # Ensure latest user message is last
    if not messages or messages[-1].get("role") != "user" or messages[-1].get("content") != user_message:
        messages.append({"role": "user", "content": user_message})
    return _trim_messages_to_budget(messages, max_tokens=max_context_tokens)


def _named_subject(user_message: str, project_title: str) -> str:
    """Best-effort subject label from message or project title (not a hard-coded canon)."""

    text = user_message or ""
    # Prefer quoted or "about X," style mentions without locking to one franchise.
    for pattern in (
        r"\ball about\s+([A-Z][\w'’\-]+(?:\s+[A-Z][\w'’\-]+){0,4})",
        r"\babout\s+(?:my\s+)?(?:web series|series|project|story)?[,]?\s*([A-Z][\w'’\-]+(?:\s+[A-Z][\w'’\-]+){0,4})",
        r"\b(?:series|project|story)\s+([A-Z][\w'’\-]+(?:\s+[A-Z][\w'’\-]+){0,3})",
    ):
        m = re.search(pattern, text)
        if m:
            candidate = m.group(1).strip(" .,;:")
            if candidate and candidate.lower() not in {"the", "a", "an", "my"}:
                return candidate
    title = (project_title or "").strip()
    if title and title.lower() not in {"untitled project", "the project"}:
        return title
    return "this project"


def deterministic_listening_fallback(
    *,
    user_message: str,
    intent: IntentAnalysis,
    plan: DialoguePlan,
    project_title: str,
) -> str:
    """Last-resort listening reply when LLM/generation/grounding fails."""

    subject = _named_subject(user_message, project_title)
    text = (user_message or "").strip()
    # INFORM / lore turns: acknowledge specifics instead of re-inviting an empty pitch.
    if intent.primary_intent == IntentType.INFORM and len(text) >= 40:
        snippet = re.sub(r"\s+", " ", text)[:180].rstrip(" .,;:")
        return (
            f"Thank you — I’m holding that. I’m tracking: {snippet}. "
            f"I’ll keep listening for story, character, world, tone, and continuity details about {subject} "
            f"without forcing a questionnaire or jumping into production."
        )
    return (
        f"Absolutely — that is the right place to begin. Before we plan scenes or production steps, "
        f"I want to understand what {subject} is, what makes it distinctive, and what you want the audience "
        f"to experience. Tell me about it in whatever order feels natural — no questionnaire. I’ll listen "
        f"closely and begin organizing important story, character, world, tone, and continuity details as "
        f"you share them."
    )
