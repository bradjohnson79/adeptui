"""Honest failure classification and recovery policy (W6P-13 / W6P-14)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .schemas import RecoveryPolicy


@dataclass
class RecoveryAction:
    policy: RecoveryPolicy
    userMessage: str
    diagnosticCode: str
    retryAvailable: bool
    providerChangeAllowed: bool = False


def classify_failure(
    error: str | Exception | None,
    *,
    context: Optional[dict[str, Any]] = None,
) -> RecoveryAction:
    text = str(error or "").lower()
    ctx = context or {}
    code = str(ctx.get("code") or "")

    if "comfy" in text and ("unavailable" in text or "offline" in text or "connection" in text):
        return RecoveryAction(
            policy="wait_for_runtime",
            userMessage="The local render runtime is offline. Restore ComfyUI, then retry.",
            diagnosticCode="comfy_unavailable",
            retryAvailable=True,
        )
    if "oom" in text or "out of memory" in text or "vram" in text:
        return RecoveryAction(
            policy="retry_lower_profile",
            userMessage="GPU memory was insufficient. Retry with a lower quality profile, or free VRAM.",
            diagnosticCode="vram_insufficient",
            retryAvailable=True,
        )
    if "blocked" in text or code == "workflow_blocked":
        return RecoveryAction(
            policy="blocked_no_safe_fallback",
            userMessage="This workflow is blocked or not certified. No silent fallback is available.",
            diagnosticCode="workflow_blocked",
            retryAvailable=False,
        )
    if "model" in text and ("missing" in text or "not found" in text):
        return RecoveryAction(
            policy="request_missing_input",
            userMessage="A required model is missing. Install it via Source Manager, then retry.",
            diagnosticCode="model_missing",
            retryAvailable=True,
        )
    if "node" in text and ("missing" in text or "not found" in text):
        return RecoveryAction(
            policy="request_missing_input",
            userMessage="A required Comfy node is missing. Repair the runtime install, then retry.",
            diagnosticCode="node_missing",
            retryAvailable=True,
        )
    if "credential" in text or "api key" in text or "unauthorized" in text:
        return RecoveryAction(
            policy="request_user_approval",
            userMessage="Cloud credentials are unavailable. Configure credentials or stay on local providers.",
            diagnosticCode="cloud_credentials_missing",
            retryAvailable=False,
            providerChangeAllowed=False,
        )
    if "validation" in text or "output gate" in text:
        return RecoveryAction(
            policy="manual_review",
            userMessage="Output validation failed. The asset was retained for review — it was not silently discarded.",
            diagnosticCode="output_validation_failed",
            retryAvailable=True,
        )
    if "registration" in text:
        return RecoveryAction(
            policy="manual_review",
            userMessage="Asset registration failed after generation. Check diagnostics; do not assume success.",
            diagnosticCode="registration_failed",
            retryAvailable=True,
        )
    if "timeline" in text and ("place" in text or "stitch" in text):
        return RecoveryAction(
            policy="resume_from_completed_children",
            userMessage="Timeline placement or stitch failed. Completed child work is preserved for resume.",
            diagnosticCode="timeline_failure",
            retryAvailable=True,
        )
    if "cancel" in text and "timeout" in text:
        return RecoveryAction(
            policy="manual_review",
            userMessage="Cancellation confirmation timed out. Verify the runtime halted before retrying.",
            diagnosticCode="cancel_timeout",
            retryAvailable=False,
        )
    if "timeout" in text:
        return RecoveryAction(
            policy="retry_same",
            userMessage="The job timed out. You may retry the same certified workflow.",
            diagnosticCode="timeout",
            retryAvailable=True,
        )
    return RecoveryAction(
        policy="retry_same",
        userMessage="Production failed. Review diagnostics, then retry the same certified path — no uncertified fallback.",
        diagnosticCode="generic_failure",
        retryAvailable=True,
    )
