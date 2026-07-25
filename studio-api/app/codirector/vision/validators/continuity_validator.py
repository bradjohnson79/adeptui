"""Continuity validator against Bible continuity constraints."""

from __future__ import annotations

from typing import Any

from ..schemas import ValidationIssue, ValidatorFinding
from ._base import finding, fixture_score, fixture_status


class ContinuityValidator:
    validator_id = "continuity"

    def validate(
        self,
        *,
        context: dict[str, Any],
        requirements: dict[str, Any],
        provider_id: str,
    ) -> ValidatorFinding:
        continuity = list(requirements.get("continuityConstraints") or [])
        conflicts = list(requirements.get("conflicts") or [])
        issues: list[ValidationIssue] = []

        if provider_id == "mock":
            score = fixture_score(context, self.validator_id, 93.0)
            if conflicts:
                score = min(score, 82.0)
                issues.append(
                    ValidationIssue(
                        code="continuity.bible_conflicts",
                        message=f"{len(conflicts)} Bible conflict(s) present in generation package.",
                        severity="warning",
                    )
                )
            status = fixture_status(score)
            return finding(
                self.validator_id,
                status=status,
                score=score,
                confidence=0.88,
                summary="Continuity checks (mock).",
                issues=issues,
                severity="warning" if status != "pass" else "info",
                metrics={"constraintCount": len(continuity), "conflictCount": len(conflicts)},
            )

        score = 95.0
        if conflicts:
            score -= min(40.0, 10.0 * len(conflicts))
            issues.append(
                ValidationIssue(
                    code="continuity.bible_conflicts",
                    message=f"{len(conflicts)} unresolved conflict(s) in generation package.",
                    severity="error",
                )
            )
        if continuity:
            issues.append(
                ValidationIssue(
                    code="continuity.open_constraints",
                    message=f"{len(continuity)} open continuity constraint(s) require human review.",
                    severity="warning",
                )
            )
            score = min(score, 90.0)
        else:
            issues.append(
                ValidationIssue(
                    code="continuity.no_constraints",
                    message="No scene continuity constraints supplied; structured check is limited.",
                    severity="info",
                    correctable=False,
                )
            )

        # Pixel-level continuity ML is not available locally in M2.5.
        if not context.get("mlContinuityAvailable"):
            issues.append(
                ValidationIssue(
                    code="continuity.ml_unavailable",
                    message="Local continuity ML unavailable; structured package checks only.",
                    severity="info",
                    correctable=False,
                )
            )

        status = "pass" if score >= 95 and not conflicts else ("warn" if score >= 80 else "fail")
        return finding(
            self.validator_id,
            status=status,
            score=score,
            confidence=0.55,
            summary="Continuity checks (structured package).",
            issues=issues,
            severity="warning" if status != "pass" else "info",
            metrics={"constraintCount": len(continuity), "conflictCount": len(conflicts)},
        )
