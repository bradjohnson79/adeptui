"""Identity / character consistency validator (blocking on hard fails)."""

from __future__ import annotations

from typing import Any

from ..schemas import ValidationIssue, ValidatorFinding
from ._base import finding, fixture_score, fixture_status


class IdentityValidator:
    validator_id = "identity"

    def validate(
        self,
        *,
        context: dict[str, Any],
        requirements: dict[str, Any],
        provider_id: str,
    ) -> ValidatorFinding:
        refs = list(requirements.get("primaryReferences") or [])
        issues: list[ValidationIssue] = []

        if provider_id == "mock":
            score = fixture_score(context, self.validator_id, 94.0)
            blocking = bool((context.get("fixtureBlocking") or {}).get(self.validator_id))
            if not refs and score >= 90:
                issues.append(
                    ValidationIssue(
                        code="identity.no_primary_reference",
                        message="No primary Bible reference linked; identity check is weak.",
                        severity="warning",
                        correctable=True,
                    )
                )
                score = min(score, 88.0)
            if blocking or score < 80:
                issues.append(
                    ValidationIssue(
                        code="identity.mismatch",
                        message="Identity mismatch against primary reference (mock).",
                        severity="blocking",
                    )
                )
            status = fixture_status(score, blocking_fail=blocking or score < 80)
            return finding(
                self.validator_id,
                status=status,
                score=score,
                confidence=0.9,
                summary="Identity consistency (mock).",
                issues=issues,
                severity="blocking" if status == "fail" else ("warning" if status == "warn" else "info"),
                blocking=status == "fail",
                metrics={"primaryReferenceCount": len(refs)},
            )

        # Local: structured package diffs only; ML identity is stubbed inconclusive.
        if context.get("mlIdentityAvailable"):
            score = float(context.get("identityScore") or 0.0)
            status = "pass" if score >= 95 else ("warn" if score >= 80 else "fail")
            return finding(
                self.validator_id,
                status=status,
                score=score,
                confidence=0.7,
                summary="Identity score from local ML adapter.",
                blocking=status == "fail",
                metrics={"primaryReferenceCount": len(refs)},
            )

        if not refs:
            issues.append(
                ValidationIssue(
                    code="identity.no_primary_reference",
                    message="No primary references in generation package; cannot verify identity.",
                    severity="warning",
                    correctable=True,
                )
            )
        issues.append(
            ValidationIssue(
                code="identity.ml_unavailable",
                message="Local identity ML model is not configured; result is inconclusive (not a pass).",
                severity="warning",
                correctable=False,
            )
        )
        return finding(
            self.validator_id,
            status="inconclusive",
            score=0.0,
            confidence=0.2,
            summary="Identity ML unavailable — inconclusive.",
            issues=issues,
            severity="warning",
            correctable=True,
            blocking=False,
            metrics={"primaryReferenceCount": len(refs), "ml": "stub"},
        )
