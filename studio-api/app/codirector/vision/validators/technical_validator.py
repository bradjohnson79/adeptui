"""Technical quality validator (runs first; blocking on hard fails)."""

from __future__ import annotations

from typing import Any

from ..schemas import ValidationIssue, ValidatorFinding
from ._base import finding, fixture_score, fixture_status


class TechnicalValidator:
    validator_id = "technical"

    def validate(
        self,
        *,
        context: dict[str, Any],
        requirements: dict[str, Any],
        provider_id: str,
    ) -> ValidatorFinding:
        issues: list[ValidationIssue] = []
        metrics = dict(context.get("technicalMetrics") or {})

        if provider_id == "mock":
            score = fixture_score(context, self.validator_id, 96.0)
            blocking = bool((context.get("fixtureBlocking") or {}).get(self.validator_id))
            if score < 80 or blocking:
                issues.append(
                    ValidationIssue(
                        code="technical.fixture_fail",
                        message="Mock fixture reports a blocking technical failure.",
                        severity="blocking",
                        correctable=True,
                    )
                )
            elif score < 95:
                issues.append(
                    ValidationIssue(
                        code="technical.fixture_warn",
                        message="Mock fixture reports technical warnings.",
                        severity="warning",
                    )
                )
            status = fixture_status(score, blocking_fail=blocking or score < 80)
            return finding(
                self.validator_id,
                status=status,
                score=score,
                confidence=0.95,
                summary="Technical checks (mock fixture).",
                issues=issues,
                severity="blocking" if status == "fail" else ("warning" if status == "warn" else "info"),
                correctable=True,
                blocking=status == "fail",
                metrics=metrics or {"source": "mock"},
            )

        # Local provider: use OpenCV/Pillow metrics when present.
        width = int(metrics.get("width") or 0)
        height = int(metrics.get("height") or 0)
        blur = float(metrics.get("laplacianVariance") or 0.0)
        mean_luma = float(metrics.get("meanLuma") or -1.0)
        score = 100.0

        if width <= 0 or height <= 0:
            issues.append(
                ValidationIssue(
                    code="technical.unreadable",
                    message="Asset could not be decoded for technical analysis.",
                    severity="blocking",
                    correctable=False,
                )
            )
            return finding(
                self.validator_id,
                status="fail",
                score=0.0,
                confidence=0.9,
                summary="Unreadable asset.",
                issues=issues,
                severity="blocking",
                correctable=False,
                blocking=True,
                metrics=metrics,
            )

        min_w = int((requirements.get("minWidth") or 256))
        min_h = int((requirements.get("minHeight") or 256))
        if width < min_w or height < min_h:
            score -= 25
            issues.append(
                ValidationIssue(
                    code="technical.resolution_low",
                    message=f"Resolution {width}x{height} below minimum {min_w}x{min_h}.",
                    severity="error",
                )
            )

        if blur > 0 and blur < 40:
            score -= 30
            issues.append(
                ValidationIssue(
                    code="technical.blur",
                    message=f"Image appears soft (laplacian variance={blur:.1f}).",
                    severity="error",
                )
            )

        if 0 <= mean_luma < 15 or mean_luma > 245:
            score -= 20
            issues.append(
                ValidationIssue(
                    code="technical.exposure",
                    message=f"Exposure outlier (mean luma={mean_luma:.1f}).",
                    severity="warning",
                )
            )

        status = "pass" if score >= 95 and not issues else ("warn" if score >= 80 else "fail")
        blocking = status == "fail"
        return finding(
            self.validator_id,
            status=status,
            score=score,
            confidence=0.85,
            summary="Technical checks (local metrics).",
            issues=issues,
            severity="blocking" if blocking else ("warning" if status == "warn" else "info"),
            correctable=True,
            blocking=blocking,
            metrics=metrics,
        )
