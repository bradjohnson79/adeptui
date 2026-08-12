"""Honest character deviation reporting without fake numeric precision."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .reference_roles import ReferenceRole

DeviationStatus = Literal["match", "review", "drift", "not_assessable"]
DeviationSeverity = Literal["informational", "minor", "major", "critical"]
ComparativeScore = Literal["aligned", "minor_drift", "clear_drift", "not_assessable"]
ConfidenceLabel = Literal["low", "medium", "high"]


class CharacterDeviationFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension: ReferenceRole
    status: DeviationStatus
    severity: DeviationSeverity
    comparative_score: ComparativeScore
    confidence: ConfidenceLabel | None = None
    expected_reference_roles: list[ReferenceRole] = Field(default_factory=list)
    observed_difference: str
    correction_goal: str | None = None
    evidence_summary: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_score_semantics(self) -> "CharacterDeviationFinding":
        if self.status == "not_assessable" and self.comparative_score != "not_assessable":
            raise ValueError("not_assessable findings must use the not_assessable comparative score")
        if self.status == "match" and self.comparative_score != "aligned":
            raise ValueError("match findings must use the aligned comparative score")
        if self.status == "drift" and self.comparative_score == "aligned":
            raise ValueError("drift findings cannot claim aligned scoring")
        return self


class CharacterDeviationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    project_id: str = Field(..., min_length=1)
    subject_id: str = Field(..., min_length=1)
    subject_label: str = Field(..., min_length=1)
    candidate_asset_id: str = Field(..., min_length=1)
    evaluator_key: str = Field(..., min_length=1)
    evaluator_version: str = Field(..., min_length=1)
    recipe_id: str | None = None
    overall_status: DeviationStatus
    overall_comparative_score: ComparativeScore
    summary: str
    findings: list[CharacterDeviationFinding] = Field(default_factory=list)
    requires_human_review: bool = True


def build_deviation_report(
    *,
    project_id: str,
    subject_id: str,
    subject_label: str,
    candidate_asset_id: str,
    evaluator_key: str,
    evaluator_version: str,
    findings: list[CharacterDeviationFinding],
    recipe_id: str | None = None,
) -> CharacterDeviationReport:
    statuses = {finding.status for finding in findings}
    worst_severity = next(
        (
            severity
            for severity in ("critical", "major", "minor", "informational")
            if any(finding.severity == severity for finding in findings)
        ),
        "informational",
    )

    if "drift" in statuses:
        overall_status: DeviationStatus = "drift"
        overall_comparative_score: ComparativeScore = "clear_drift"
        summary = "Clear character drift detected; targeted correction is required before production continuity."
    elif "review" in statuses:
        overall_status = "review"
        overall_comparative_score = "minor_drift"
        summary = "Differences need review before the result can be treated as continuity-safe."
    elif statuses == {"not_assessable"} or not findings:
        overall_status = "not_assessable"
        overall_comparative_score = "not_assessable"
        summary = "The current evidence is insufficient for a reliable continuity judgment."
    else:
        overall_status = "match"
        overall_comparative_score = "aligned"
        summary = "Observed identity signals align with approved references at the current evidence level."

    requires_human_review = overall_status in {"review", "drift", "not_assessable"} or worst_severity in {
        "major",
        "critical",
    }

    return CharacterDeviationReport(
        project_id=project_id,
        subject_id=subject_id,
        subject_label=subject_label,
        candidate_asset_id=candidate_asset_id,
        evaluator_key=evaluator_key,
        evaluator_version=evaluator_version,
        recipe_id=recipe_id,
        overall_status=overall_status,
        overall_comparative_score=overall_comparative_score,
        summary=summary,
        findings=findings,
        requires_human_review=requires_human_review,
    )
