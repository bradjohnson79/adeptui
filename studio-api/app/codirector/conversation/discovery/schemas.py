"""Typed contracts for personality discovery, intrigue, documentation, and research."""

from __future__ import annotations

from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class CreativeDevelopmentStage(str, Enum):
    EMERGENCE = "EMERGENCE"
    EXPLORATION = "EXPLORATION"
    FORMATION = "FORMATION"
    EVALUATION = "EVALUATION"
    PRODUCTION = "PRODUCTION"


class CreativeTemperature(BaseModel):
    stage: CreativeDevelopmentStage = CreativeDevelopmentStage.EMERGENCE
    momentum: Literal["FRAGILE", "BUILDING", "STABLE", "HIGH"] = "BUILDING"
    critique_allowed: bool = False
    caution_allowed: bool = False
    intrigue_priority: Literal["LOW", "MEDIUM", "HIGH"] = "HIGH"
    documentation_priority: Literal["LOW", "MEDIUM", "HIGH"] = "HIGH"
    question_budget: int = 1


class IntrigueLevel(str, Enum):
    EMERGING = "EMERGING"
    STRONG = "STRONG"
    EXCEPTIONAL = "EXCEPTIONAL"


class CreativeIntrigueAssessment(BaseModel):
    distinctive_elements: list[str] = Field(default_factory=list)
    emotional_hooks: list[str] = Field(default_factory=list)
    cinematic_hooks: list[str] = Field(default_factory=list)
    thematic_potential: list[str] = Field(default_factory=list)
    audience_promise: list[str] = Field(default_factory=list)
    originality_signals: list[str] = Field(default_factory=list)
    unanswered_creative_questions: list[str] = Field(default_factory=list)
    intrigue_level: IntrigueLevel = IntrigueLevel.EMERGING
    evidence_spans: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.4, ge=0.0, le=1.0)


class ResponseEvidenceSlot(str, Enum):
    INTRIGUE = "INTRIGUE"
    REFLECTION = "REFLECTION"
    WIKI_SUMMARY = "WIKI_SUMMARY"
    DISCOVERY_QUESTION = "DISCOVERY_QUESTION"
    RESEARCH_OPPORTUNITY = "RESEARCH_OPPORTUNITY"


class ResponseEvidence(BaseModel):
    slots_hit: list[ResponseEvidenceSlot] = Field(default_factory=list)
    count: int = 0
    required_minimum: int = 2
    ok: bool = False
    notes: list[str] = Field(default_factory=list)


class WikiCandidateCategory(str, Enum):
    PROJECT = "PROJECT"
    CHARACTER = "CHARACTER"
    RELATIONSHIP = "RELATIONSHIP"
    ENTITY = "ENTITY"
    LOCATION = "LOCATION"
    TIMELINE = "TIMELINE"
    EVENT = "EVENT"
    WORLD_RULE = "WORLD_RULE"
    THEME = "THEME"
    TONE = "TONE"
    STORY_PRINCIPLE = "STORY_PRINCIPLE"
    VISUAL_LANGUAGE = "VISUAL_LANGUAGE"
    PRODUCTION_CONSTRAINT = "PRODUCTION_CONSTRAINT"
    RESEARCH_NOTE = "RESEARCH_NOTE"
    ANTI_REFERENCE = "ANTI_REFERENCE"


class DiscoveryWikiCandidate(BaseModel):
    id: str = Field(default_factory=lambda: f"wiki-{uuid4().hex[:10]}")
    project_id: str = ""
    category: WikiCandidateCategory = WikiCandidateCategory.PROJECT
    title: str = ""
    content: str = ""
    status: Literal["CONFIRMED", "EMERGING", "INFERRED", "DISPUTED", "SUPERSEDED"] = "EMERGING"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    source_message_ids: list[str] = Field(default_factory=list)
    evidence_excerpts: list[str] = Field(default_factory=list)
    duplicate_of_id: str | None = None
    requires_approval: bool = False


class DocumentationReason(str, Enum):
    OK = "OK"
    NO_PROJECT_FACTS_FOUND = "NO_PROJECT_FACTS_FOUND"  # alias: NO_RELEVANT_FACTS
    AMBIGUOUS_CONTENT = "AMBIGUOUS_CONTENT"
    DOCUMENTATION_DISABLED = "DOCUMENTATION_DISABLED"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    DUPLICATE_ONLY = "DUPLICATE_ONLY"
    NOT_SUBSTANTIVE = "NOT_SUBSTANTIVE"


