"""Shared schemas for the Co-Director conversation core."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

KnowledgeState = Literal[
    "confirmed",
    "proposed",
    "unresolved",
    "approved",
    "rejected",
    "superseded",
    "reference-only",
]

PrimaryIntent = Literal[
    "receive_information",
    "answer_question",
    "request_clarification",
    "recommend_next_step",
    "execute_action",
    "confirm_correction",
    "invite_continuation",
    "summarize",
]


class WikiCandidate(BaseModel):
    id: str
    text: str
    state: KnowledgeState
    section: str = "creativeFoundation"
    supersedes_id: str | None = None
    provenance: str | None = None
    sourceTurn: str | None = None


class ConversationPlan(BaseModel):
    primaryIntent: PrimaryIntent = "receive_information"
    acknowledgedFacts: list[str] = Field(default_factory=list)
    relevantContext: list[str] = Field(default_factory=list)
    missingInformation: list[str] = Field(default_factory=list)
    contradictionFlags: list[str] = Field(default_factory=list)
    responseMode: str = "conversation"
    shouldAskQuestion: bool = False
    selectedQuestion: str | None = None
    recommendedNextStep: str | None = None
    shouldWriteWiki: bool = False
    wikiCandidates: list[WikiCandidate] = Field(default_factory=list)
    creativeStage: str = "Project Creation"
    creativeSubstate: str | None = None
    directorContext: dict[str, Any] = Field(default_factory=dict)


class ProjectDirectorState(BaseModel):
    currentGoal: str = ""
    currentTask: str = ""
    recentlyCompleted: list[str] = Field(default_factory=list)
    outstandingQuestions: list[str] = Field(default_factory=list)
    blockedItems: list[str] = Field(default_factory=list)
    recommendedNextStep: str = ""
    creativeStage: str = "Project Creation"
    creativeSubstate: str | None = None
    revision: int = 0


class ProjectIntelligenceSnapshot(BaseModel):
    projectId: str
    revision: int = 0
    title: str = "Untitled Project"
    format: str | None = None
    currentObjective: str | None = None
    confirmedFacts: list[str] = Field(default_factory=list)
    recentCorrections: list[str] = Field(default_factory=list)
    keyCharacters: list[str] = Field(default_factory=list)
    currentStoryScope: str | None = None
    recentDecisions: list[str] = Field(default_factory=list)
    openQuestions: list[str] = Field(default_factory=list)
    unresolvedIdeas: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    currentStage: str | None = None
    currentSubstate: str | None = None
    knowledgeEntries: list[WikiCandidate] = Field(default_factory=list)
    # Notes working desk (messy); Wiki UI must not paint these as articles.
    workingNotes: list[dict[str, Any]] = Field(default_factory=list)
    # Compiled Wiki Bible cache (creator-facing pages).
    compiledWiki: dict[str, Any] = Field(default_factory=dict)
    # Production lifecycle state blob.
    productionLifecycle: dict[str, Any] = Field(default_factory=dict)
    director: ProjectDirectorState = Field(default_factory=ProjectDirectorState)
    recentMessages: list[dict[str, Any]] = Field(default_factory=list)
    # Foundational AI state (Part A)
    cognitiveMode: str | None = None
    activeGoal: str | None = None
    workflowHold: bool = False
    preferenceExplainBeforeProduction: bool = False
    deferredQuestions: list[str] = Field(default_factory=list)
    lastIntentPrimary: str | None = None
    lastEvidenceSpans: list[str] = Field(default_factory=list)
    companionNeed: str | None = None
    advisoryDecisionState: str | None = None
    companionSupportStrategy: list[str] = Field(default_factory=list)


class InquiryDecision(BaseModel):
    should_ask: bool = False
    question: str | None = None
    mode: str = "conversation"


class ConversationSuccessScore(BaseModel):
    overall: float = 0.0
    checks: dict[str, bool] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ConversationCoreResult(BaseModel):
    plan: ConversationPlan
    snapshot: ProjectIntelligenceSnapshot
    reply: str
    score: ConversationSuccessScore
    timings: dict[str, float] = Field(default_factory=dict)
    events: list[dict[str, Any]] = Field(default_factory=list)
    # Foundation payloads (authoritative path)
    intent: dict[str, Any] = Field(default_factory=dict)
    dialoguePlan: dict[str, Any] = Field(default_factory=dict)
    conversationState: dict[str, Any] = Field(default_factory=dict)
    usesLlmPrimary: bool = False
    fallbackReply: str | None = None
    generationMessages: list[dict[str, str]] = Field(default_factory=list)
    companionSupport: dict[str, Any] = Field(default_factory=dict)
    companionAdvisory: dict[str, Any] = Field(default_factory=dict)
    companionDeviation: dict[str, Any] = Field(default_factory=dict)
    companionBlock: dict[str, Any] = Field(default_factory=dict)
    companionGroundingHints: dict[str, Any] = Field(default_factory=dict)
    wantsSpecialistConsult: bool = False
    # Personality / discovery layer (additive)
    relationshipProfile: dict[str, Any] = Field(default_factory=dict)
    creativeTemperature: dict[str, Any] = Field(default_factory=dict)
    intrigue: dict[str, Any] = Field(default_factory=dict)
    documentationResult: dict[str, Any] = Field(default_factory=dict)
    responseEvidence: dict[str, Any] = Field(default_factory=dict)
    discoveryQuestions: list[dict[str, Any]] = Field(default_factory=list)
    conversationActions: list[dict[str, str]] = Field(default_factory=list)
    projectPulse: dict[str, Any] = Field(default_factory=dict)
    whatChanged: list[str] = Field(default_factory=list)
    processingStages: list[str] = Field(default_factory=list)
    livingBrief: dict[str, Any] = Field(default_factory=dict)
    # Hands-on partnership layer (additive)
    artifactReadiness: list[dict[str, Any]] = Field(default_factory=list)
    activeDeliverable: dict[str, Any] = Field(default_factory=dict)
    journeyState: dict[str, Any] = Field(default_factory=dict)
    visionProfile: dict[str, Any] = Field(default_factory=dict)
    pitchPackage: dict[str, Any] = Field(default_factory=dict)
    marketingStrategy: dict[str, Any] = Field(default_factory=dict)
    collaborationProfile: dict[str, Any] = Field(default_factory=dict)
