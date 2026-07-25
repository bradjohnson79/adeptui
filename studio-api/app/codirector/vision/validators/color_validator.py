"""Color palette / grade validator."""

from __future__ import annotations

from typing import Any

from ..schemas import ValidationIssue, ValidatorFinding
from ._base import finding, fixture_score, fixture_status


class ColorValidator:
    validator_id = "color"

    def validate(
        self,
        *,
        context: dict[str, Any],
        requirements: dict[str, Any],
        provider_id: str,
    ) -> ValidatorFinding:
        issues: list[ValidationIssue] = []
        style = dict(requirements.get("styleConstraints") or {})

        if provider_id == "mock":
            score = fixture_score(context, self.validator_id, 91.0)
            status = fixture_status(score)
            if status != "pass":
                issues.append(
                    ValidationIssue(
                        code="color.fixture",
                        message="Color grade deviation in mock fixture.",
                        severity="warning" if status == "warn" else "error",
                    )
                )
            return finding(
                self.validator_id,
                status=status,
                score=score,
                confidence=0.8,
                summary="Color checks (mock).",
                issues=issues,
            )

        metrics = dict(context.get("technicalMetrics") or {})
        saturation = metrics.get("meanSaturation")
        if saturation is None and not context.get("mlColorAvailable"):
            issues.append(
                ValidationIssue(
                    code="color.ml_unavailable",
                    message="Local color ML unavailable; inconclusive (not a pass).",
                    severity="info",
                    correctable=False,
                )
            )
            return finding(
                self.validator_id,
                status="inconclusive",
                score=0.0,
                confidence=0.2,
                summary="Color inconclusive.",
                issues=issues,
                metrics={"styleKeys": list(style.keys())[:8]},
            )

        score = 92.0
        if saturation is not None and float(saturation) < 0.05:
            score = 84.0
            issues.append(
                ValidationIssue(
                    code="color.low_saturation",
                    message="Very low mean saturation detected.",
                    severity="warning",
                )
            )
        status = "pass" if score >= 95 else ("warn" if score >= 80 else "fail")
        return finding(
            self.validator_id,
            status=status,
            score=score,
            confidence=0.55,
            summary="Color checks (local metrics).",
            issues=issues,
            metrics={"meanSaturation": saturation},
        )
