"""Shared helpers for modular validators."""

from __future__ import annotations

from typing import Any

from ..schemas import ValidationIssue, ValidatorFinding


def finding(
    validator_id: str,
    *,
    status: str,
    score: float,
    confidence: float,
    summary: str,
    issues: list[ValidationIssue] | None = None,
    severity: str = "info",
    correctable: bool = True,
    blocking: bool = False,
    metrics: dict[str, Any] | None = None,
) -> ValidatorFinding:
    return ValidatorFinding(
        validatorId=validator_id,
        status=status,  # type: ignore[arg-type]
        score=max(0.0, min(100.0, float(score))),
        confidence=max(0.0, min(1.0, float(confidence))),
        severity=severity,  # type: ignore[arg-type]
        correctable=correctable,
        blocking=blocking,
        issues=list(issues or []),
        summary=summary,
        metrics=dict(metrics or {}),
    )


def fixture_score(context: dict[str, Any], validator_id: str, default: float = 92.0) -> float:
    scores = context.get("fixtureScores") or {}
    if validator_id in scores:
        return float(scores[validator_id])
    return float(context.get("fixtureDefaultScore", default))


def fixture_status(score: float, *, blocking_fail: bool = False) -> str:
    if blocking_fail:
        return "fail"
    if score >= 95:
        return "pass"
    if score >= 80:
        return "warn"
    return "fail"
