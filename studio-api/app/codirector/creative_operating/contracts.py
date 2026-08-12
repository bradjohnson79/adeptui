"""Frozen contracts for Co-Director Creative Operating Intelligence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

# Reuse wiki CanonState vocabulary for consistency.
CanonState = Literal[
    "CONFIRMED",
    "INFERRED",
    "EXPLORATORY",
    "PROPOSED",
    "DISPUTED",
    "SUPERSEDED",
    "LOCKED",
]

UserNeed = Literal[
    "LISTEN",
    "ENCOURAGEMENT",
    "DEVELOPMENT",
    "CRITIQUE",
    "CORRECTION",
    "PRODUCTION",
    "EXECUTION",
    "RESEARCH",
]

CreativeStage = Literal[
    "EMERGING",
    "FORMING",
    "STRUCTURING",
    "REFINING",
    "LOCKING",
    "PRODUCING",
]

InitiativeLevel = Literal[
    "QUIET_PARTNER",
    "COLLABORATIVE_PARTNER",
    "PROACTIVE_PRODUCER",
    "HANDS_ON_CO_CREATOR",
]

ResponsePosture = Literal[
    "LISTEN",
    "ENCOURAGE",
    "QUESTION",
    "DEVELOP",
    "ADVISE",
    "WARN_GENTLY",
    "ORGANIZE",
    "EXECUTE",
    "REVIEW",
]

CuriosityState = Literal["OPEN", "PARTIALLY_ANSWERED", "ANSWERED", "DEFERRED", "DISMISSED"]
CuriosityPriority = Literal["HIGH", "MEDIUM", "LOW"]
KnowledgeKind = Literal["CONFIRMED_FACT", "INTERPRETATION", "POSSIBILITY"]
ProjectFormat = Literal[
    "FEATURE_FILM",
    "SHORT_FILM",
    "EPISODIC_SERIES",
    "DOCUMENTARY",
    "ANIMATION",
    "NOVEL",
    "GAME",
    "MUSIC_VIDEO",
    "COMMERCIAL",
    "PODCAST",
    "THEATRE",
    "EDUCATIONAL",
    "EXPERIMENTAL",
    "UNKNOWN",
]

INITIATIVE_LABELS: dict[str, str] = {
    "QUIET_PARTNER": "Quiet Partner",
    "COLLABORATIVE_PARTNER": "Collaborative Partner",
    "PROACTIVE_PRODUCER": "Proactive Producer",
    "HANDS_ON_CO_CREATOR": "Hands-On Co-Creator",
}

INITIATIVE_TIPS: dict[str, str] = {
    "QUIET_PARTNER": "Listens closely, organizes quietly, and asks only when something truly matters.",
    "COLLABORATIVE_PARTNER": "Offers helpful ideas at natural pauses and asks high-value questions.",
    "PROACTIVE_PRODUCER": "Surfaces missing pieces, previews, and next steps more actively.",
    "HANDS_ON_CO_CREATOR": "Drafts and develops with you more often, with clear permission gates.",
}

# Question budget: max newly surfaced questions per creator-facing response.
QUESTION_BUDGET_BY_INITIATIVE: dict[str, int] = {
    "QUIET_PARTNER": 0,
    "COLLABORATIVE_PARTNER": 1,
    "PROACTIVE_PRODUCER": 1,
    "HANDS_ON_CO_CREATOR": 1,
}


class StructuredKnowledge(BaseModel):
    statement: str
    kind: KnowledgeKind = "INTERPRETATION"
    evidence: str | None = None
    canonState: CanonState = "INFERRED"
    confidence: float = 0.5
    sourceIds: list[str] = Field(default_factory=list)
    field: str | None = None


class CreativeCuriosityThread(BaseModel):
    id: str
    projectId: str
    targetRecordIds: list[str] = Field(default_factory=list)
    question: str
    whyItMatters: str = ""
    sourceIds: list[str] = Field(default_factory=list)
    priority: CuriosityPriority = "MEDIUM"
    state: CuriosityState = "OPEN"
    lastSurfacedAt: str | None = None
    createdAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CreativeOpening(BaseModel):
    id: str
    targetRecordIds: list[str] = Field(default_factory=list)
    openingType: str
    knownFoundation: list[str] = Field(default_factory=list)
    missingDimension: str
    whyItMatters: str
    suggestedQuestion: str | None = None
    suggestedAction: str | None = None
    priority: float = 0.5


class ForwardDevelopmentSuggestion(BaseModel):
    id: str
    projectId: str
    currentDevelopmentUnit: str
    nextDevelopmentUnit: str | None = None
    confirmedFoundation: list[str] = Field(default_factory=list)
    unresolvedSetups: list[str] = Field(default_factory=list)
    availableDirections: list[str] = Field(default_factory=list)
    suggestion: str
    whyItFits: str
    canonState: Literal["EXPLORATORY"] = "EXPLORATORY"
    confidence: float = 0.45
    sourceRecordIds: list[str] = Field(default_factory=list)
    format: ProjectFormat = "UNKNOWN"
    state: Literal["ACTIVE", "DISMISSED", "ACCEPTED"] = "ACTIVE"
    createdAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EpisodeProgressionState(BaseModel):
    latestConfirmedEpisode: int = 0
    latestAnalyzedEpisode: int = 0
    nextMissingEpisode: int = 0
    unresolvedThreads: list[str] = Field(default_factory=list)
    characterArcPositions: dict[str, str] = Field(default_factory=dict)
    pendingReveals: list[str] = Field(default_factory=list)
    nextEpisodeSuggestions: list[ForwardDevelopmentSuggestion] = Field(default_factory=list)


class ProfessionalSpecialistResult(BaseModel):
    specialistId: str
    taskId: str
    result: dict[str, Any] = Field(default_factory=dict)
    evidenceIds: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    unresolvedQuestions: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    recommendedAction: str | None = None
    confidence: float = 0.5


class ProfessionalDisagreement(BaseModel):
    topic: str
    specialistPositions: dict[str, str] = Field(default_factory=dict)
    evidenceIds: list[str] = Field(default_factory=list)
    conflictType: str = "creative"
    synthesizedRecommendation: str
    requiresCreatorDecision: bool = True


class WhyItMatters(BaseModel):
    storyImportance: str = ""
    productionImportance: str = ""
    evidenceIds: list[str] = Field(default_factory=list)


class CoDirectorCreativeDecision(BaseModel):
    userNeed: UserNeed = "LISTEN"
    creativeStage: CreativeStage = "EMERGING"
    initiativeLevel: InitiativeLevel = "COLLABORATIVE_PARTNER"
    importantNewKnowledge: list[StructuredKnowledge] = Field(default_factory=list)
    affectedRecordIds: list[str] = Field(default_factory=list)
    strongestCreativeInsights: list[str] = Field(default_factory=list)
    strongestOpenQuestions: list[str] = Field(default_factory=list)
    nextNaturalDevelopment: str | None = None
    wikiActions: list[str] = Field(default_factory=list)
    requiredSpecialists: list[str] = Field(default_factory=list)
    canonState: CanonState = "INFERRED"
    responsePosture: ResponsePosture = "LISTEN"
    projectFormat: ProjectFormat = "UNKNOWN"
    listeningOnly: bool = False
    questionBudget: int = 1
    surfacedQuestion: str | None = None
    creativeOpening: CreativeOpening | None = None
    forwardSuggestion: ForwardDevelopmentSuggestion | None = None
    disagreement: ProfessionalDisagreement | None = None
    mindNotes: dict[str, str] = Field(default_factory=dict)
    loopCompleted: list[str] = Field(default_factory=list)


class CreativeOperatingBundle(BaseModel):
    """Project-scoped creative operating state (settings_json key)."""

    projectId: str
    initiativeLevel: InitiativeLevel = "COLLABORATIVE_PARTNER"
    creativeStage: CreativeStage = "EMERGING"
    projectFormat: ProjectFormat = "UNKNOWN"
    curiosityThreads: list[CreativeCuriosityThread] = Field(default_factory=list)
    forwardSuggestions: list[ForwardDevelopmentSuggestion] = Field(default_factory=list)
    dismissedSuggestionIds: list[str] = Field(default_factory=list)
    episodeProgression: EpisodeProgressionState | None = None
    lastDecision: CoDirectorCreativeDecision | None = None
    lastDisagreement: ProfessionalDisagreement | None = None
    identityAliases: dict[str, str] = Field(default_factory=dict)  # alias → canonical name
    installments: list[dict[str, Any]] = Field(default_factory=list)
    revision: int = 1
    updatedAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
