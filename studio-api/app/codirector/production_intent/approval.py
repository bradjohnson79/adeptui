"""Approval, cost, and safety policy for production actions (W6P-4)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .schemas import ApprovalPolicyState, ProductionIntent


HIGH_COST_OPS = frozenset(
    {
        "video.batch_timeline",
        "video.timeline_render",
        "video.scene_render",
        "asset.replace",
    }
)
IDENTITY_SENSITIVE = frozenset({"voice.generate", "video.lipsync"})


@dataclass
class ApprovalPolicy:
    state: ApprovalPolicyState
    required: bool
    reasons: list[str]
    disclosure: dict[str, Any]


def evaluate_approval_requirement(
    intent: ProductionIntent,
    *,
    replaces_approved_asset: bool = False,
    batch_count: int = 1,
    cloud_paid: bool = False,
    high_vram: bool = True,
) -> ApprovalPolicy:
    reasons: list[str] = []
    if cloud_paid:
        reasons.append("Paid cloud generation requires explicit confirmation.")
    if intent.operation in HIGH_COST_OPS or batch_count > 1:
        reasons.append("Batch or project-wide render requires confirmation.")
    if replaces_approved_asset or intent.operation == "asset.replace":
        reasons.append("Replacing an approved asset requires confirmation.")
    if intent.operation == "video.batch_timeline":
        reasons.append("Timeline rebuild / batch may overwrite incomplete placements.")
    if intent.operation in IDENTITY_SENSITIVE:
        reasons.append("Identity-sensitive audio / lipsync requires confirmation.")
    if high_vram and intent.modality == "video":
        reasons.append("High-VRAM / long-running local job requires confirmation.")
    # Mutating media always goes through proposal bus; mark awaiting when reasons exist
    # or when tool registry requires approval (default for mutating tools).
    required = True
    if intent.operation in {"job.cancel"} and not cloud_paid:
        required = True
        reasons = reasons or ["Cancellation of an active production job requires confirmation."]
    state: ApprovalPolicyState = "awaiting_approval" if required else "not_required"
    disclosure = build_disclosure(intent, reasons=reasons, cloud_paid=cloud_paid, batch_count=batch_count)
    return ApprovalPolicy(state=state, required=required, reasons=reasons, disclosure=disclosure)


def build_disclosure(
    intent: ProductionIntent,
    *,
    reasons: Optional[list[str]] = None,
    cloud_paid: bool = False,
    batch_count: int = 1,
    contract: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    contract = contract or {}
    provider = "cloud" if cloud_paid else "local"
    return {
        "intentId": intent.intentId,
        "intendedAction": intent.operation,
        "objective": intent.objective or intent.prompt,
        "capability": intent.workflowPreference
        or contract.get("workflow_key")
        or contract.get("workflowKey")
        or intent.operation,
        "provider": provider,
        "engine": intent.enginePreference or contract.get("engine") or "minimax-h3",
        "expectedOutputs": list(
            (intent.outputRequirements or {}).get("kinds")
            or ([intent.modality] if intent.modality else [])
        ),
        "jobScope": {
            "sceneId": intent.sceneId,
            "shotId": intent.shotId,
            "batchCount": batch_count,
            "duration": intent.duration,
            "qualityProfile": intent.qualityProfile,
        },
        "replacesExistingAsset": bool(
            intent.operation in {"asset.replace", "editor.place"}
            and intent.sourceAssets
        ),
        "mayConsumeCredits": cloud_paid,
        "reasons": list(reasons or []),
        "workflowId": contract.get("workflow_id") or contract.get("workflowId"),
        "workflowVersion": contract.get("workflow_version") or contract.get("workflowVersion"),
    }