class DocumentationResult(BaseModel):
    substantive: bool = False
    candidate_count: int = 0
    candidates: list[DiscoveryWikiCandidate] = Field(default_factory=list)
    reason: DocumentationReason = DocumentationReason.NOT_SUBSTANTIVE
    confirmed_writes: int = 0
    emerging_writes: int = 0
    summary_lines: list[str] = Field(default_factory=list)


class LivingProjectBrief(BaseModel):
    project_id: str = ""
    completeness: float = 0.0
    confirmed_field_count: int = 0
    emerging_field_count: int = 0
    unresolved_field_count: int = 0
    updated_at: str = ""
    fields: dict[str, str] = Field(default_factory=dict)


class DiscoveryQuestion(BaseModel):
    id: str = Field(default_factory=lambda: f"dq-{uuid4().hex[:10]}")
    project_id: str = ""
    question: str = ""
    explanation: str = ""
    category: str = "story"
    options: list[str] = Field(default_factory=list)
    allow_custom_answer: bool = True
    required: bool = False
    priority: int = 50
    source_gap_ids: list[str] = Field(default_factory=list)


class CuriosityThread(BaseModel):
    id: str = Field(default_factory=lambda: f"cur-{uuid4().hex[:10]}")
    project_id: str = ""
    subject: str = ""
    why_it_matters: str = ""
    source_ids: list[str] = Field(default_factory=list)
    priority: int = 50
    status: Literal["OPEN", "DEFERRED", "RESOLVED", "DISMISSED"] = "OPEN"


class ResearchPermission(str, Enum):
    ASK_FIRST = "ASK_FIRST"
    WHEN_USEFUL = "WHEN_USEFUL"
    ACTIVE = "ACTIVE"
    OFFLINE = "OFFLINE"


class ResearchNote(BaseModel):
    id: str = Field(default_factory=lambda: f"rn-{uuid4().hex[:10]}")
    project_id: str = ""
    title: str = ""
    category: str = "CREATIVE_COMPARABLES"
    summary: str = ""
    project_relevance: str = ""
    key_findings: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    status: Literal["DRAFT", "REVIEWED", "APPROVED", "ARCHIVED"] = "DRAFT"


class CreativeComparison(BaseModel):
    reference_title: str = ""
    reference_type: str = "FILM"
    comparison_dimensions: list[str] = Field(default_factory=list)
    relevant_similarities: list[str] = Field(default_factory=list)
    critical_differences: list[str] = Field(default_factory=list)
    useful_lessons: list[str] = Field(default_factory=list)
    risks_of_over_similarity: list[str] = Field(default_factory=list)
    project_distinctiveness: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    confidence: float = 0.4


class ProjectPulse(BaseModel):
    current_phase: str = "Discovery"
    creative_momentum: str = "Building"
    confirmed_facts: int = 0
    emerging_ideas: int = 0
    open_decisions: int = 0
    canon_conflicts: int = 0
    next_useful_step: str = ""


class CoDirectorProcessingStage(str, Enum):
    RECEIVED = "RECEIVED"
    UNDERSTANDING = "UNDERSTANDING"
    INTRIGUE_ANALYSIS = "INTRIGUE_ANALYSIS"
    FACT_EXTRACTION = "FACT_EXTRACTION"
    WIKI_UPDATE = "WIKI_UPDATE"
    VISION_ANALYSIS = "VISION_ANALYSIS"
    ARTIFACT_READINESS = "ARTIFACT_READINESS"
    DRAFTING = "DRAFTING"
    RESEARCHING = "RESEARCHING"
    DISCOVERY_FORM = "DISCOVERY_FORM"
    PITCH_BUILDING = "PITCH_BUILDING"
    MARKETING_ANALYSIS = "MARKETING_ANALYSIS"
    RESPONSE_GENERATION = "RESPONSE_GENERATION"
    GROUNDING = "GROUNDING"
    COMPLETE = "COMPLETE"


class DiscoveryProjectBundle(BaseModel):
    brief: LivingProjectBrief = Field(default_factory=LivingProjectBrief)
    wiki_candidates: list[DiscoveryWikiCandidate] = Field(default_factory=list)
    discovery_questions: list[DiscoveryQuestion] = Field(default_factory=list)
    curiosity_threads: list[CuriosityThread] = Field(default_factory=list)
    research_notes: list[ResearchNote] = Field(default_factory=list)
    anti_references: list[str] = Field(default_factory=list)
    creative_stage: CreativeDevelopmentStage = CreativeDevelopmentStage.EMERGENCE
    last_documentation: DocumentationResult | None = None
    last_intrigue: CreativeIntrigueAssessment | None = None
    last_response_evidence: ResponseEvidence | None = None
    last_what_changed: list[str] = Field(default_factory=list)


IDENTITY_POLICY_VERSION = "codirector-discovery-identity-v1"
