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
    MODEL_DISCOVER = "model_discover"
    EVALUATE_COMPATIBILITY = "evaluate_compatibility"
    SANDBOX_PLAN = "sandbox_plan"
    SANDBOX_INSTALL = "sandbox_install"
    SANDBOX_VALIDATE = "sandbox_validate"
    SANDBOX_PROMOTE = "sandbox_promote"
    RECIPE_STAGE = "recipe_stage"
    APPLY_SHOT_PROFILE = "apply_shot_profile"
    FRAME_GENERATE = "frame_generate"
    FRAME_SEQUENCE = "frame_sequence"
    VIDEO_GENERATE = "video_generate"
    LIPSYNC_GENERATE = "lipsync_generate"
    MOUTH_TRACK_GENERATE = "mouth_track_generate"
    AUDIO_GENERATE = "audio_generate"
    AUDIO_PROCESS = "audio_process"
    TIMELINE_RENDER = "timeline_render"
    SCENE_RENDER = "scene_render"
    EDIT_APPLY = "edit_apply"


# Capability keys required per job type (honest block if unavailable).
JOB_TYPE_CAPABILITIES: dict[str, list[str]] = {
    JobType.STORYBOARD_GENERATE.value: ["comfyui.health", "storyboard.generate"],
    JobType.IMAGE_GENERATE.value: ["comfyui.health", "storyboard.generate"],
    JobType.VALIDATE.value: ["codirector.vision.validate"],
    JobType.CREATE_PROPOSAL.value: ["codirector.bible.propose"],
    JobType.AWAIT_APPROVAL.value: ["codirector.bible.propose"],
    JobType.APPLY_CANON.value: ["codirector.bible.propose"],
    JobType.GENERIC.value: [],
    JobType.MODEL_DISCOVER.value: ["m28.radar.discover"],
    JobType.EVALUATE_COMPATIBILITY.value: ["m28.compat.evaluate"],
    JobType.SANDBOX_PLAN.value: ["m28.sandbox.plan"],
    JobType.SANDBOX_INSTALL.value: ["m28.sandbox.install"],
    JobType.SANDBOX_VALIDATE.value: ["m28.sandbox.validate"],
    JobType.SANDBOX_PROMOTE.value: ["m28.sandbox.promote"],
    JobType.RECIPE_STAGE.value: ["m28.recipe.execute"],
    JobType.APPLY_SHOT_PROFILE.value: ["m28.shot_profile.apply"],
    JobType.FRAME_GENERATE.value: [],  # registry IDs honest; not blocking until locally_verified
    JobType.FRAME_SEQUENCE.value: [],  # registry IDs honest; not blocking until locally_verified
    JobType.VIDEO_GENERATE.value: [],  # registry IDs honest; not blocking until locally_verified
    JobType.LIPSYNC_GENERATE.value: [],  # registry IDs honest; not blocking until locally_verified
    JobType.MOUTH_TRACK_GENERATE.value: [],  # registry IDs honest; not blocking until locally_verified
    JobType.AUDIO_GENERATE.value: [],  # registry IDs honest; not blocking until locally_verified
    JobType.AUDIO_PROCESS.value: [],  # registry IDs honest; not blocking until locally_verified
    JobType.TIMELINE_RENDER.value: [],  # registry IDs honest; not blocking until locally_verified
    JobType.SCENE_RENDER.value: [],  # registry IDs honest; not blocking until locally_verified
    JobType.EDIT_APPLY.value: [],  # registry IDs honest; not blocking until locally_verified
}

