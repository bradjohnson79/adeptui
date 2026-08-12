"""Frozen canonical RouteDecision schema — §3 of the Phase 3 router contract."""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class RouteActionClass(str, Enum):
    DISCUSS = "DISCUSS"
    NAVIGATE = "NAVIGATE"
    READ_INSPECT = "READ_INSPECT"
    MODIFY_KNOWLEDGE = "MODIFY_KNOWLEDGE"
    PROPOSE_CREATIVE_CHANGE = "PROPOSE_CREATIVE_CHANGE"
    EXECUTE_PRODUCTION = "EXECUTE_PRODUCTION"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    CLARIFY = "CLARIFY"
    AMBIGUOUS = "AMBIGUOUS"
    UNKNOWN = "UNKNOWN"


class RouteDecision(BaseModel):
    actionClass: RouteActionClass
    target: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    ambiguity: Optional[list[str]] = None
    clarificationOptions: Optional[list[str]] = None
    executionLane: Optional[str] = None
    destructive: bool = False
    capabilityAvailable: bool = True
    supportedAlternative: Optional[str] = None
    evidence: list[str] = Field(default_factory=list)
    classifierSource: Literal["deterministic", "semantic", "contextual"] = "deterministic"
    targetWorkspace: Optional[str] = None
    targetToolIds: Optional[list[str]] = None
    writeAllowed: bool = False
