"""Typed failure classification for video runtime jobs."""

from __future__ import annotations

from typing import Any

from .job_model import FailureClass


def classify_exception(exc: BaseException) -> FailureClass:
    text = str(exc).lower()
    name = type(exc).__name__.lower()

    if "cancel" in text or "interrupted by user" in text:
        return FailureClass.USER_CANCELLATION
    if "timed out" in text or "timeout" in name:
        return FailureClass.PROVIDER_TIMEOUT
    if "vram" in text or "out of memory" in text or "cuda out of memory" in text:
        return FailureClass.VRAM_EXHAUSTED
    if "cuda" in text:
        return FailureClass.CUDA_FAILURE
    if "missing" in text and "node" in text:
        return FailureClass.NODE_MISSING
    if "extension_missing" in text or "missingextensions" in text.replace(" ", ""):
        return FailureClass.NODE_MISSING
    if "workflow_missing_models" in text or ("model" in text and "missing" in text):
        return FailureClass.MODEL_MISSING
    if "workflow_graph_drift" in text or "graphhash mismatch" in text:
        return FailureClass.WORKFLOW_GRAPH_DRIFT
    if "workflow_not_certified" in text or "workflow_deferred" in text:
        return FailureClass.WORKFLOW_NOT_CERTIFIED
    if "workflow" in text and ("invalid" in text or "malformed" in text):
        return FailureClass.WORKFLOW_INVALID
    if "unsupported resolution" in text:
        return FailureClass.UNSUPPORTED_RESOLUTION
    if "unsupported frame" in text:
        return FailureClass.UNSUPPORTED_FRAME_COUNT
    if "quota" in text or "rate limit" in text or "429" in text:
        return FailureClass.PROVIDER_QUOTA
    if "safety" in text or "nsfw" in text or "content policy" in text:
        return FailureClass.SAFETY_REJECTION
    if "rejected" in text or "403" in text or "401" in text:
        return FailureClass.PROVIDER_REJECTED
    if "comfyui" in text and ("unreachable" in text or "connect" in text):
        return FailureClass.RUNTIME_UNAVAILABLE
    if "no output" in text or "output missing" in text:
        return FailureClass.OUTPUT_MISSING
    if "corrupt" in text or "unplayable" in text or "invalid container" in text:
        return FailureClass.OUTPUT_CORRUPT
    if "input" in text and ("invalid" in text or "required" in text or "missing" in text):
        return FailureClass.INPUT_INVALID
    return FailureClass.UNKNOWN


def failure_payload(
    failure_class: FailureClass,
    *,
    message: str,
    compute_consumed: bool = False,
    retry_eligible: bool | None = None,
    settings_should_change: bool = False,
    partial_output_exists: bool = False,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if retry_eligible is None:
        retry_eligible = failure_class not in {
            FailureClass.USER_CANCELLATION,
            FailureClass.SAFETY_REJECTION,
            FailureClass.PROVIDER_QUOTA,
            FailureClass.UNSUPPORTED_RESOLUTION,
            FailureClass.UNSUPPORTED_FRAME_COUNT,
            FailureClass.INPUT_INVALID,
            FailureClass.WORKFLOW_INVALID,
            FailureClass.NODE_MISSING,
            FailureClass.MODEL_MISSING,
        }
    if failure_class in {
        FailureClass.VRAM_EXHAUSTED,
        FailureClass.UNSUPPORTED_RESOLUTION,
        FailureClass.UNSUPPORTED_FRAME_COUNT,
        FailureClass.INPUT_INVALID,
        FailureClass.MODEL_MISSING,
        FailureClass.NODE_MISSING,
    }:
        settings_should_change = True

    return {
        "failureClass": failure_class.value,
        "whatFailed": message,
        "computeConsumed": compute_consumed,
        "retrySafe": retry_eligible,
        "settingsShouldChange": settings_should_change,
        "partialOutputExists": partial_output_exists,
        "details": details or {},
    }
