"""Typed contracts for Production Executive closed-loop job handlers.

Each JobType defines input/output schemas, required capabilities, retry
classification, idempotency, cancellation behavior, and audit metadata.
Handlers validate payloads at their boundary via ``validate_job_input``.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from .models import JOB_TYPE_CAPABILITIES, JobType


class RetryClass(str, Enum):
    """How failures should be classified for retry budgeting."""

    TRANSIENT = "transient"  # network/provider blip — retry
    PERMANENT = "permanent"  # bad input / policy — do not burn attempts blindly
    NEEDS_HUMAN = "needs_human"  # approval / review gate
    NONE = "none"  # terminal by design


class CancellationBehavior(str, Enum):
    COOPERATIVE = "cooperative"  # stop before next side effect; leave partial artifacts
    IMMEDIATE = "immediate"  # mark cancelled; do not start downstream work
    FORBIDDEN_WHEN_RUNNING = "forbidden_when_running"  # reject cancel once side effects started


class JobContract(BaseModel):
    job_type: JobType
    required_capabilities: list[str] = Field(default_factory=list)
    retry_class: RetryClass = RetryClass.TRANSIENT
    idempotency_key_fields: list[str] = Field(default_factory=list)
    cancellation: CancellationBehavior = CancellationBehavior.COOPERATIVE
    audit_event_prefix: str = "executive.job"
    description: str = ""


# --- Input / output schemas per closed-loop type ---


class StoryboardGenerateInput(BaseModel):
    projectId: str
    sceneId: Optional[str] = None
    panelId: Optional[str] = None
    segmentId: Optional[str] = None
    style: Optional[str] = None
    prompt: Optional[str] = None
    provider: Optional[str] = None


class StoryboardGenerateOutput(BaseModel):
    panelId: str
    imageJobId: str
    segmentId: Optional[str] = None
    status: str = "generating"
    provider: Optional[str] = None


class ImageGenerateInput(BaseModel):
    projectId: str
    sceneId: Optional[str] = None
    panelId: Optional[str] = None
    imageJobId: Optional[str] = None
    prompt: Optional[str] = None
    provider: Optional[str] = None
    assetId: Optional[str] = None  # if already produced (idempotent resume)


class ImageGenerateOutput(BaseModel):
    assetId: str
    imageJobId: str
    panelId: Optional[str] = None
    provider: str = "comfy"
    mockAdapter: bool = False


class ValidateInput(BaseModel):
    projectId: str
    assetId: Optional[str] = None
    sceneId: Optional[str] = None
    planId: Optional[str] = None
    timelineItemId: Optional[str] = None
    provider: str = "local"
    fixtureProfile: Optional[str] = None
    referenceAssetId: Optional[str] = None


class ValidateOutput(BaseModel):
    sessionId: str
    reportId: str
    score: float = 0.0
    passed: bool = False
    band: str = "correction-required"
    provider: str = "local"
    # visualValidationPending is cleared only by M2.5 VisionEngine when planId is set.
    visualValidationPendingCleared: bool = False


class CreateProposalInput(BaseModel):
    projectId: str
    sceneId: Optional[str] = None
    assetId: Optional[str] = None
    sessionId: Optional[str] = None
    reportId: Optional[str] = None
    score: Optional[float] = None
    passed: Optional[bool] = None
    proposalId: Optional[str] = None  # idempotent reuse


class CreateProposalOutput(BaseModel):
    proposalId: str
    status: str = "pending"
    path: str = "M2.2 Proposal → Review → Approval"


class AwaitApprovalInput(BaseModel):
    projectId: str
    proposalId: str
    proposalApproved: bool = False


class AwaitApprovalOutput(BaseModel):
    proposalId: str
    awaited: bool = True
    approvedExternally: bool = False
    proposalStatus: Optional[str] = None
    message: str = "Waiting for M2.2 Proposal → Review → Approval (not auto-approved)"


class ApplyCanonInput(BaseModel):
    projectId: str
    proposalId: str
    proposalApproved: bool = False


class ApplyCanonOutput(BaseModel):
    proposalId: str
    applied: bool = False
    receiptId: Optional[str] = None
    resultingVersionId: Optional[str] = None
    notes: str = ""


CONTRACTS: dict[str, JobContract] = {
    JobType.STORYBOARD_GENERATE.value: JobContract(
        job_type=JobType.STORYBOARD_GENERATE,
        required_capabilities=list(
            JOB_TYPE_CAPABILITIES.get(JobType.STORYBOARD_GENERATE.value, [])
        ),
        retry_class=RetryClass.TRANSIENT,
        idempotency_key_fields=["projectId", "sceneId", "panelId", "segmentId"],
        cancellation=CancellationBehavior.COOPERATIVE,
        audit_event_prefix="executive.storyboard_generate",
        description="Create/update storyboard panel and enqueue ImageGen job.",
    ),
    JobType.IMAGE_GENERATE.value: JobContract(
        job_type=JobType.IMAGE_GENERATE,
        required_capabilities=list(JOB_TYPE_CAPABILITIES.get(JobType.IMAGE_GENERATE.value, [])),
        retry_class=RetryClass.TRANSIENT,
        idempotency_key_fields=["projectId", "panelId", "imageJobId"],
        cancellation=CancellationBehavior.COOPERATIVE,
        audit_event_prefix="executive.image_generate",
        description="Enqueue/poll ImageGen Job until done; record assetId via Job+Asset lifecycle.",
    ),
    JobType.VALIDATE.value: JobContract(
        job_type=JobType.VALIDATE,
        required_capabilities=list(JOB_TYPE_CAPABILITIES.get(JobType.VALIDATE.value, [])),
        retry_class=RetryClass.TRANSIENT,
        idempotency_key_fields=["projectId", "assetId", "planId"],
        cancellation=CancellationBehavior.IMMEDIATE,
        audit_event_prefix="executive.validate",
        description="Run M2.5 vision validation; never clears visualValidationPending except via planId→VisionEngine.",
    ),
    JobType.CREATE_PROPOSAL.value: JobContract(
        job_type=JobType.CREATE_PROPOSAL,
        required_capabilities=list(
            JOB_TYPE_CAPABILITIES.get(JobType.CREATE_PROPOSAL.value, [])
        ),
        retry_class=RetryClass.PERMANENT,
        idempotency_key_fields=["projectId", "sceneId", "assetId", "sessionId"],
        cancellation=CancellationBehavior.IMMEDIATE,
        audit_event_prefix="executive.create_proposal",
        description="Create real M2.2 proposal via ProposalService (never auto-approve).",
    ),
    JobType.AWAIT_APPROVAL.value: JobContract(
        job_type=JobType.AWAIT_APPROVAL,
        required_capabilities=list(JOB_TYPE_CAPABILITIES.get(JobType.AWAIT_APPROVAL.value, [])),
        retry_class=RetryClass.NEEDS_HUMAN,
        idempotency_key_fields=["projectId", "proposalId"],
        cancellation=CancellationBehavior.IMMEDIATE,
        audit_event_prefix="executive.await_approval",
        description="NeedsReview until M2.2 approval/rejection; Executive never auto-approves.",
    ),
    JobType.APPLY_CANON.value: JobContract(
        job_type=JobType.APPLY_CANON,
        required_capabilities=list(JOB_TYPE_CAPABILITIES.get(JobType.APPLY_CANON.value, [])),
        retry_class=RetryClass.PERMANENT,
        idempotency_key_fields=["projectId", "proposalId"],
        cancellation=CancellationBehavior.FORBIDDEN_WHEN_RUNNING,
        audit_event_prefix="executive.apply_canon",
        description="Apply canon only via approved ProposalService.approve path (idempotent).",
    ),
}

INPUT_MODELS: dict[str, type[BaseModel]] = {
    JobType.STORYBOARD_GENERATE.value: StoryboardGenerateInput,
    JobType.IMAGE_GENERATE.value: ImageGenerateInput,
    JobType.VALIDATE.value: ValidateInput,
    JobType.CREATE_PROPOSAL.value: CreateProposalInput,
    JobType.AWAIT_APPROVAL.value: AwaitApprovalInput,
    JobType.APPLY_CANON.value: ApplyCanonInput,
}

OUTPUT_MODELS: dict[str, type[BaseModel]] = {
    JobType.STORYBOARD_GENERATE.value: StoryboardGenerateOutput,
    JobType.IMAGE_GENERATE.value: ImageGenerateOutput,
    JobType.VALIDATE.value: ValidateOutput,
    JobType.CREATE_PROPOSAL.value: CreateProposalOutput,
    JobType.AWAIT_APPROVAL.value: AwaitApprovalOutput,
    JobType.APPLY_CANON.value: ApplyCanonOutput,
}


def get_contract(job_type: str) -> JobContract | None:
    return CONTRACTS.get(job_type)


def validate_job_input(job_type: str, payload: dict[str, Any], *, project_id: str) -> BaseModel:
    """Validate handler input at the boundary. Raises ValueError on contract failure."""
    model = INPUT_MODELS.get(job_type)
    if model is None:
        # generic / unknown types — pass-through envelope
        return BaseModel.model_construct()
    data = dict(payload or {})
    data.setdefault("projectId", project_id)
    try:
        return model.model_validate(data)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"invalid {job_type} input: {exc}") from exc


def validate_job_output(job_type: str, result: dict[str, Any]) -> dict[str, Any]:
    """Validate handler output; return normalized dict."""
    model = OUTPUT_MODELS.get(job_type)
    if model is None:
        return dict(result or {})
    return model.model_validate(result or {}).model_dump(mode="json")


def suggested_idempotency_key(job_type: str, payload: dict[str, Any]) -> str | None:
    contract = get_contract(job_type)
    if not contract or not contract.idempotency_key_fields:
        return None
    parts = [job_type]
    for field_name in contract.idempotency_key_fields:
        val = payload.get(field_name)
        if val is None:
            continue
        parts.append(f"{field_name}={val}")
    if len(parts) <= 1:
        return None
    return ":".join(parts)


def audit_metadata(job_type: str, *, job_id: str, attempt_n: int | None = None) -> dict[str, Any]:
    contract = get_contract(job_type)
    prefix = contract.audit_event_prefix if contract else "executive.job"
    meta: dict[str, Any] = {
        "eventPrefix": prefix,
        "jobType": job_type,
        "jobId": job_id,
        "neverAutoApprove": True,
        "neverSilentCanon": True,
    }
    if attempt_n is not None:
        meta["attemptN"] = attempt_n
    if contract:
        meta["retryClass"] = contract.retry_class.value
        meta["cancellation"] = contract.cancellation.value
        meta["requiredCapabilities"] = list(contract.required_capabilities)
    return meta
