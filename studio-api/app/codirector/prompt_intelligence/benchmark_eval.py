"""Automated health checks and score aggregation for PI V2."""

from __future__ import annotations

from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Optional

from .benchmark_models import (
    AutomatedHealthScores,
    CategoryEvidence,
    CertificationStatusV2,
    ConfidenceLevel,
    HumanReviewScores,
    PromptBenchmarkRun,
)
from .benchmark_store import list_runs, load_evidence, save_evidence
from .models import utc_now_iso

CERTIFICATION_SAMPLE_THRESHOLD = 3


def health_check_image_file(path: Path) -> AutomatedHealthScores:
    exists = path.is_file()
    size = path.stat().st_size if exists else 0
    format_ok = exists and (path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"} or size > 8)
    notes: list[str] = []
    if exists and path.suffix.lower() == ".png" and size >= 8:
        head = path.read_bytes()[:8]
        if head.startswith(b"\x89PNG"):
            format_ok = True
        else:
            notes.append("png_header_soft")
            format_ok = size > 0
    passed = exists and size > 0 and format_ok
    return AutomatedHealthScores(
        completed=True,
        artifactExists=exists,
        artifactNonEmpty=size > 0,
        formatOk=format_ok,
        metadataComplete=True,
        passed=passed,
        notes=notes,
    )


def health_check_video_file(path: Path) -> AutomatedHealthScores:
    exists = path.is_file()
    size = path.stat().st_size if exists else 0
    format_ok = exists and size > 16
    black = size > 0 and size < 64  # tiny files suspect
    frozen = False
    notes: list[str] = []
    if black:
        notes.append("black_or_tiny_suspect")
    return AutomatedHealthScores(
        completed=exists,
        artifactExists=exists,
        artifactNonEmpty=size > 0,
        formatOk=format_ok,
        blackFrameSuspect=black,
        frozenFrameSuspect=frozen,
        metadataComplete=exists,
        passed=exists and size > 16 and not black,
        notes=notes,
    )


def health_check_audio_file(path: Path) -> AutomatedHealthScores:
    exists = path.is_file()
    size = path.stat().st_size if exists else 0
    silence = False
    clipping = False
    notes: list[str] = []
    if exists and path.suffix.lower() == ".wav" and size > 44:
        # Heuristic: all-zero PCM after header → silence
        data = path.read_bytes()[44:44 + 4000]
        if data and all(b == 0 for b in data):
            silence = True
            notes.append("silence_suspect")
    passed = exists and size > 44
    return AutomatedHealthScores(
        completed=exists,
        artifactExists=exists,
        artifactNonEmpty=size > 0,
        formatOk=exists and size > 44,
        silenceSuspect=silence,
        clippingSuspect=clipping,
        metadataComplete=exists,
        passed=passed,
        notes=notes,
    )


def confidence_from_samples(sample_count: int, score_spread: float) -> ConfidenceLevel:
    if sample_count < CERTIFICATION_SAMPLE_THRESHOLD:
        return "low"
    if sample_count >= 6 and score_spread < 8:
        return "high"
    if sample_count >= CERTIFICATION_SAMPLE_THRESHOLD and score_spread < 15:
        return "medium"
    return "low"


def aggregate_strategy_scores(
    runs: list[PromptBenchmarkRun],
    *,
    human_by_run: Optional[dict[str, HumanReviewScores]] = None,
) -> dict[str, dict[str, Any]]:
    by_strategy: dict[str, list[float]] = {}
    success_counts: dict[str, int] = {}
    for run in runs:
        if not run.success or not run.automatedScores.passed:
            continue
        success_counts[run.strategy] = success_counts.get(run.strategy, 0) + 1
        score = 50.0
        if human_by_run and run.runId in human_by_run:
            score = float(human_by_run[run.runId].overall)
        elif run.humanScores:
            score = float(run.humanScores.overall)
        by_strategy.setdefault(run.strategy, []).append(score)
    out: dict[str, dict[str, Any]] = {}
    for strategy, scores in by_strategy.items():
        spread = float(pstdev(scores)) if len(scores) > 1 else 0.0
        out[strategy] = {
            "mean": round(mean(scores), 2),
            "sampleCount": len(scores),
            "successCount": success_counts.get(strategy, 0),
            "spread": round(spread, 2),
            "confidence": confidence_from_samples(len(scores), spread),
        }
    return out


def evaluate_category(
    *,
    provider_id: str,
    model_revision: str,
    domain: str,
    category: str,
    suite_run_id: Optional[str] = None,
    workflow_revision: str = "default",
) -> CategoryEvidence:
    runs = list_runs(suite_run_id=suite_run_id) if suite_run_id else list_runs()
    runs = [
        r
        for r in runs
        if r.providerId == provider_id
        and r.modelRevision == model_revision
        and r.domain == domain
        and r.category == category
        and r.success
    ]
    agg = aggregate_strategy_scores(runs)
    scores = {k: float(v["mean"]) for k, v in agg.items()}
    sample_count = sum(int(v["sampleCount"]) for v in agg.values())
    min_samples = min((int(v["sampleCount"]) for v in agg.values()), default=0)

    status: CertificationStatusV2 = "not_tested"
    recommended: Optional[str] = None
    reason_parts: list[str] = []

    if not agg:
        status = "not_tested"
    elif min_samples < CERTIFICATION_SAMPLE_THRESHOLD:
        status = "insufficient_evidence"
        reason_parts.append(f"need>={CERTIFICATION_SAMPLE_THRESHOLD} samples/strategy; have {min_samples}")
    else:
        # Rank strategies
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_strategy, top_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else top_score
        en_score = scores.get("refined-english", scores.get("creator", 0.0))
        bilingual = [s for s in scores if s.startswith("bilingual-")]
        if abs(top_score - second_score) < 3:
            status = "no_material_difference"
            recommended = "refined-english"
        elif top_strategy.startswith("bilingual-") and top_score >= en_score + 3:
            status = "experimental"  # human must still promote
            recommended = top_strategy
        elif en_score >= top_score:
            status = "english_preferred"
            recommended = "refined-english"
            if bilingual and max(scores[b] for b in bilingual) + 3 < en_score:
                status = "bilingual_not_recommended"
        else:
            status = "experimental"
            recommended = top_strategy

    conf: ConfidenceLevel = "low"
    if agg:
        spreads = [float(v["spread"]) for v in agg.values()]
        conf = confidence_from_samples(min_samples, mean(spreads) if spreads else 0.0)

    existing = load_evidence(provider_id, model_revision, domain, category)
    evidence = CategoryEvidence(
        providerId=provider_id,
        modelRevision=model_revision,
        domain=domain,
        category=category,
        workflowRevision=workflow_revision,
        status=status,
        recommendedStrategy=recommended,  # type: ignore[arg-type]
        confidence=conf,
        sampleCount=sample_count,
        scoresByStrategy=scores,
        runIds=[r.runId for r in runs],
        evidenceVersion=str(int(existing.evidenceVersion) + 1) if existing and existing.evidenceVersion.isdigit() else "1",
        stale=False,
        updatedAt=utc_now_iso(),
        auditLog=(existing.auditLog if existing else [])
        + [
            {
                "at": utc_now_iso(),
                "action": "evaluate",
                "status": status,
                "recommendedStrategy": recommended,
                "reason": "; ".join(reason_parts) or status,
            }
        ],
    )
    return save_evidence(evidence)


def mark_stale_if_revision_changed(
    evidence: CategoryEvidence,
    *,
    model_revision: str,
    workflow_revision: str,
) -> CategoryEvidence:
    if evidence.modelRevision != model_revision or evidence.workflowRevision != workflow_revision:
        evidence.stale = True
        evidence.staleReason = "modelRevision or workflowRevision changed"
        evidence.status = "not_tested"
        evidence.auditLog.append(
            {
                "at": utc_now_iso(),
                "action": "stale",
                "reason": evidence.staleReason,
                "fromModel": evidence.modelRevision,
                "toModel": model_revision,
            }
        )
        evidence.modelRevision = model_revision
        evidence.workflowRevision = workflow_revision
        return save_evidence(evidence)
    return evidence
