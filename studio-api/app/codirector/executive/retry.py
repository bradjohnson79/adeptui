"""Retry policy — attempt history is append-only; never overwrite."""

from __future__ import annotations

from .models import JobStatus
from .schemas import JobOut


def next_status_after_failure(job: JobOut) -> str:
    """Return Retrying if attempts remain, else Failed."""
    if job.attemptsCount < job.maxAttempts:
        return JobStatus.RETRYING.value
    return JobStatus.FAILED.value


def can_manual_retry(job: JobOut) -> bool:
    return job.status in (
        JobStatus.FAILED.value,
        JobStatus.BLOCKED.value,
        JobStatus.CANCELLED.value,
    )