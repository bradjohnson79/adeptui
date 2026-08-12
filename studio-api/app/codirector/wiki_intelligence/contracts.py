"""Frozen contracts for Professional Wiki Intelligence + Reorganize Wiki."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

CanonState = Literal[
    "CONFIRMED",
    "INFERRED",
    "EXPLORATORY",
    "PROPOSED",
    "DISPUTED",
    "SUPERSEDED",
    "LOCKED",
]

WikiAction = Literal["CREATE", "UPDATE", "MERGE", "RECLASSIFY", "REVIEW", "REJECT"]
SpecialistRecommendedAction = Literal[
    "CREATE",
    "UPDATE",
    "MERGE",
    "RECLASSIFY",
    "REJECT",
    "FLAG_CONFLICT",
    "REQUEST_CONFIRMATION",
    "NO_ACTION",
]
ExecutionMode = Literal["FOREGROUND_REQUIRED", "BACKGROUND", "DEFERRED_MAINTENANCE"]
ReorgStatus = Literal[
    "QUEUED",
    "ANALYZING",
    "REORGANIZING",
    "VERIFYING",
    "COMPLETE",
    "PARTIAL",
    "FAILED",
    "CANCELLED",
]

# Professional TOC section keys (projection tree).
PROFESSIONAL_TOC_ROOTS: tuple[str, ...] = (
    "projectOverview",
    "story",
    "characters",
    "episodesAndScenes",
    "worldAndLore",
    "locationsAndSets",
    "timelineAndContinuity",
    "visualDevelopment",
    "audioAndPerformance",
    "scriptsAndDevelopment",
    "production",
    "references",
)

# Domains selectable in Reorganize Wiki confirmation UI.
REORGANIZE_DOMAINS: tuple[str, ...] = (
    "characters",
    "locations",
    "story",
    "world",
    "timeline",
    "wardrobe",
    "props",
    "visual",
    "audio",
    "assets",
    "canon",
)

# Problem-driven specialist routing (existing + planned IDs).
DOMAIN_SPECIALIST_MAP: dict[str, list[str]] = {
    "characters": [
        "character-creator",
        "casting-director",
        "performance-director",
        "story-editor",
        "costume-designer",
    ],
    "locations": ["production-designer", "art-director", "cinematographer", "sound-designer"],
    "story": ["story-editor", "story-analyst", "screenwriter", "storyteller", "editor"],
    "world": [
        "worldbuilding-specialist",
        "bible-manager",
        "project-bible-steward",
        "production-designer",
        "research-specialist",
    ],
    "timeline": ["script-supervisor", "continuity-analyst", "editor"],
    "wardrobe": ["costume-designer", "character-creator", "script-supervisor"],
    "props": ["props-master", "production-designer", "script-supervisor"],
    "visual": [
        "cinematographer",
        "lighting-supervisor",
        "art-director",
        "vision-reviewer",
        "storyboard-artist",
        "prompt-architect",
    ],
    "audio": ["sound-designer", "music-supervisor", "sound-producer", "performance-director"],
    "assets": ["asset-manager", "pipeline-manager", "producer"],
    "canon": [
        "bible-manager",
        "project-bible-steward",
        "script-supervisor",
        "continuity-analyst",
        "qa-reviewer",
    ],
}

# Curated set allowed to propose Wiki writes (orchestrator applies).
WIKI_WRITE_SPECIALIST_IDS: frozenset[str] = frozenset(
    {
        "story-editor",
        "story-analyst",
        "screenwriter",
        "storyteller",
        "director",
        "character-creator",
        "casting-director",
        "performance-director",
        "script-supervisor",
        "continuity-analyst",
        "production-designer",
        "art-director",
        "cinematographer",
        "lighting-supervisor",
        "sound-designer",
        "music-supervisor",
        "sound-producer",
        "producer",
        "pipeline-manager",
        "asset-manager",
        "editor",
        "vfx-supervisor",
        "bible-manager",
        "project-bible-steward",
        "costume-designer",
        "props-master",
        "storyboard-artist",
        "worldbuilding-specialist",
        "research-specialist",
        "marketing-pitch",
    }
)

FALSE_CHARACTER_TOKENS: frozenset[str] = frozenset(
    {
        "she",
        "he",
        "they",
        "here",
        "there",
        "research",
        "episode",
        "series",
        "synopsis",
        "series synopsis",
        "overview",
        "treatment",
        "the",
        "this",
        "that",
        "when",
        "after",
        "before",
        "agent gold",  # Co-Director preference persona, not project cast
        "current",
        "narrative",
        "director",
        "creator",
        "default",
        "assistant",
        "suggestion",
        "suggest",
        "test",
        "sample",
        "example",
        "understanding",
        "collaboration",
        "preference",
        "onboarding",
        "tell",
        "skip",
    }
)


class StructuredFact(BaseModel):
    statement: str
    field: str | None = None
    evidence: str | None = None
    canonState: CanonState = "INFERRED"
    confidence: float = 0.5
    sourceIds: list[str] = Field(default_factory=list)


class WikiConflict(BaseModel):
    conflictType: str
    description: str
    entityIds: list[str] = Field(default_factory=list)
    severity: Literal["info", "warning", "error"] = "warning"
    suggestedResolution: str | None = None


class WikiQuestion(BaseModel):
    question: str
    reason: str = ""
    entityIds: list[str] = Field(default_factory=list)
    options: list[str] = Field(default_factory=list)


class WikiSpecialistFinding(BaseModel):
    specialistId: str
    sourceId: str
    targetRecordType: str
    targetRecordId: str | None = None
    facts: list[StructuredFact] = Field(default_factory=list)
    inferredInsights: list[StructuredFact] = Field(default_factory=list)
    conflicts: list[WikiConflict] = Field(default_factory=list)
    missingInformation: list[WikiQuestion] = Field(default_factory=list)
    productionUses: list[str] = Field(default_factory=list)
    recommendedAction: SpecialistRecommendedAction = "NO_ACTION"
    confidence: float = 0.5
    canonRecommendation: CanonState = "INFERRED"


class WikiSpecialistAssignment(BaseModel):
    sourceId: str
    projectId: str
    detectedDomains: list[str] = Field(default_factory=list)
    selectedSpecialists: list[str] = Field(default_factory=list)
    requiredSpecialists: list[str] = Field(default_factory=list)
    optionalSpecialists: list[str] = Field(default_factory=list)
    reasonForSelection: dict[str, str] = Field(default_factory=dict)
    executionMode: ExecutionMode = "BACKGROUND"
    contextBudgetTokens: int = 2500
    latencyBudgetMs: int = 8000


class WikiIntelligenceDecision(BaseModel):
    sourceId: str
    detectedEntityType: str
    targetSection: str
    targetRecordId: str | None = None
    canonState: CanonState = "INFERRED"
    confidence: float = 0.5
    productionUses: list[str] = Field(default_factory=list)
    relatedRecordIds: list[str] = Field(default_factory=list)
    action: WikiAction = "REVIEW"
    specialistIds: list[str] = Field(default_factory=list)
    text: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class WikiOrganizationProblem(BaseModel):
    problemType: str
    description: str
    domain: str
    recordIds: list[str] = Field(default_factory=list)
    severity: Literal["info", "warning", "error"] = "warning"


class WikiChangeRecord(BaseModel):
    changeType: str
    recordId: str | None = None
    before: str | None = None
    after: str | None = None
    sectionFrom: str | None = None
    sectionTo: str | None = None
    specialistIds: list[str] = Field(default_factory=list)


class WikiReorganizationJob(BaseModel):
    id: str
    projectId: str
    requestedBy: str = "creator"
    selectedDomains: list[str] = Field(default_factory=list)
    detectedProblems: list[WikiOrganizationProblem] = Field(default_factory=list)
    specialistAssignments: list[WikiSpecialistAssignment] = Field(default_factory=list)
    status: ReorgStatus = "QUEUED"
    stage: str | None = None
    recordsReviewed: int = 0
    recordsCreated: int = 0
    recordsUpdated: int = 0
    recordsMerged: int = 0
    recordsReclassified: int = 0
    recordsRejected: int = 0
    conflictsFound: int = 0
    creatorConfirmationsRequired: int = 0
    tocRebuilt: bool = False
    readBackVerified: bool = False
    summaryLines: list[str] = Field(default_factory=list)
    changes: list[WikiChangeRecord] = Field(default_factory=list)
    revisionId: str | None = None
    startedAt: str | None = None
    completedAt: str | None = None
    error: str | None = None


class WikiReorganizationRevision(BaseModel):
    revisionId: str
    projectId: str
    jobId: str
    previousWikiRevision: int
    newWikiRevision: int
    changes: list[WikiChangeRecord] = Field(default_factory=list)
    specialistIds: list[str] = Field(default_factory=list)
    createdAt: str
    reversible: bool = True
    snapshot: dict[str, Any] = Field(default_factory=dict)


class ProductionCharacterProfile(BaseModel):
    """Wiki projection DTO — assembled from Bible + Character Identity."""

    id: str
    projectId: str
    canonicalName: str
    aliases: list[str] = Field(default_factory=list)
    titles: list[str] = Field(default_factory=list)
    status: CanonState = "INFERRED"
    narrativeRole: str | None = None
    characterType: str | None = None
    biography: str | None = None
    personalityTraits: list[str] = Field(default_factory=list)
    motivations: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    fears: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    vulnerabilities: list[str] = Field(default_factory=list)
    relationships: list[dict[str, Any]] = Field(default_factory=list)
    affiliations: list[str] = Field(default_factory=list)
    arcSummary: str | None = None
    physicalDescription: str | None = None
    ageOrAgeRange: str | None = None
    distinguishingFeatures: list[str] = Field(default_factory=list)
    wardrobeLooks: list[dict[str, Any]] = Field(default_factory=list)
    props: list[dict[str, Any]] = Field(default_factory=list)
    voiceNotes: str | None = None
    performanceNotes: list[str] = Field(default_factory=list)
    continuityNotes: list[str] = Field(default_factory=list)
    unresolvedQuestions: list[str] = Field(default_factory=list)
    sourceMessageIds: list[str] = Field(default_factory=list)
    sourceAssetIds: list[str] = Field(default_factory=list)


class ProductionLocationProfile(BaseModel):
    id: str
    canonicalName: str
    aliases: list[str] = Field(default_factory=list)
    locationType: str = ""
    description: str | None = None
    geography: str | None = None
    interiors: list[str] = Field(default_factory=list)
    exteriors: list[str] = Field(default_factory=list)
    connectedSpaces: list[str] = Field(default_factory=list)
    architectureNotes: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    lightingNotes: list[str] = Field(default_factory=list)
    colorPalette: list[str] = Field(default_factory=list)
    atmosphereNotes: list[str] = Field(default_factory=list)
    weatherNotes: list[str] = Field(default_factory=list)
    soundscapeNotes: list[str] = Field(default_factory=list)
    recurringProps: list[str] = Field(default_factory=list)
    scenes: list[str] = Field(default_factory=list)
    continuityNotes: list[str] = Field(default_factory=list)
    referenceAssetIds: list[str] = Field(default_factory=list)
    status: CanonState = "INFERRED"


class ProductionTimelineEvent(BaseModel):
    id: str
    dateOrPeriod: str | None = None
    sequenceOrder: int = 0
    title: str
    description: str = ""
    characters: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    organizations: list[str] = Field(default_factory=list)
    episodeId: str | None = None
    sceneId: str | None = None
    causes: list[str] = Field(default_factory=list)
    consequences: list[str] = Field(default_factory=list)
    timelineBranch: str | None = None
    canonStatus: CanonState = "INFERRED"
    sourceIds: list[str] = Field(default_factory=list)
