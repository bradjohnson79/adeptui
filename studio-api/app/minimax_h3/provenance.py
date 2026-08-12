"""Provenance helpers for MiniMax H3 planning receipts."""

from __future__ import annotations

from .contracts import H3GenerationPlan, utc_now


def build_receipt(
    plan: H3GenerationPlan,
    *,
    approval_id: str | None = None,
    fallback_status: str = "not_requested",
) -> dict[str, object]:
    return {
        "capturedAt": utc_now(),
        "model": "minimax-h3",
        "lane": plan.deployment,
        "strategy": plan.threeFramePlan.strategy if plan.threeFramePlan else None,
        "frameRoles": [item.role for item in plan.referenceAssignments],
        "approvalId": approval_id,
        "fallbackStatus": fallback_status,
    }
