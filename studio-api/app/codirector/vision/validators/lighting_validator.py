"""Lighting consistency validator."""

from __future__ import annotations

from typing import Any

from ..schemas import ValidationIssue, ValidatorFinding
from ._base import finding, fixture_score, fixture_status


class LightingValidator:
    validator_id = "lighting"

    def validate(
        self,
        *,
        context: dict[str, Any],
        requirements: dict[str, Any],
        provider_id: str,
    ) -> ValidatorFinding:
        style = dict(requirements.get("styleConstraints") or {})
        issues: list[ValidationIssue] = []

        if provider_id == "mock":
            score = fixture_score(context, self.validator_id, 92.0)
            status = fixture_status(score)
            if status != "pass":
                issues.append(
                    ValidationIssue(
                        code="lighting.fixture",
                        message="Lighting deviation reported by mock fixture.",
                        severity="warning" if status == "warn" else "error",
                    )
                )
            return finding(
                self.validator_id,
                status=status,
                score=score,
                confidence=0.85,
                summary="Lighting checks (mock).",
                issues=issues,
                severity="warning" if status != "pass" else "info",
            )

        metrics = dict(context.get("technicalMetrics") or {})
        mean_luma = float(metrics.get("meanLuma") or -1.0)
        score = 92.0
        if mean_luma >= 0:
            if mean_luma < 30 or mean_luma > 220:
                score = 78.0
                issues.append(
                    ValidationIssue(
                        code="lighting.exposure_band",
                        message=f"Mean luma {mean_luma:.1f} outside preferred band.",
                        severity="warning",
                    )
                )
        else:
            issues.append(
                ValidationIssue(
                    code="lighting.metrics_missing",
                    message="Lighting metrics unavailable; inconclusive.",
                    severity="info",
                    correctable=False,
                )
            )
            return finding(
                self.validator_id,
                status="inconclusive",
                score=0.0,
                confidence=0.2,
                summary="Lighting inconclusive.",
                issues=issues,
            )

        if style.get("lighting") and not context.get("mlLightingAvailable"):
            issues.append(
                ValidationIssue(
                    code="lighting.ml_unavailable",
                    message="Style lighting cue present but local lighting ML is stubbed.",
                    severity="info",
                    correctable=False,
                )
            )

        status = "pass" if score >= 95 else ("warn" if score >= 80 else "fail")
        return finding(
            self.validator_id,
            status=status,
            score=score,
            confidence=0.6,
            summary="Lighting checks (local metrics).",
            issues=issues,
            severity="warning" if status != "pass" else "info",
            metrics={"meanLuma": mean_luma},
        )
