"""M41 4.1A/4.1B — Video Runtime + Certified Workflow Library."""

from __future__ import annotations

from .job_model import (
    CANONICAL_STAGES,
    ConcurrencyClass,
    FailureClass,
    NormalizedStage,
    ProviderKindVideo,
    VramSafetyState,
    VideoJobContract,
    apply_contract_to_job_params,
    extract_contract_from_job,
    merge_video_runtime_history,
)
from .failures import classify_exception, failure_payload
from .workflow_resolver import CanonicalWorkflowContract, resolve_workflow

__all__ = [
    "CANONICAL_STAGES",
    "ConcurrencyClass",
    "FailureClass",
    "NormalizedStage",
    "ProviderKindVideo",
    "VramSafetyState",
    "VideoJobContract",
    "CanonicalWorkflowContract",
    "apply_contract_to_job_params",
    "extract_contract_from_job",
    "merge_video_runtime_history",
    "classify_exception",
    "failure_payload",
    "resolve_workflow",
]
