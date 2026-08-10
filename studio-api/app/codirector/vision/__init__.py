"""Vision Validation — production-aware media quality and continuity analysis.

Architecture:
                    VISION VALIDATION ENGINE
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
          IMAGE QA         VIDEO QA        FRAME QA
              │               │               │
              └───────────────┼───────────────┘
                              ▼
                    CONTINUITY ANALYZER
                              │
                  ┌───────────┴───────────┐
                  ▼                       ▼
             LIP-SYNC QA             HUMAN REVIEW
                  │                       │
                  └───────────┬───────────┘
                              ▼
                       VALIDATION RESULT
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ValidationStatus(str, Enum):
    PASSED = "PASSED"
    WARNING = "WARNING"
    FAILED = "FAILED"
    NOT_APPLICABLE = "N/A"
    SKIPPED = "SKIPPED"


class ValidationCheck(BaseModel):
    """Result of a single validation check (e.g. character continuity, composition)."""
    name: str
    status: ValidationStatus = ValidationStatus.SKIPPED
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    details: str = ""
    category: str = "general"  # "continuity", "quality", "adherence", "sync"


class ValidationResult(BaseModel):
    """Complete validation result for a single media asset.

    Human authority is absolute — this result is advisory.
    The creator always decides via Accept / Review / Retake.
    """
    asset_id: str
    overall_status: ValidationStatus = ValidationStatus.SKIPPED
    overall_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    checks: list[ValidationCheck] = Field(default_factory=list)
    advisory: bool = True
    human_review_required: bool = False
    errors: list[str] = Field(default_factory=list)
    asset_type: str = "unknown"  # "image", "video", "frame", "audio"
    duration_ms: int = 0

    @property
    def passed(self) -> bool:
        return self.overall_status in (ValidationStatus.PASSED, ValidationStatus.NOT_APPLICABLE)

    @property
    def needs_human_review(self) -> bool:
        return self.human_review_required or any(
            c.status in (ValidationStatus.FAILED, ValidationStatus.WARNING)
            for c in self.checks
        )
