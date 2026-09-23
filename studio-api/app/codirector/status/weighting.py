from __future__ import annotations

from collections import defaultdict
from ...readiness.v11_policy import (
    POLICY_VERSION,
    SCORE_SEMANTICS,
    ReadinessClass,
    classify_status_check,
    infer_from_criticality,
    worst_class,
)
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

_PRODUCTION_CLASSES = {
    ReadinessClass.PLATFORM_CRITICAL,
    ReadinessClass.PRODUCTION_CRITICAL,
}


def score_for_status(status: HealthStatus) -> int:
    return _STATUS_SCORES.get(status, 45)


def resolve_readiness_class(result: HealthCheckResult) -> ReadinessClass:
    raw = getattr(result, "readinessClass", None)
    if raw:
        try:
            return ReadinessClass(str(raw))
        except ValueError:
            pass
    assignment = classify_status_check(result.checkId)
    if assignment is not None:
        return assignment.readiness_class
    return infer_from_criticality(result.criticality)


def band_for_score(score: int, indicator: StatusIndicator = "Operational") -> str:
    """Owner band labels. Numeric 35 / 84 / 95 caps stay in ``summarize_results``."""
    if indicator == "Blocked" or score <= 35:
        return "Blocked"
    if indicator == "Degraded":
        return "Workflow Degraded"
    if score >= 95:
        return "Operational"
    if score >= 85:
        return "Advisory"
    return "Fair"


def _category_label(category: str) -> str:
    return category.replace("_", " ").title()


def summarize_results(results: list[HealthCheckResult], mode: StatusMode) -> tuple[HealthRunSummary, list[HealthCategoryTally], HealthExplainability]:
    if not results:
        summary = HealthRunSummary(
            statusIndicator="Not Checked",
            score=0,
            band="Blocked",
            mode=mode,
            totalChecks=0,
            healthyChecks=0,
            warningChecks=0,
            blockedChecks=0,
            checkedAt="",
            scoreExplanation="No status checks have run yet.",
            scoreSemantics=SCORE_SEMANTICS,
            readinessPolicyVersion=POLICY_VERSION,
        )
        return summary, [], HealthExplainability(band="Blocked")

    weighted_total = 0.0
    weight_sum = 0.0
    blocked_checks = 0
    warning_checks = 0
    healthy_checks = 0
    dominant_checks: list[str] = []
    blocker_lines: list[str] = []
    warning_lines: list[str] = []
    category_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "healthy": 0, "warnings": 0, "blocked": 0})

    production_blockers: list[HealthCheckResult] = []
    workflow_issues: list[HealthCheckResult] = []
    advisory_issues: list[HealthCheckResult] = []
    other_warnings: list[HealthCheckResult] = []

    for result in results:
        weight = _CRITICALITY_WEIGHTS[result.criticality]
        score = score_for_status(result.status)
        weighted_total += score * weight
        weight_sum += weight
        category_counts[result.category]["total"] += 1
        readiness = resolve_readiness_class(result)

        # Active chat inference reports as busy — never treat as a Degraded score cause.
        # Completed-but-slow probes already succeeded; latency is not a production gap.
        if result.status in {"busy", "slow"}:
            healthy_checks += 1
            category_counts[result.category]["healthy"] += 1
            continue
        if result.status in _BLOCKING or result.status in _WARNING:
            line = f"{result.title}: {result.summary}"
            probe_noise = result.status in {"timed_out", "slow", "starting"}
            if readiness == ReadinessClass.OPTIONAL:
                # Optional leftovers (gated IC-LoRA, leftover startup names, dormant
                # probes, legacy menu-hidden surfaces) stay visible on the run, but
                # they never own the score: no warningChecks, no blockedChecks, no
                # advisory/workflow/production issue lists, and no score cap.
                continue
            if readiness in _PRODUCTION_CLASSES and result.status in _BLOCKING:
                blocked_checks += 1
                category_counts[result.category]["blocked"] += 1
                production_blockers.append(result)
                blocker_lines.append(line)
                dominant_checks.append(result.checkId)
            elif readiness == ReadinessClass.WORKFLOW_DEGRADED and result.status in _BLOCKING:
                warning_checks += 1
                category_counts[result.category]["warnings"] += 1
                workflow_issues.append(result)
                warning_lines.append(line)
                dominant_checks.append(result.checkId)
            elif readiness == ReadinessClass.ADVISORY_REVIEW_DEGRADED:
                warning_checks += 1
                category_counts[result.category]["warnings"] += 1
                advisory_issues.append(result)
                warning_lines.append(line)
            elif probe_noise:
                # Slow or timed-out production probes are not proof the studio is down.
                warning_checks += 1
                category_counts[result.category]["warnings"] += 1
                advisory_issues.append(result)
                warning_lines.append(line)
            elif readiness == ReadinessClass.WORKFLOW_DEGRADED:
                warning_checks += 1
                category_counts[result.category]["warnings"] += 1
                workflow_issues.append(result)
                warning_lines.append(line)
                dominant_checks.append(result.checkId)
            elif result.status in _BLOCKING:
                warning_checks += 1
                category_counts[result.category]["warnings"] += 1
                other_warnings.append(result)
                warning_lines.append(line)
            else:
                warning_checks += 1
                category_counts[result.category]["warnings"] += 1
                other_warnings.append(result)
                warning_lines.append(line)
        else:
            healthy_checks += 1
            category_counts[result.category]["healthy"] += 1

    score = int(round(weighted_total / weight_sum)) if weight_sum else 0
    if production_blockers:
        indicator: StatusIndicator = "Blocked"
        score = min(score, 35)
    elif workflow_issues:
        indicator = "Degraded"
        score = min(score, 84)
    elif other_warnings:
        indicator = "Degraded"
        score = min(score, 84)
    elif advisory_issues:
        indicator = "Operational"
        # Excellent is reserved for no open registry/review gaps.
        score = min(max(score, 85), 94)
    else:
        indicator = "Operational"

    band = band_for_score(score, indicator)
    checked_at = max(result.checkedAt for result in results)
    score_explanation = (
        f"{SCORE_SEMANTICS}: {healthy_checks} checks healthy, {warning_checks} warning, {blocked_checks} blocked."
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
        scoreSemantics=SCORE_SEMANTICS,
        readinessPolicyVersion=POLICY_VERSION,
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
    worst = worst_class(resolve_readiness_class(item) for item in production_blockers + workflow_issues + advisory_issues)
    explainability = HealthExplainability(
        band=band,
        dominantChecks=sorted(set(dominant_checks)),
        blockers=blocker_lines[:8],
        warnings=warning_lines[:8],
        reasons=[
            f"{SCORE_SEMANTICS} ({POLICY_VERSION}).",
            "Platform and production-critical failures block the studio.",
            "Workflow-degraded failures lower the score without pretending the platform is down.",
            "Advisory / review gaps (including Temporal Continuity) stay visible and prevent a perfect 100, but they do not cap the studio at Degraded.",
            "Optional leftovers do not own the score.",
        ]
        + ([f"Worst readiness class this run: {worst.value}."] if worst else []),
    )
    return summary, categories, explainability
