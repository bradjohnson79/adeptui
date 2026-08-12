"""M3.0h local-first routing helpers.

Priority: installed local provider → selected local model → compatible alternate local
→ explicit paid fal fallback only (never silent).
"""

from __future__ import annotations

import json
from typing import Any

from .fal_catalog import is_fal_engine

LOCAL_I2V_ENGINES = frozenset({"ltx", "wan"})
LOCAL_START_FRAME_REQUIRED = "LOCAL_START_FRAME_REQUIRED"
PAID_FAL_APPROVAL_REQUIRED = "PAID_FAL_APPROVAL_REQUIRED"
LOCAL_RUNTIME_BLOCKED = "LOCAL_RUNTIME_BLOCKED"


def paid_fallback_approved(params: dict[str, Any] | None) -> bool:
    if not params:
        return False
    return bool(
        params.get("paidFallbackApproved")
        or params.get("paid_fallback_approved")
        or params.get("allowPaidFal")
    )


def provider_prefers_local(params: dict[str, Any] | None) -> bool:
    """Default is local-first unless the caller explicitly requests cloud."""
    if not params:
        return True
    pref = str(params.get("providerPreference") or params.get("provider_preference") or "local").lower()
    if pref in ("cloud", "fal", "paid"):
        return False
    return True


def local_start_frame_blocker(*, preferred_engine: str = "ltx") -> dict[str, Any]:
    return {
        "code": LOCAL_START_FRAME_REQUIRED,
        "message": (
            f"Local engine '{preferred_engine}' is image-to-video and requires a start frame. "
            "Generate a local start frame and continue, or approve paid fal.ai fallback."
        ),
        "preferredAction": "generate_local_start_frame",
        "actions": [
            {
                "id": "generate_local_start_frame",
                "label": "Generate local start frame and continue",
                "preferred": True,
            },
            {
                "id": "approve_paid_fal_fallback",
                "label": "Use paid fal.ai text-to-video (requires approval)",
                "preferred": False,
                "requiresPaidApproval": True,
            },
        ],
        "falSubmissionAllowedWithoutApproval": False,
    }


def paid_fal_approval_blocker(*, engine: str) -> dict[str, Any]:
    return {
        "code": PAID_FAL_APPROVAL_REQUIRED,
        "message": (
            f"Cloud engine '{engine}' bills through fal.ai. "
            "Confirm paid fallback before Studio submits a request."
        ),
        "preferredAction": "try_local_alternatives",
        "actions": [
            {
                "id": "try_local_alternatives",
                "label": "Try compatible local models first",
                "preferred": True,
            },
            {
                "id": "approve_paid_fal_fallback",
                "label": "Approve paid fal.ai submission",
                "preferred": False,
                "requiresPaidApproval": True,
            },
        ],
        "falSubmissionAllowedWithoutApproval": False,
    }


def assert_fal_allowed(params: dict[str, Any] | None, *, engine: str) -> None:
    """Raise RuntimeError with structured JSON when fal would submit without approval."""
    if paid_fallback_approved(params):
        return
    blocker = paid_fal_approval_blocker(engine=engine)
    raise RuntimeError(json.dumps(blocker))


def local_first_provenance(
    *,
    start_frame_provider: str | None = None,
    start_frame_model: str | None = None,
    video_provider: str = "comfyui",
    video_model: str = "ltx-2.3",
    paid_provider_used: bool = False,
    fal_request_id: str | None = None,
    historical_fal_submission_count: int = 1,
    m30h_local_certification_fal_submission_count: int = 0,
    current_job_fal_submission_count: int = 0,
) -> dict[str, Any]:
    return {
        "providerClass": "local" if not paid_provider_used else "cloud",
        "startFrameProvider": start_frame_provider,
        "startFrameModel": start_frame_model,
        "videoProvider": video_provider,
        "videoModel": video_model,
        "paidProviderUsed": paid_provider_used,
        "historicalFalSubmissionCount": historical_fal_submission_count,
        "m30hLocalCertificationFalSubmissionCount": m30h_local_certification_fal_submission_count,
        "currentJobFalSubmissionCount": current_job_fal_submission_count,
        "falRequestId": fal_request_id,
    }


def resolve_local_video_engine(preferred: str | None = None) -> str:
    eng = (preferred or "minimax-h3").strip().lower()
    if eng in LOCAL_I2V_ENGINES:
        return eng
    if is_fal_engine(eng):
        return "ltx"
    return "ltx"
