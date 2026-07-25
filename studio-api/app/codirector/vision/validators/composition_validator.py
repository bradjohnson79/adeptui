"""Composition validator."""

from __future__ import annotations

from typing import Any

from ..schemas import ValidationIssue, ValidatorFinding
from ._base import finding, fixture_score, fixture_status


class CompositionValidator:
    validator_id = "composition"

    def validate(
        self,
        *,
        context: dict[str, Any],
        requirements: dict[str, Any],
        provider_id: str,
    ) -> ValidatorFinding:
        issues: list[ValidationIssue] = []
        if provider_id == "mock":
            score = fixture_score(context, self.validator_id, 90.0)
            status = fixture_status(score)
            if status != "pass":
                issues.append(
                    ValidationIssue(
                        code="composition.fixture",
                        message="Composition issues in mock fixture.",
                        severity="warning" if status == "warn" else "error",
                    )
                )
            return finding(
                self.validator_id,
                status=status,
                score=score,
                confidence=0.8,
                summary="Composition checks (mock).",
                issues=issues,
            )

        metrics = dict(context.get("technicalMetrics") or {})
        aspect = metrics.get("aspectRatio")
        score = 90.0
        if aspect:
            score = 93.0
        if not context.get("mlCompositionAvailable"):
            issues.append(
                ValidationIssue(
                    code="composition.ml_unavailable",
                    message="Local composition ML unavailable; limited geometric checks only.",
                    severity="info",
                    correctable=False,
                )
            )
            return finding(
                self.validator_id,
                status="inconclusive" if not aspect else "warn",
                score=0.0 if not aspect else score,
                confidence=0.25,
                summary="Composition limited / inconclusive.",
                issues=issues,
                metrics={"aspectRatio": aspect},
            )

        score = float(context.get("compositionScore") or score)
        status = "pass" if score >= 95 else ("warn" if score >= 80 else "fail")
        return finding(
            self.validator_id,
            status=status,
            score=score,
            confidence=0.65,
            summary="Composition checks (local).",
            issues=issues,
        )
