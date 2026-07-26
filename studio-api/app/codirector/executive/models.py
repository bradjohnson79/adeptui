"""Production Executive job status / type constants."""

from __future__ import annotations

from enum import Enum


class JobStatus(str, Enum):
    QUEUED = "Queued"
    WAITING = "Waiting"
    RUNNING = "Running"
    PAUSED = "Paused"
    BLOCKED = "Blocked"
    RETRYING = "Retrying"
    CANCELLED = "Cancelled"
    COMPLETED = "Completed"
    FAILED = "Failed"
    NEEDS_REVIEW = "NeedsReview"


JOB_STATUSES = frozenset(s.value for s in JobStatus)

TERMINAL_STATUSES = frozenset(
    {
        JobStatus.CANCELLED.value,
        JobStatus.COMPLETED.value,
        JobStatus.FAILED.value,
    }
)

RUNNABLE_STATUSES = frozenset(
    {
        JobStatus.QUEUED.value,
        JobStatus.RETRYING.value,
    }
)

ACTIVE_QUEUE_STATUSES = frozenset(
    {
        JobStatus.QUEUED.value,
        JobStatus.WAITING.value,
        JobStatus.RETRYING.value,
        JobStatus.BLOCKED.value,
        JobStatus.PAUSED.value,
    }
)


class JobType(str, Enum):
    """Orchestration job kinds. Handlers call real providers; they never approve canon."""

    STORYBOARD_GENERATE = "storyboard_generate"
    IMAGE_GENERATE = "image_generate"
    VALIDATE = "validate"
    CREATE_PROPOSAL = "create_proposal"
    AWAIT_APPROVAL = "await_approval"
    APPLY_CANON = "apply_canon"
    GENERIC = "generic"


# Capability keys required per job type (honest block if unavailable).
JOB_TYPE_CAPABILITIES: dict[str, list[str]] = {
    JobType.STORYBOARD_GENERATE.value: ["comfyui.health", "storyboard.generate"],
    JobType.IMAGE_GENERATE.value: ["comfyui.health", "storyboard.generate"],
    JobType.VALIDATE.value: ["codirector.vision.validate"],
    JobType.CREATE_PROPOSAL.value: ["codirector.bible.propose"],
    JobType.AWAIT_APPROVAL.value: ["codirector.bible.propose"],
    JobType.APPLY_CANON.value: ["codirector.bible.propose"],
    JobType.GENERIC.value: [],
}
