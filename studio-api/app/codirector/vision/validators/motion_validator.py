"""Motion validator (video profiles only)."""

from __future__ import annotations

from typing import Any

from ..schemas import ValidationIssue, ValidatorFinding
from ._base import finding, fixture_score, fixture_status


class MotionValidator:
    validator_id = "motion"

    def validate(
        self,
        *,
        context: dict[str, Any],
        requirements: dict[str, Any],
        provider_id: str,
    ) -> ValidatorFinding:
        issues: list[ValidationIssue] = []
        media_kind = str(context.get("mediaKind") or requirements.get("mediaKind") or "image")

        if media_kind != "video":
            return finding(
                self.validator_id,
                status="skipped",
                score=0.0,
                confidence=1.0,
                summary="Motion skipped for non-video assets.",
                issues=[],
                metrics={"mediaKind": media_kind},
            )

        if provider_id == "mock":
            score = fixture_score(context, self.validator_id, 90.0)
            status = fixture_status(score)
            if status != "pass":
                issues.append(
                    ValidationIssue(
                        code="motion.fixture",
                        message="Motion issues in mock fixture.",
                        severity="warning" if status == "warn" else "error",
                    )
                )
            return finding(
                self.validator_id,
                status=status,
                score=score,
                confidence=0.8,
                summary="Motion checks (mock).",
                issues=issues,
            )

        if not context.get("mlMotionAvailable"):
            issues.append(
                ValidationIssue(
                    code="motion.ml_unavailable",
                    message="Local motion ML unavailable; inconclusive (not a pass).",
                    severity="info",
                    correctable=False,
                )
            )
            return finding(
                self.validator_id,
                status="inconclusive",
                score=0.0,
                confidence=0.15,
                summary="Motion inconclusive.",
                issues=issues,
            )

        score = float(context.get("motionScore") or 90.0)
        status = "pass" if score >= 95 else ("warn" if score >= 80 else "fail")
        return finding(
            self.validator_id,
            status=status,
            score=score,
            confidence=0.65,
            summary="Motion checks (local ML).",
            issues=issues,
        )
