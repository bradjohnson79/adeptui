"""Contracts for the Production State Projection — per-field provenance, 14-domain enum, and the
projection DTO. Law 4: projection-only, never persists.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ProjectionDomain(str, Enum):
    """The 14 authoritative domains composing a production state projection (§2.1)."""

    PROJECT = "PROJECT"
    CHARACTERS = "CHARACTERS"
    LOCATIONS = "LOCATIONS"
    SCRIPT = "SCRIPT"
    SCENES = "SCENES"
    PRODUCTION_BIBLE = "PRODUCTION_BIBLE"
    WIKI = "WIKI"
    DECISIONS = "DECISIONS"
    TIMELINE = "TIMELINE"
    IMAGE_PLANNING = "IMAGE_PLANNING"
    MULTI_SHOT = "MULTI_SHOT"
    MAGI_READINESS = "MAGI_READINESS"
    SESSION_CONTEXT = "SESSION_CONTEXT"
    PRODUCTION_LIFECYCLE = "PRODUCTION_LIFECYCLE"


ProvenanceTaxonomy = Literal[
    "creator-stated",
    "creator-approved",
    "system-derived",
    "ai-inferred",
    "session-only",
    "project-persisted",
]

ALLOWED_PROVENANCE: frozenset[str] = frozenset({
    "creator-stated",
    "creator-approved",
    "system-derived",
    "ai-inferred",
    "session-only",
    "project-persisted",
})


class ProvenanceField(BaseModel):
    """A single projected field with its authoritative source and provenance classification."""

    value: Any = None
    source: str = ""
    provenance: ProvenanceTaxonomy = "system-derived"
    updated_at: datetime | None = None


class StageEvidence(BaseModel):
    """A candidate stage-evidence entry contributing to the projection's evidence trace."""

    source: str = ""
    raw_label: str = ""
    mapped_label: str = ""
    agreed: bool = False
    stale: bool = False


class ProductionState(BaseModel):
    """Read-through projection of all 14 authoritative domains for a project.

    Composed on demand from authoritative stores. Never persisted (Law 4).
    Every domain value is a dict[str, ProvenanceField] — per-field provenance is mandatory.
    """

    domains: dict[ProjectionDomain, dict[str, ProvenanceField]] = Field(default_factory=dict)
    evidenceTrace: list[dict[str, Any]] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
