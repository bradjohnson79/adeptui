"""Prompt Intelligence V2 FastAPI routes (sibling to V1, non-breaking)."""

from __future__ import annotations

from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .benchmark_certify import certification_status, promote_strategy, rollback_strategy
from .benchmark_eval import evaluate_category
from .benchmark_models import HumanReviewScores, RetentionMode
from .benchmark_runner import (
    cancel_suite,
    pause_suite,
    plan_suite,
    resume_suite,
    start_suite_run,
    suite_status,
)
from .benchmark_store import list_evidence, list_reviews, list_runs, list_suite_runs, load_review, load_run, save_review, save_run
from .benchmark_suites import list_suites, resolve_live_video_provider
from .errors import PromptIntelligenceError
from .feedback import list_queued_feedback, submit_feedback
from .recommendation import resolve_strategy_recommendation
from .scoring_v2 import analyze_v2

router = APIRouter(prefix="/prompt-intelligence/v2", tags=["prompt-intelligence-v2"])


class PlanBody(BaseModel):
    suiteId: str
    providerId: str
    modelRevision: str = "default"
    samplesPerStrategy: Optional[int] = None


class RunBody(BaseModel):
    suiteId: str
    providerId: str
    modelRevision: str = "default"
    samplesPerStrategy: int = 1
    dryRun: bool = True
    retentionMode: RetentionMode = "keep_all"


class ReviewSubmitBody(BaseModel):
    comparisonId: str
    reviews: dict[str, dict[str, Any]] = Field(default_factory=dict)
    reveal: bool = True


class EvaluateBody(BaseModel):
    providerId: str
    modelRevision: str = "default"
    domain: str
    category: str
    suiteRunId: Optional[str] = None
    workflowRevision: str = "default"


class PromoteBody(BaseModel):
    providerId: str
    modelRevision: str = "default"
    domain: str
    category: str
    strategy: str
    force: bool = False


class RollbackBody(BaseModel):
    providerId: str
    modelRevision: str = "default"
    domain: str
    category: str


class RecommendBody(BaseModel):
    domain: str = "video"
    category: str = "general"
    providerId: Optional[str] = None
    modelRevision: str = "default"
    strategyMode: Literal["manual", "recommend", "automatic_certified"] = "recommend"
    manualOverride: Optional[str] = None
    minConfidence: str = "medium"
    projectPrefs: Optional[dict[str, Any]] = None


class AnalyzeV2Body(BaseModel):
    creatorPrompt: str = ""
    domain: Literal["image", "video", "audio", "voice", "music", "sfx"] = "video"
    providerId: Optional[str] = None
    modelRevision: str = "default"
    category: str = "general"
    strategyMode: str = "recommend"
    projectPrefs: Optional[dict[str, Any]] = None


class FeedbackBody(BaseModel):
    domain: str
    category: str = ""
    providerId: str = ""
    modelRevision: str = ""
    strategyApplied: Optional[str] = None
    rating: Optional[int] = None
    notes: str = ""
    projectId: Optional[str] = None
    optIn: bool = True


def _http_pi_error(exc: PromptIntelligenceError) -> HTTPException:
    return HTTPException(status_code=400, detail=exc.to_dict())


@router.get("/suites")
def get_suites() -> dict[str, Any]:
    return {"ok": True, "suites": [s.model_dump(mode="json") for s in list_suites()]}


@router.post("/plan")
def post_plan(body: PlanBody) -> dict[str, Any]:
    try:
        plan = plan_suite(
            body.suiteId,
            provider_id=body.providerId,
            model_revision=body.modelRevision,
            samples_per_strategy=body.samplesPerStrategy,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"code": "SUITE_NOT_FOUND", "message": str(exc)}) from exc
    return {"ok": True, "plan": plan.model_dump(mode="json")}


@router.post("/runs")
def post_run(body: RunBody) -> dict[str, Any]:
    try:
        suite_run = start_suite_run(
            body.suiteId,
            provider_id=body.providerId,
            model_revision=body.modelRevision,
            samples_per_strategy=body.samplesPerStrategy,
            dry_run=body.dryRun,
            retention_mode=body.retentionMode,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail={"code": "SUITE_RUN_FAILED", "message": str(exc)}) from exc
    return {"ok": True, "suiteRun": suite_run.model_dump(mode="json")}


@router.get("/runs")
def get_runs(suiteRunId: Optional[str] = None) -> dict[str, Any]:
    if suiteRunId:
        return suite_status(suiteRunId)
    return {
        "ok": True,
        "suiteRuns": [s.model_dump(mode="json") for s in list_suite_runs()],
        "runs": [r.model_dump(mode="json") for r in list_runs()[:200]],
    }


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    run = load_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail={"code": "RUN_NOT_FOUND"})
    return {"ok": True, "run": run.model_dump(mode="json")}


@router.post("/runs/{suite_run_id}/pause")
def post_pause(suite_run_id: str) -> dict[str, Any]:
    try:
        return {"ok": True, "suiteRun": pause_suite(suite_run_id).model_dump(mode="json")}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"code": "SUITE_RUN_NOT_FOUND"}) from exc


