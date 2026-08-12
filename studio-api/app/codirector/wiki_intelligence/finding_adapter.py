"""Adapt SpecialistFinding / heuristic signals → WikiSpecialistFinding."""

from __future__ import annotations

from typing import Any

from .classification import classify_entity_type, target_section_for_entity
from .contracts import (
    CanonState,
    StructuredFact,
    WikiConflict,
    WikiSpecialistFinding,
)


def adapt_specialist_finding(
    *,
    specialist_id: str,
    source_id: str,
    finding: Any,
    seed_text: str = "",
) -> WikiSpecialistFinding:
    """Convert intelligence SpecialistFinding (or dict) into WikiSpecialistFinding."""
    if finding is None:
        return WikiSpecialistFinding(
            specialistId=specialist_id,
            sourceId=source_id,
            targetRecordType=classify_entity_type(seed_text),
            recommendedAction="NO_ACTION",
        )

    if hasattr(finding, "model_dump"):
        data = finding.model_dump(mode="json")
    elif isinstance(finding, dict):
        data = finding
    else:
        data = {"summary": str(finding)}

    summary = str(data.get("summary") or data.get("recommendation") or seed_text or "").strip()
    entity_type = classify_entity_type(summary or seed_text)
    facts: list[StructuredFact] = []
    if summary:
        facts.append(
            StructuredFact(
                statement=summary[:400],
                field="summary",
                canonState="INFERRED",
                confidence=float(data.get("confidence") or 0.55),
                sourceIds=[source_id],
            )
        )
    for req in data.get("requirements") or []:
        if isinstance(req, str) and req.strip():
            facts.append(
                StructuredFact(
                    statement=req.strip()[:300],
                    field="requirement",
                    canonState="PROPOSED",
                    confidence=0.5,
                    sourceIds=[source_id],
                )
            )

    conflicts: list[WikiConflict] = []
    for risk in data.get("risks") or data.get("blockingIssues") or []:
        if isinstance(risk, str) and risk.strip():
            conflicts.append(
                WikiConflict(
                    conflictType="specialist_risk",
                    description=risk.strip()[:300],
                    severity="warning",
                )
            )

    action = "UPDATE" if facts else "NO_ACTION"
    if conflicts:
        action = "FLAG_CONFLICT"
    conf = float(data.get("confidence") or 0.55)
    canon: CanonState = "INFERRED"
    if conf >= 0.85 and not conflicts:
        canon = "PROPOSED"

    return WikiSpecialistFinding(
        specialistId=specialist_id,
        sourceId=source_id,
        targetRecordType=entity_type,
        targetRecordId=None,
        facts=facts,
        inferredInsights=[],
        conflicts=conflicts,
        missingInformation=[],
        productionUses=[target_section_for_entity(entity_type)],
        recommendedAction=action,  # type: ignore[arg-type]
        confidence=conf,
        canonRecommendation=canon,
    )


def heuristic_department_finding(
    *,
    specialist_id: str,
    source_id: str,
    text: str,
    problem_type: str,
) -> WikiSpecialistFinding:
    """Deterministic structured finding for reorganization when live LLM specialist is skipped."""
    entity_type = classify_entity_type(text)
    action = "RECLASSIFY"
    if problem_type == "duplicate_character":
        action = "MERGE"
    elif problem_type == "false_character":
        action = "REJECT"
    elif problem_type == "preference_leak":
        action = "RECLASSIFY"
    elif problem_type == "enrichment":
        action = "UPDATE"

    return WikiSpecialistFinding(
        specialistId=specialist_id,
        sourceId=source_id,
        targetRecordType=entity_type,
        facts=[
            StructuredFact(
                statement=f"{specialist_id} reviewed: {text[:240]}",
                field="reorganize",
                canonState="INFERRED",
                confidence=0.7,
                sourceIds=[source_id],
            )
        ],
        productionUses=[target_section_for_entity(entity_type)],
        recommendedAction=action,  # type: ignore[arg-type]
        confidence=0.7,
        canonRecommendation="INFERRED",
    )
