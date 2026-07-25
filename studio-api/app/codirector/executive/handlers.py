"""Mock job handlers for the Production Executive closed loop.

These simulate storyboard -> image -> validation -> proposal -> await approval -> apply canon.
They never auto-approve and never mutate Production Bible canon directly.
"""

from __future__ import annotations

from typing import Any

from .models import JobType
from .schemas import JobOut


class HandlerResult:
    def __init__(
        self,
        *,
        ok: bool,
        status: str,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        needs_review: bool = False,
    ) -> None:
        self.ok = ok
        self.status = status
        self.result = result or {}
        self.error = error
        self.needs_review = needs_review


def execute_job(job: JobOut) -> HandlerResult:
    """Run a single job attempt. Pure orchestration mock — no silent canon writes."""
    payload = dict(job.payload or {})
    if bool(payload.get("forceFail")):
        return HandlerResult(
            ok=False,
            status="Failed",
            error=str(payload.get("failMessage") or "forced failure"),
        )

    job_type = job.type
    if job_type == JobType.AWAIT_APPROVAL.value:
        if payload.get("proposalApproved") is True:
            return HandlerResult(
                ok=True,
                status="Completed",
                result={
                    "proposalId": payload.get("proposalId"),
                    "awaited": True,
                    "approvedExternally": True,
                },
            )
        return HandlerResult(
            ok=True,
            status="NeedsReview",
            needs_review=True,
            result={
                "proposalId": payload.get("proposalId"),
                "message": "Waiting for M2.2 Proposal -> Review -> Approval (not auto-approved)",
            },
        )

    if job_type == JobType.APPLY_CANON.value:
        if not payload.get("proposalApproved"):
            return HandlerResult(
                ok=False,
                status="Blocked",
                error="apply_canon blocked: proposal not approved (M2.2 gate)",
            )
        return HandlerResult(
            ok=True,
            status="Completed",
            result={
                "applied": False,
                "note": "Canon apply is scheduled only after explicit approval; handler records receipt stub without silent mutation.",
                "proposalId": payload.get("proposalId"),
                "receipt": f"receipt-{job.id[:8]}",
            },
        )

    if job_type == JobType.CREATE_PROPOSAL.value:
        proposal_id = payload.get("proposalId") or f"prop-{job.id[:8]}"
        return HandlerResult(
            ok=True,
            status="Completed",
            result={
                "proposalId": proposal_id,
                "status": "pending_review",
                "path": "M2.2 Proposal -> Review -> Approval",
            },
        )

    if job_type == JobType.VALIDATE.value:
        score = float(payload.get("score", 88))
        passed = score >= 80
        return HandlerResult(
            ok=True,
            status="Completed",
            result={
                "provider": job.provider or payload.get("provider") or "mock",
                "score": score,
                "passed": passed,
                "band": "approve" if passed else "corrections_required",
            },
        )

    if job_type == JobType.STORYBOARD_GENERATE.value:
        return HandlerResult(
            ok=True,
            status="Completed",
            result={
                "panels": payload.get("panels") or [{"id": "p1", "prompt": "mock panel"}],
                "provider": job.provider or "mock",
            },
        )

    if job_type == JobType.IMAGE_GENERATE.value:
        return HandlerResult(
            ok=True,
            status="Completed",
            result={
                "assetId": payload.get("assetId") or f"asset-{job.id[:8]}",
                "provider": job.provider or "mock",
            },
        )

    return HandlerResult(
        ok=True,
        status="Completed",
        result={"echo": payload, "type": job_type},
    )