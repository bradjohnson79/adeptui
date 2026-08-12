"""Targeted correction planning from deviation findings."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .deviation_report import CharacterDeviationReport
from .reference_roles import ReferenceRole
from .seed_policy import SeedPolicy


class CorrectionInstruction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension: ReferenceRole
    priority: str
    keep_instruction: str
    change_instruction: str
    prompt_additions: list[str] = Field(default_factory=list)
    negative_additions: list[str] = Field(default_factory=list)
    reference_roles: list[ReferenceRole] = Field(default_factory=list)


class CharacterCorrectionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    report_subject_id: str
    source_asset_id: str
    next_seed_policy: SeedPolicy
    instructions: list[CorrectionInstruction] = Field(default_factory=list)
    escalation_notes: list[str] = Field(default_factory=list)


def build_correction_plan(report: CharacterDeviationReport) -> CharacterCorrectionPlan:
    instructions: list[CorrectionInstruction] = []
    for finding in report.findings:
        if finding.status not in {"review", "drift"}:
            continue
        instructions.append(
            CorrectionInstruction(
                dimension=finding.dimension,
                priority="critical" if finding.severity in {"critical", "major"} else "targeted",
                keep_instruction=f"Preserve approved {finding.dimension.value} identity signals from the locked references.",
                change_instruction=finding.correction_goal or finding.observed_difference,
                prompt_additions=[
                    f"Match approved {finding.dimension.value} reference before introducing new variation.",
                ],
                negative_additions=[
                    f"Do not introduce unapproved {finding.dimension.value} changes.",
                ],
                reference_roles=list(finding.expected_reference_roles),
            )
        )

    escalation_notes: list[str] = []
    if any(finding.status == "not_assessable" for finding in report.findings):
        escalation_notes.append("Acquire a better-matched reference or angle before claiming continuity.")
    if not instructions:
        escalation_notes.append("No targeted correction pass was generated because no actionable drift was detected.")

    return CharacterCorrectionPlan(
        report_subject_id=report.subject_id,
        source_asset_id=report.candidate_asset_id,
        next_seed_policy=SeedPolicy.REFINE if instructions else SeedPolicy.PRODUCTION_CONTINUITY,
        instructions=instructions,
        escalation_notes=escalation_notes,
    )
