"""Co-Director M2.4 production intelligence orchestration."""

from __future__ import annotations

from typing import Any

from .schemas import (
    ContextFact,
    ContextPackage,
    IntentClassification,
    ProductionPlan,
    ProposedToolAction,
    SpecialistFinding,
    SynthesisResult,
)

__all__ = [
    "ContextFact",
    "ContextPackage",
    "IntentClassification",
    "IntelligenceService",
    "ProductionPlan",
    "ProposedToolAction",
    "SpecialistFinding",
    "SynthesisResult",
]


def __getattr__(name: str) -> Any:
    # Lazy export avoids circular imports (vision.store -> intelligence.schemas -> service -> tools -> vision).
    if name == "IntelligenceService":
        from .service import IntelligenceService

        return IntelligenceService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
