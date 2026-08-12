"""Goal-ranked context assembly for listening / discovery turns."""

from __future__ import annotations

from typing import Any

from ..schemas import ProjectIntelligenceSnapshot
from .schemas import ConversationState, DialoguePlan, IntentAnalysis


def assemble_listening_context(
    *,
    snapshot: ProjectIntelligenceSnapshot,
    state: ConversationState,
    intent: IntentAnalysis,
    plan: DialoguePlan,
    recent_messages: list[dict[str, Any]] | None = None,
) -> str:
    """Assemble a compact, goal-appropriate context block (not full bible dumps)."""

    lines: list[str] = [
        "=== Active conversation context (ranked) ===",
        f"Project title: {snapshot.title or 'Untitled Project'}",
        f"Mode: {plan.mode.value}",
        f"Active goal: {state.active_goal or intent.user_goal_summary or '(none)'}",
        f"Workflow hold: {state.workflow_hold or plan.workflow_advance_policy == 'HOLD'}",
        f"Primary intent: {intent.primary_intent.value}",
    ]
    if intent.evidence_spans:
        lines.append("Intent evidence: " + " | ".join(intent.evidence_spans[:5]))
    if state.preference_explain_before_production:
        lines.append("Preference: explain story before production planning.")
    if snapshot.confirmedFacts:
        lines.append("Confirmed facts (top): " + "; ".join(snapshot.confirmedFacts[:4]))
    # Recent turns — last 6, truncated
    msgs = recent_messages or snapshot.recentMessages or []
    if msgs:
        lines.append("Recent messages:")
        for m in msgs[-6:]:
            role = str(m.get("role") or "user")
            content = str(m.get("content") or "").strip()
            if len(content) > 220:
                content = content[:217] + "..."
            lines.append(f"- {role}: {content}")
    lines.append(
        "Do NOT inject unrelated production jobs, full wiki dumps, or title/premise questionnaires."
    )
    return "\n".join(lines)


def estimate_tokens(text: str) -> int:
    return max(1, len(text or "") // 4)
