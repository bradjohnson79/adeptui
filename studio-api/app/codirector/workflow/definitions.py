"""Canonical workflow definitions — maps describing production logic, not project progress."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class WorkflowRequirementType(str, Enum):
    BLOCKING = "BLOCKING"
    REQUIRED = "REQUIRED"
    RECOMMENDED = "RECOMMENDED"
    OPTIONAL = "OPTIONAL"


class WorkflowRequirement(BaseModel):
    type: WorkflowRequirementType
    evidence_rule: str
    reason: str
    supported_action: Optional[str] = None


class WorkflowStage(BaseModel):
    id: str
    label: str
    evidence_rules: list[str] = Field(default_factory=list)
    readiness_rules: list[WorkflowRequirement] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    major_stage_boundary: bool = False


class WorkflowTransition(BaseModel):
    from_stage: str
    to_stage: str
    requirements: list[WorkflowRequirement] = Field(default_factory=list)


class WorkflowDefinition(BaseModel):
    id: str
    name: str
    applicable_formats: list[str]
    stages: list[WorkflowStage]
    transitions: list[WorkflowTransition]
    optional_branches: list[list[str]] = Field(default_factory=list)


COMMERCIAL_WORKFLOW = WorkflowDefinition(
    id="commercial",
    name="Commercial Workflow",
    applicable_formats=["commercial", "short", "ad", "promo"],
    stages=[
        WorkflowStage(id="concept", label="Concept Development", evidence_rules=["Project exists with title and format"], major_stage_boundary=False),
        WorkflowStage(id="product_premise", label="Product/Premise", evidence_rules=["Script has product/setting references"], readiness_rules=[WorkflowRequirement(type="REQUIRED", evidence_rule="Primary character identified", reason="Commercial needs a central figure")], major_stage_boundary=False),
        WorkflowStage(id="script", label="Script", evidence_rules=["Script document exists with elements"], readiness_rules=[WorkflowRequirement(type="BLOCKING", evidence_rule="Script draft saved", reason="Cannot proceed without a script")], major_stage_boundary=True),
        WorkflowStage(id="shot_planning", label="Shot Planning", evidence_rules=["Shot plans or image pipeline data exists"], readiness_rules=[WorkflowRequirement(type="REQUIRED", evidence_rule="Script ready", reason="Shots need script grounding"), WorkflowRequirement(type="REQUIRED", evidence_rule="Primary character approved", reason="Character drives shot composition")], major_stage_boundary=True),
        WorkflowStage(id="visual_development", label="Visual Development", evidence_rules=["Generated assets or character refs exist"], major_stage_boundary=False),
        WorkflowStage(id="generation", label="Generation", evidence_rules=["Image/video generation jobs exist"], major_stage_boundary=False),
        WorkflowStage(id="audio", label="Audio/Voice", evidence_rules=["Audio studio data or voice profiles exist"], major_stage_boundary=False),
        WorkflowStage(id="timeline", label="Timeline/Editorial", evidence_rules=["Timeline clips or MAGI sequence exist"], major_stage_boundary=True),
        WorkflowStage(id="finishing", label="Finishing", evidence_rules=["Final QC or post-production data exists"], major_stage_boundary=False),
    ],
    transitions=[],
)

NARRATIVE_WORKFLOW = WorkflowDefinition(
    id="narrative",
    name="Narrative Workflow",
    applicable_formats=["narrative", "feature", "short_film", "episodic", "scene"],
    stages=[
        WorkflowStage(id="concept", label="Concept", evidence_rules=["Project exists"], major_stage_boundary=False),
        WorkflowStage(id="story_development", label="Story Development", evidence_rules=["Bible overview data or premise exists"], major_stage_boundary=True),
        WorkflowStage(id="characters", label="Character Development", evidence_rules=["Character profiles exist"], major_stage_boundary=False),
        WorkflowStage(id="bible", label="Production Bible", evidence_rules=["Bible entities exist"], major_stage_boundary=False),
        WorkflowStage(id="screenplay", label="Screenplay", evidence_rules=["Script document exists"], major_stage_boundary=True),
        WorkflowStage(id="scene_planning", label="Scene/Sequence Planning", evidence_rules=["Scene records with continuity"], major_stage_boundary=False),
        WorkflowStage(id="shot_planning", label="Shot Planning", evidence_rules=["Shot plans exist"], major_stage_boundary=True),
        WorkflowStage(id="asset_development", label="Asset Development", evidence_rules=["Generated assets or character refs"], major_stage_boundary=False),
        WorkflowStage(id="generation", label="Generation/Production", evidence_rules=["Generation jobs exist"], major_stage_boundary=False),
        WorkflowStage(id="editorial", label="Editorial", evidence_rules=["Timeline clips or MAGI sequence"], major_stage_boundary=True),
        WorkflowStage(id="audio", label="Audio", evidence_rules=["Audio assets exist"], major_stage_boundary=False),
        WorkflowStage(id="finishing", label="Finishing", evidence_rules=["Post-production data exists"], major_stage_boundary=False),
    ],
    transitions=[],
    optional_branches=[["characters", "bible"], ["asset_development", "generation"]],
)

MUSIC_VIDEO_WORKFLOW = WorkflowDefinition(
    id="music_video",
    name="Music Video Workflow",
    applicable_formats=["music_video", "song", "lyric", "performance"],
    stages=[
        WorkflowStage(id="audio_source", label="Song/Audio Source", evidence_rules=["Audio track referenced"], major_stage_boundary=False),
        WorkflowStage(id="visual_concept", label="Visual Concept", evidence_rules=["Concept descriptions exist"], major_stage_boundary=True),
        WorkflowStage(id="performance", label="Performance/Characters", evidence_rules=["Character or performer profiles"], major_stage_boundary=False),
        WorkflowStage(id="lyrics", label="Lyrics/Storyboard", evidence_rules=["Lyrics or storyboard exists"], major_stage_boundary=False),
        WorkflowStage(id="shot_design", label="Shot Design", evidence_rules=["Shot plans exist"], major_stage_boundary=True),
        WorkflowStage(id="generation", label="Generation", evidence_rules=["Generated assets exist"], major_stage_boundary=False),
        WorkflowStage(id="editorial", label="Editorial", evidence_rules=["Timeline clips"], major_stage_boundary=True),
    ],
    transitions=[],
)

UNKNOWN_WORKFLOW = WorkflowDefinition(
    id="unknown",
    name="General Creative Workflow",
    applicable_formats=["unknown", "custom", "other"],
    stages=[
        WorkflowStage(id="concept", label="Concept", evidence_rules=["Project exists"], major_stage_boundary=False),
        WorkflowStage(id="development", label="Development", evidence_rules=["Any creative artifacts exist"], major_stage_boundary=False),
        WorkflowStage(id="production", label="Production", evidence_rules=["Generated assets exist"], major_stage_boundary=True),
        WorkflowStage(id="finishing", label="Finishing", evidence_rules=["Post-production data"], major_stage_boundary=False),
    ],
    transitions=[],
)


_FORMAT_WORKFLOW_MAP: dict[str, WorkflowDefinition] = {
    "commercial": COMMERCIAL_WORKFLOW,
    "narrative": NARRATIVE_WORKFLOW,
    "music_video": MUSIC_VIDEO_WORKFLOW,
    "unknown": UNKNOWN_WORKFLOW,
}


def get_workflow_for_format(format_str: Optional[str]) -> WorkflowDefinition:
    if not format_str:
        return UNKNOWN_WORKFLOW
    fmt = format_str.strip().lower().replace("-", "_").replace(" ", "_")
    if fmt in _FORMAT_WORKFLOW_MAP:
        return _FORMAT_WORKFLOW_MAP[fmt]
    return UNKNOWN_WORKFLOW