@router.post("/runs/{suite_run_id}/resume")
def post_resume(suite_run_id: str) -> dict[str, Any]:
    try:
        return {"ok": True, "suiteRun": resume_suite(suite_run_id).model_dump(mode="json")}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"code": "SUITE_RUN_NOT_FOUND"}) from exc


@router.post("/runs/{suite_run_id}/cancel")
def post_cancel(suite_run_id: str) -> dict[str, Any]:
    try:
        return {"ok": True, "suiteRun": cancel_suite(suite_run_id).model_dump(mode="json")}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"code": "SUITE_RUN_NOT_FOUND"}) from exc


@router.get("/reviews")
def get_reviews() -> dict[str, Any]:
    reviews = []
    for r in list_reviews():
        payload = r.model_dump(mode="json")
        if not r.submitted:
            payload["strategyMap"] = {}  # blind
        reviews.append(payload)
    return {"ok": True, "reviews": reviews}


@router.get("/reviews/{comparison_id}")
def get_review(comparison_id: str) -> dict[str, Any]:
    review = load_review(comparison_id)
    if not review:
        raise HTTPException(status_code=404, detail={"code": "REVIEW_NOT_FOUND"})
    payload = review.model_dump(mode="json")
    if not review.submitted:
        payload["strategyMap"] = {}
    return {"ok": True, "review": payload}


@router.post("/reviews/submit")
def post_review_submit(body: ReviewSubmitBody) -> dict[str, Any]:
    review = load_review(body.comparisonId)
    if not review:
        raise HTTPException(status_code=404, detail={"code": "REVIEW_NOT_FOUND"})
    for slot_id, raw in body.reviews.items():
        scores = HumanReviewScores.model_validate(raw)
        review.reviews[slot_id] = scores
        # Attach to run
        item = next((i for i in review.items if i.slotId == slot_id), None)
        if item:
            run = load_run(item.runId)
            if run:
                run.humanScores = scores
                save_run(run)
    review.submitted = True
    if body.reveal:
        review.revealed = True
    save_review(review)
    return {"ok": True, "review": review.model_dump(mode="json")}


@router.post("/evaluate")
def post_evaluate(body: EvaluateBody) -> dict[str, Any]:
    evidence = evaluate_category(
        provider_id=body.providerId,
        model_revision=body.modelRevision,
        domain=body.domain,
        category=body.category,
        suite_run_id=body.suiteRunId,
        workflow_revision=body.workflowRevision,
    )
    return {"ok": True, "evidence": evidence.model_dump(mode="json")}


@router.post("/promote")
def post_promote(body: PromoteBody) -> dict[str, Any]:
    try:
        return promote_strategy(
            provider_id=body.providerId,
            model_revision=body.modelRevision,
            domain=body.domain,
            category=body.category,
            strategy=body.strategy,
            force=body.force,
        )
    except PromptIntelligenceError as exc:
        raise _http_pi_error(exc) from exc


@router.post("/rollback")
def post_rollback(body: RollbackBody) -> dict[str, Any]:
    try:
        return rollback_strategy(
            provider_id=body.providerId,
            model_revision=body.modelRevision,
            domain=body.domain,
            category=body.category,
        )
    except PromptIntelligenceError as exc:
        raise _http_pi_error(exc) from exc


@router.get("/certification")
def get_certification(
    providerId: str,
    domain: str,
    category: str,
    modelRevision: str = "default",
) -> dict[str, Any]:
    return certification_status(
        provider_id=providerId,
        model_revision=modelRevision,
        domain=domain,
        category=category,
    )


@router.get("/evidence")
def get_evidence() -> dict[str, Any]:
    return {"ok": True, "evidence": [e.model_dump(mode="json") for e in list_evidence()]}


@router.post("/recommend")
def post_recommend(body: RecommendBody) -> dict[str, Any]:
    rec = resolve_strategy_recommendation(
        domain=body.domain,
        category=body.category,
        provider_id=body.providerId,
        model_revision=body.modelRevision,
        strategy_mode=body.strategyMode,
        manual_override=body.manualOverride,
        min_confidence=body.minConfidence,
        project_prefs=body.projectPrefs,
    )
    return {"ok": True, "strategyRecommendation": rec.model_dump(mode="json")}


@router.post("/analyze")
def post_analyze_v2(body: AnalyzeV2Body) -> dict[str, Any]:
    return analyze_v2(
        body.creatorPrompt,
        domain=body.domain,
        provider_id=body.providerId,
        model_revision=body.modelRevision,
        category=body.category,
        strategy_mode=body.strategyMode,
        project_prefs=body.projectPrefs,
    )


@router.post("/feedback")
def post_feedback(body: FeedbackBody) -> dict[str, Any]:
    return submit_feedback(
        domain=body.domain,
        category=body.category,
        provider_id=body.providerId,
        model_revision=body.modelRevision,
        strategy_applied=body.strategyApplied,
        rating=body.rating,
        notes=body.notes,
        project_id=body.projectId,
        opt_in=body.optIn,
    )


@router.get("/feedback")
def get_feedback() -> dict[str, Any]:
    return list_queued_feedback()


@router.get("/providers/live")
def get_live_providers() -> dict[str, Any]:
    return {"ok": True, "video": resolve_live_video_provider()}
