"""Camera / framing grammar validator."""

from __future__ import annotations

from typing import Any

from ..schemas import ValidationIssue, ValidatorFinding
from ._base import finding, fixture_score, fixture_status


class CameraValidator:
    validator_id = "camera"

    def validate(
        self,
        *,
        context: dict[str, Any],
        requirements: dict[str, Any],
        provider_id: str,
    ) -> ValidatorFinding:
        issues: list[ValidationIssue] = []
        if provider_id == "mock":
            score = fixture_score(context, self.validator_id, 91.0)
            status = fixture_status(score)
            if status != "pass":
                issues.append(
                    ValidationIssue(
                        code="camera.fixture",
                        message="Camera/framing deviation in mock fixture.",
                        severity="warning" if status == "warn" else "error",
                    )
                )
            return finding(
                self.validator_id,
                status=status,
                score=score,
                confidence=0.8,
                summary="Camera checks (mock).",
                issues=issues,
            )

        if not context.get("mlCameraAvailable"):
            issues.append(
                ValidationIssue(
                    code="camera.ml_unavailable",
                    message="Local camera/framing ML unavailable; inconclusive (not a pass).",
                    severity="info",
                    correctable=False,
                )
            )
            return finding(
                self.validator_id,
                status="inconclusive",
                score=0.0,
                confidence=0.15,
                summary="Camera ML unavailable.",
                issues=issues,
                metrics={"planHints": bool(requirements.get("shotPurpose"))},
            )

        score = float(context.get("cameraScore") or 90.0)
        status = "pass" if score >= 95 else ("warn" if score >= 80 else "fail")
        return finding(
            self.validator_id,
            status=status,
            score=score,
            confidence=0.7,
            summary="Camera checks (local ML).",
            issues=issues,
        )
