"""Weighted scoring and threshold bands for validation reports."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Iterable

from .config import DEFAULT_VISION_CONFIG, VisionConfig
from .schemas import ScoreBand, ValidationReport, ValidatorFinding


def band_for_score(score: float, config: VisionConfig | None = None) -> ScoreBand:
    cfg = config or DEFAULT_VISION_CONFIG
    t = cfg.thresholds
    if score >= t.approve:
        return "approve"
    if score >= t.review:
        return "review"
    if score >= t.corrections_required:
        return "corrections_required"
    return "reject"


def compute_report(
    *,
    session_id: str,
    project_id: str,
    findings: Iterable[ValidatorFinding],
    provider: str,
    include_motion: bool = False,
    config: VisionConfig | None = None,
) -> ValidationReport:
    cfg = config or DEFAULT_VISION_CONFIG
    weights = cfg.weights.as_dict(include_motion=include_motion)
    finding_list = [f for f in findings if f.status != "skipped"]

    weighted_sum = 0.0
    weight_total = 0.0
    strengths: list[str] = []
    warnings: list[str] = []
    failures: list[str] = []
    recommendations: list[str] = []
    blocking: list[str] = []
    confidences: list[float] = []

    for f in finding_list:
        w = float(weights.get(f.validatorId, 0.0))
        if f.status == "inconclusive":
            # Inconclusive does not count as a pass and does not inflate the average.
            warnings.append(f"{f.validatorId}: inconclusive — {f.summary}")
            confidences.append(f.confidence)
            continue
        if w > 0:
            weighted_sum += f.score * w
            weight_total += w
        confidences.append(f.confidence)

        if f.status == "pass" and f.score >= 95:
            strengths.append(f"{f.validatorId}: {f.summary or 'pass'}")
        elif f.status == "warn":
            warnings.append(f"{f.validatorId}: {f.summary or 'warning'}")
            for issue in f.issues:
                if issue.correctable:
                    recommendations.append(f"Correct {f.validatorId}: {issue.message}")
        elif f.status == "fail":
            failures.append(f"{f.validatorId}: {f.summary or 'fail'}")
            for issue in f.issues:
                recommendations.append(f"Fix {f.validatorId}: {issue.message}")

        if f.blocking or (f.validatorId in cfg.blocking_validators and f.status == "fail"):
            blocking.append(f.validatorId)

    overall = (weighted_sum / weight_total) if weight_total else 0.0
    # Blocking technical/identity fails cannot be averaged away.
    if blocking:
        overall = min(overall, cfg.thresholds.corrections_required - 0.01)

    band = band_for_score(overall, cfg)
    if blocking:
        band = "reject" if overall < cfg.thresholds.corrections_required else "corrections_required"
        if any(b in cfg.blocking_validators for b in blocking):
            band = "reject"

    passed = band == "approve" and not blocking and not failures
    confidence = sum(confidences) / len(confidences) if confidences else 0.0

    return ValidationReport(
        reportId=str(uuid.uuid4()),
        sessionId=session_id,
        projectId=project_id,
        overallScore=round(overall, 2),
        passed=passed,
        band=band,
        strengths=strengths,
        warnings=warnings,
        failures=failures,
        recommendations=recommendations[:20],
        confidence=round(confidence, 3),
        weights=weights,
        findings=list(findings),
        blockingFailures=sorted(set(blocking)),
        provider=provider,
        createdAt=datetime.utcnow().isoformat() + "Z",
    )
