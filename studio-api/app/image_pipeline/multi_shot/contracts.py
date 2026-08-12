"""Pydantic wire contracts for the Multi-Shot Image Planning API.

Wire format is camelCase (matching `image_pipeline.contracts` and the studio-web
`imagePipeline.ts` client contracts). Every model sets `populate_by_name=True`,
so payloads written in snake_case (the SQL column names) parse identically —
camelCase and snake_case clients are both first-class.

Provider-agnostic by construction: `provider_id` / `model_id` are plain strings
with no registry validation, and per-candidate `provider` / `model` / `settings`
are free-form so any backend can record generation metadata.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

MultiShotPlanStatus = Literal["draft", "active", "archived"]
MultiShotStatus = Literal[
    "pending", "generating", "candidate_review", "approved", "rejected", "sent_to_timeline"
]
MultiShotCandidateStatus = Literal["pending", "approved", "rejected"]

#: Recognized roles for shared plan references. The list is documentary, not
#: enforced — new reference kinds must not require a schema change.
REFERENCE_ROLES = ("style", "character", "environment", "moodboard", "lighting", "costume", "prop")


class _WireModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class MultiShotReference(_WireModel):
    """One shared visual reference on a plan, tagged with its semantic role."""

    role: str = "style"
    asset_id: str | None = None
    reference_id: str | None = None
    character_id: str | None = None
    label: str | None = None
    notes: str | None = None


class MultiShotPlanCreate(_WireModel):
    name: str | None = None
    provider_id: str | None = None
    model_id: str | None = None
    shared_visual_context: str | None = None
    shared_references: list[MultiShotReference] | None = None
    aspect_ratio: str | None = None
    resolution_label: str | None = None
    status: MultiShotPlanStatus | None = None


class MultiShotPlanUpdate(_WireModel):
    name: str | None = None
    provider_id: str | None = None
    model_id: str | None = None
    shared_visual_context: str | None = None
    shared_references: list[MultiShotReference] | None = None
    aspect_ratio: str | None = None
    resolution_label: str | None = None
    status: MultiShotPlanStatus | None = None


class MultiShotCreate(_WireModel):
    title: str | None = None
    prompt: str | None = None
    image_prompt: str | None = None
    video_prompt: str | None = None
    duration_hint: float | None = None
    framing: str | None = None
    camera_angle: str | None = None
    subject_ids: list[str] | None = None
    reference_ids: list[str] | None = None
    seed_strategy: str | None = None
    status: MultiShotStatus | None = None


class MultiShotUpdate(_WireModel):
    title: str | None = None
    prompt: str | None = None
    image_prompt: str | None = None
    video_prompt: str | None = None
    duration_hint: float | None = None
    framing: str | None = None
    camera_angle: str | None = None
    subject_ids: list[str] | None = None
    reference_ids: list[str] | None = None
    seed_strategy: str | None = None
    status: MultiShotStatus | None = None


class MultiShotReorderRequest(_WireModel):
    """Full-set reorder: must list every shot id in the plan, in the new order."""

    shot_ids: list[str] = Field(default_factory=list)


class MultiShotCandidateCreate(_WireModel):
    """Record a generation candidate for a shot.

    This endpoint records metadata only — it never queues generation. `asset_id`
    points at the shared Asset system when the candidate produced a real image;
    tests may supply a simulated id.
    """

    generation_id: str | None = None
    provider: str | None = None
    model: str | None = None
    seed: int | None = None
    prompt: str | None = None
    references: list[dict[str, Any]] | None = None
    loras: list[dict[str, Any]] | None = None
    settings: dict[str, Any] | None = None
    asset_id: str | None = None
    status: MultiShotCandidateStatus | None = None


class MultiShotCandidateActionRequest(_WireModel):
    candidate_id: str


class MultiShotSendToTimelineRequest(_WireModel):
    """Request to hand off approved shots to the W46 Timeline.

    By default only shots with status ``approved`` are sent. Set ``only_missing``
    to skip shots that already have a ``timeline_batch_block_id`` rather than
    creating duplicate batches.
    """

    only_missing: bool = True
    generator_id: str | None = None
    default_duration: float = 5.0


class MultiShotERSRecommendation(_WireModel):
    """ERS (Environment Reference Sheet) advisory for a Multi-Shot plan.

    Krea 2 excels at style continuity; ERS provides environmental/location
    conditioning. The recommendation is surfaced as a plain-language advisory
    and the actual ERS assets are wired through the shared reference path when
    present (``environment`` role, ERS Semantic Role Law).
    """

    ers_available: bool
    sheet_count: int
    recommended: bool
    reason: str
    missing_reason: str | None = None
    sheet_ids: list[str] = Field(default_factory=list)
