from __future__ import annotations

from collections import defaultdict

from .types import (
    HealthCategoryTally,
    HealthCheckResult,
    HealthExplainability,
    HealthRunSummary,
    HealthStatus,
    StatusIndicator,
    StatusMode,
)

_STATUS_SCORES: dict[HealthStatus, int] = {
    "healthy": 100,
    "ready": 100,
    "connected": 98,
    "busy": 90,
    "starting": 82,
    "slow": 78,
    "degraded": 72,
    "warning": 64,
    "blocked": 20,
    "failed": 12,
    "offline": 0,
    "timed_out": 55,
    "not_installed": 28,
    "disabled": 35,
    "not_configured": 38,
    "not_tested": 52,
    "experimental": 58,
    "unknown": 45,
    "not_applicable": 100,
}

_CRITICALITY_WEIGHTS = {
    "critical": 1.0,
    "high": 0.8,
    "standard": 0.55,
    "optional": 0.2,
}

_BLOCKING = {"blocked", "failed", "offline", "not_installed", "disabled", "not_configured"}
# Active inference reports as busy — never treat as a warning/Degraded cause.
_WARNING = {"degraded", "warning", "not_tested", "experimental", "unknown", "timed_out", "slow", "starting"}


def score_for_status(status: HealthStatus) -> int:
    return _STATUS_SCORES.get(status, 45)


def band_for_score(score: int) -> str:
    if score >= 95:
        return "Excellent"
    if score >= 85:
        return "Strong"
    if score >= 70:
        return "Fair"
    if score >= 40:
        return "Needs Attention"
    if score > 0:
        return "Blocked"
    return "Offline"


def _category_label(category: str) -> str:
    return category.replace("_", " ").title()


def summarize_results(results: list[HealthCheckResult], mode: StatusMode) -> tuple[HealthRunSummary, list[HealthCategoryTally], HealthExplainability]:
    if not results:
        summary = HealthRunSummary(
            statusIndicator="Not Checked",
            score=0,
            band="Offline",
            mode=mode,
            totalChecks=0,
            healthyChecks=0,
            warningChecks=0,
            blockedChecks=0,
            checkedAt="",
            scoreExplanation="No status checks have run yet.",
        )
        return summary, [], HealthExplainability(band="Offline")

    weighted_total = 0.0
    weight_sum = 0.0
    blocked_checks = 0
    warning_checks = 0
    healthy_checks = 0
    dominant_checks: list[str] = []
    blocker_lines: list[str] = []
    warning_lines: list[str] = []
    category_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "healthy": 0, "warnings": 0, "blocked": 0})

    critical_blockers = []
    high_blockers = []

    for result in results:
        weight = _CRITICALITY_WEIGHTS[result.criticality]
        score = score_for_status(result.status)
        weighted_total += score * weight
        weight_sum += weight
        category_counts[result.category]["total"] += 1

        # Active chat inference reports as busy — never treat as a Degraded score cause.
        if result.status == "busy":
            healthy_checks += 1
            category_counts[result.category]["healthy"] += 1
            continue
        if result.status in _BLOCKING:
            blocked_checks += 1
            category_counts[result.category]["blocked"] += 1
            line = f"{result.title}: {result.summary}"
            blocker_lines.append(line)
            dominant_checks.append(result.checkId)
            if result.criticality == "critical":
                critical_blockers.append(result.checkId)
            elif result.criticality == "high":
                high_blockers.append(result.checkId)
        elif result.status in _WARNING:
            warning_checks += 1
            category_counts[result.category]["warnings"] += 1
            line = f"{result.title}: {result.summary}"
            warning_lines.append(line)
            if result.criticality in {"critical", "high"}:
                dominant_checks.append(result.checkId)
        else:
            healthy_checks += 1
            category_counts[result.category]["healthy"] += 1

    score = int(round(weighted_total / weight_sum)) if weight_sum else 0
    if critical_blockers:
        indicator: StatusIndicator = "Blocked"
        score = min(score, 35)
    elif high_blockers or warning_checks:
        indicator = "Degraded"
        score = min(score, 84)
    else:
        indicator = "Operational"

    band = band_for_score(score)
    checked_at = max(result.checkedAt for result in results)
    score_explanation = (
        f"{healthy_checks} checks healthy, {warning_checks} warning, {blocked_checks} blocked."
        if results
        else "No status checks have run yet."
    )
    summary = HealthRunSummary(
        statusIndicator=indicator,
        score=score,
        band=band,
        mode=mode,
        totalChecks=len(results),
        healthyChecks=healthy_checks,
        warningChecks=warning_checks,
        blockedChecks=blocked_checks,
        checkedAt=checked_at,
        scoreExplanation=score_explanation,
    )
    categories = [
        HealthCategoryTally(
            category=category,  # type: ignore[arg-type]
            label=_category_label(category),
            total=counts["total"],
            healthy=counts["healthy"],
            warnings=counts["warnings"],
            blocked=counts["blocked"],
        )
        for category, counts in sorted(category_counts.items())
    ]
    explainability = HealthExplainability(
        band=band,
        dominantChecks=sorted(set(dominant_checks)),
        blockers=blocker_lines[:8],
        warnings=warning_lines[:8],
        reasons=[
            "Critical and high-severity checks dominate the overall score.",
            "Optional checks can lower confidence, but they do not block the studio on their own.",
            "Project binding, provider/runtime readiness, tool execution, proposals, and persistence are treated as blocking when they fail.",
        ],
    )
    return summary, categories, explainability
