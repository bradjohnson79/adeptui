"""M2.14 domain contracts (versioned, approval-aware)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional
from uuid import uuid4

from .honesty import default_honesty


def _id() -> str:
    return str(uuid4())


@dataclass
class EmotionalSceneProfile:
    id: str = field(default_factory=_id)
    project_id: str = ""
    scene_id: str = ""
    version: int = 1
    emotional_arc: str = ""
    subtext: str = ""
    tone: str = ""
    stakes: str = ""
    character_beats: list[dict[str, Any]] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    mode: str = "guided"  # guided | creative | variation
    honesty: str = field(default_factory=default_honesty)  # unavailable | mocked | real
    approved: bool = False
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StorytellerHandoff:
    id: str = field(default_factory=_id)
    project_id: str = ""
    scene_id: str = ""
    version: int = 1
    profile_id: str = ""
    direction_summary: str = ""
    format_guidance: str = ""
    progressive_depth: str = "shallow"
    approved: bool = False
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SonicConcept:
    id: str = field(default_factory=_id)
    project_id: str = ""
    scene_id: str = ""
    version: int = 1
    score_brief: str = ""
    ambience: str = ""
    cues: list[str] = field(default_factory=list)
    dialogue_plan: str = ""
    mix_intent: str = ""
    mode: str = "guided"
    honesty: str = field(default_factory=default_honesty)
    approved: bool = False
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SpecialistMessage:
    id: str = field(default_factory=_id)
    project_id: str = ""
    scene_id: str = ""
    from_specialist: str = ""
    to_specialist: str = ""
    kind: str = "note"  # note | question | handoff | conflict | decision
    body: str = ""
    requires_response: bool = False
    responded: bool = False
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class UnifiedSceneBrief:
    id: str = field(default_factory=_id)
    project_id: str = ""
    scene_id: str = ""
    revision: int = 1
    title: str = ""
    logline: str = ""
    emotional_profile_id: Optional[str] = None
    sonic_concept_id: Optional[str] = None
    storyteller_handoff_id: Optional[str] = None
    departments: dict[str, Any] = field(default_factory=dict)
    primary_next_action: str = ""
    approved_keys: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProductionMeeting:
    id: str = field(default_factory=_id)
    project_id: str = ""
    scene_id: str = ""
    topic: str = ""
    participants: list[str] = field(default_factory=list)
    exchanges: list[dict[str, Any]] = field(default_factory=list)
    synthesis: str = ""
    primary_next_action: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProductionDecisionImpact:
    id: str = field(default_factory=_id)
    project_id: str = ""
    scene_id: str = ""
    decision_id: str = ""
    decision_summary: str = ""
    affected_departments: list[str] = field(default_factory=list)
    revalidate_keys: list[str] = field(default_factory=list)
    preserved_approvals: list[str] = field(default_factory=list)
    impact_summary: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProductionMotif:
    id: str = field(default_factory=_id)
    project_id: str = ""
    scene_id: str = ""
    name: str = ""
    kind: str = "visual"  # visual | sonic | narrative
    description: str = ""
    linked_media_ids: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AttachmentInterpretation:
    id: str = field(default_factory=_id)
    project_id: str = ""
    attachment_id: str = ""
    classified_kind: str = "unknown"
    confidence: float = 0.0
    summary: str = ""
    proposals: list[dict[str, Any]] = field(default_factory=list)
    status: str = "proposed"  # proposed | approved | corrected | provisional | cancelled
    content_signals: list[str] = field(default_factory=list)
    honesty: str = field(default_factory=default_honesty)
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
