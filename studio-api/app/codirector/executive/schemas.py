"""Pydantic schemas for Production Executive APIs."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from .models import JobType


class CreateJobRequest(BaseModel):
    type: JobType  # pydantic will coerce string
    projectId: str
    owner: str = "user"
    sceneId: Optional[str] = None
    timelineItemId: Optional[str] = None
    priority: int = Field(default=100, ge=0, le=1000)
    capabilityRequirements: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    dependsOnJobIds: list[str] = Field(default_factory=list)
    idempotencyKey: Optional[str] = None
    maxAttempts: int = Field(default=3, ge=1, le=20)
    provider: Optional[str] = None


class JobActionRequest(BaseModel):
    actor: str = "user"
    reason: str = ""


class MarkApprovalRequest(BaseModel):
    """Signal that M2.2 proposal approval completed — Executive never approves itself."""

    proposalId: str
    approved: bool = True
    actor: str = "user"
    reason: str = "proposal_approved"


class JobOut(BaseModel):
    id: str
    type: str
    owner: str
    projectId: str
    sceneId: Optional[str] = None
    timelineItemId: Optional[str] = None
    priority: int
    status: str
    capabilityRequirements: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    result: Optional[dict[str, Any]] = None
    errorMessage: Optional[str] = None
    idempotencyKey: Optional[str] = None
    attemptsCount: int = 0
    maxAttempts: int = 3
    provider: Optional[str] = None
    blockedReason: Optional[str] = None
    dependsOnJobIds: list[str] = Field(default_factory=list)
    productionContextId: Optional[str] = None
    productionContext: Optional[dict[str, Any]] = None
    createdAt: str
    updatedAt: str
    startedAt: Optional[str] = None
    completedAt: Optional[str] = None


class AttemptOut(BaseModel):
    id: str
    jobId: str
    attemptN: int
    provider: Optional[str] = None
    startedAt: str
    finishedAt: Optional[str] = None
    durationMs: Optional[int] = None
    errors: list[Any] = Field(default_factory=list)
    capabilitySnapshot: dict[str, Any] = Field(default_factory=dict)
    result: Optional[dict[str, Any]] = None
    outcome: str


class EventOut(BaseModel):
    id: str
    jobId: Optional[str] = None
    projectId: str
    eventType: str
    payload: dict[str, Any] = Field(default_factory=dict)
    createdAt: str


class NotificationOut(BaseModel):
    id: str
    projectId: str
    jobId: Optional[str] = None
    eventId: Optional[str] = None
    level: str
    title: str
    body: str
    read: bool
    createdAt: str


class AuditOut(BaseModel):
    id: str
    jobId: str
    fromStatus: Optional[str] = None
    toStatus: str
    actor: str
    reason: str
    detail: dict[str, Any] = Field(default_factory=dict)
    createdAt: str


class SceneProgressOut(BaseModel):
    sceneId: str
    projectId: str
    totalJobs: int
    completed: int
    failed: int
    blocked: int
    running: int
    queued: int
    needsReview: int
    percentComplete: float
    derivedFromJobs: bool = True
