"""Frozen DeliberationDecision contracts — cd-deliberation-v1.

Validated plan only. Does not execute. Classifiers are evidence inputs.
Law: converge existing brain; do not build a second brain.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


SCHEMA_VERSION: Literal["cd-deliberation-v1"] = "cd-deliberation-v1"


class DeliberationMode(str, Enum):
    FAST = "FAST"
    DEEP = "DEEP"


class TalkAskAct(str, Enum):
    """Final creator-facing behavior from one deliberation stage."""

    TALK = "TALK"
    ASK = "ASK"
    ACT = "ACT"
    STOP = "STOP"  # risk / STRICT unavailable / unresolved entity hard stop


class Commitment(str, Enum):
    """Normalized commitment across foundation / speech / pending paths."""

    NONE = "NONE"
    IMPLIED = "IMPLIED"  # imperative production verb with target
    EXPLICIT = "EXPLICIT"  # confirm-execute / pending yes / do it / go ahead


class RiskLevel(str, Enum):
    SAFE = "SAFE"
    REVERSIBLE = "REVERSIBLE"
    DESTRUCTIVE = "DESTRUCTIVE"


class SufficiencyResult(BaseModel):
    """Deliberation-facing sufficiency view (wraps foundation evaluate_sufficiency)."""

    contextSufficient: bool = True
    clarificationRequired: bool = False
    missingRequiredFields: list[str] = Field(default_factory=list)
    clarificationQuestion: str = ""
    resolvedAction: str = ""
    notes: list[str] = Field(default_factory=list)


class CapabilityCandidate(BaseModel):
    capabilityId: str = ""
    score: float = 0.0
    selected: bool = False
    rejectedWhy: str = ""
    source: str = ""  # unified|speech|canonical|visual_evidence|destructive


class RuntimePrecheck(BaseModel):
    consulted: bool = False
    ready: bool = True
    lockLevel: str = "UNLOCKED"
    selectedProvider: str = ""
    selectedModelId: str = ""
    error: str = ""
    reasonCodes: list[str] = Field(default_factory=list)


class RiskAssessment(BaseModel):
    level: RiskLevel = RiskLevel.SAFE
    confirmationRequired: bool = False
    destructive: bool = False
    confirmationQuestion: str = ""
    reasonCodes: list[str] = Field(default_factory=list)


class ReferentialResolution(BaseModel):
    matched: bool = False
    sourceArtifactType: str = ""
    targetArtifactType: str = ""
    subjectQualifier: str = ""  # e.g. corridor — structural, not special-cased
    memoryRequestId: str = ""
    preferCanonical: bool = True
    usedChatInherit: bool = False
    reasonCodes: list[str] = Field(default_factory=list)


class ExecutionPlanStub(BaseModel):
    """Handoff to execution core — deliberation stops here."""

    capabilityId: str = ""
    params: dict[str, Any] = Field(default_factory=dict)
    routeLock: dict[str, Any] = Field(default_factory=dict)
    memoryRequestId: str = ""
    inheritedFields: list[str] = Field(default_factory=list)
    overrides: dict[str, Any] = Field(default_factory=dict)
    preferCanonicalMemory: bool = True


class ResponsePlan(BaseModel):
    purpose: str = ""  # talk | ask | stop | plan  (plan = TALK speech; not a fourth act)
    clarificationQuestion: str = ""
    talkHint: str = ""
    prohibited: list[str] = Field(default_factory=list)


class DeliberationDecision(BaseModel):
    """Single validated plan for one turn. Does not execute."""

    schemaVersion: Literal["cd-deliberation-v1"] = SCHEMA_VERSION
    mode: DeliberationMode = DeliberationMode.FAST
    act: TalkAskAct = TalkAskAct.TALK
    reasonCodes: list[str] = Field(default_factory=list)

    intentKind: str = ""
    speechAct: str = ""
    commitment: Commitment = Commitment.NONE

    capabilityId: str = ""
    capabilityCandidates: list[CapabilityCandidate] = Field(default_factory=list)
    artifactType: str = ""

    projectId: str = ""
    sceneId: str = ""
    entityBindings: list[dict[str, Any]] = Field(default_factory=list)

    memoryRequestId: str = ""
    inheritedFields: list[str] = Field(default_factory=list)
    overrides: dict[str, Any] = Field(default_factory=dict)
    routeLock: dict[str, Any] = Field(default_factory=dict)

    sufficiency: SufficiencyResult = Field(default_factory=SufficiencyResult)
    risk: RiskAssessment = Field(default_factory=RiskAssessment)
    referential: ReferentialResolution = Field(default_factory=ReferentialResolution)
    runtimePrecheck: RuntimePrecheck = Field(default_factory=RuntimePrecheck)

    responsePlan: ResponsePlan = Field(default_factory=ResponsePlan)
    executionPlanStub: ExecutionPlanStub = Field(default_factory=ExecutionPlanStub)


    # --- Production Planner attachments (evidence / stubs only; not act bosses) ---
    intentEvidence: dict[str, Any] = Field(default_factory=dict)
    productionPlan: dict[str, Any] = Field(default_factory=dict)
    selectivePreflight: dict[str, Any] = Field(default_factory=dict)
    pendingBrief: dict[str, Any] = Field(default_factory=dict)

    classifierSources: list[str] = Field(default_factory=list)
    competingAuthorityFlags: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    failedExecutionSummary: str = ""
    effortHint: str = ""  # FAST|DEEP mirror of mode for stream metadata

    def should_dispatch(self) -> bool:
        return self.act == TalkAskAct.ACT and bool(self.capabilityId)

    def should_ask(self) -> bool:
        return self.act == TalkAskAct.ASK

    def should_talk(self) -> bool:
        return self.act == TalkAskAct.TALK

    def should_stop(self) -> bool:
        return self.act == TalkAskAct.STOP
