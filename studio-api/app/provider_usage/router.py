"""HTTP API for dock spend, usage ledger, budgets, preflight."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import budgets, ledger
from .rate_cards import estimate_cost, get_rate_card

router = APIRouter(prefix="/provider-usage", tags=["provider-usage"])


class RecordBody(BaseModel):
    providerId: str
    modelId: Optional[str] = None
    capability: str = "image"
    projectId: Optional[str] = None
    jobId: Optional[str] = None
    tool: Optional[str] = None
    userAction: Optional[str] = None
    workspaceOrigin: Optional[str] = None
    units: float = 1.0
    estimatedCost: Optional[float] = None
    confirmedCost: Optional[float] = None
    currency: str = "USD"
    pricingSource: Optional[str] = None
    status: str = "estimated"
    billingStatus: str = "pending"
    failureStage: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class PreflightBody(BaseModel):
    providerId: str
    capability: str = "image"
    units: float = 1.0
    projectId: Optional[str] = None
    estimatedCost: Optional[float] = None
    approved: bool = False


class BudgetsBody(BaseModel):
    budgetPreference: Optional[str] = None
    perRequestWarnUsd: Optional[float] = None
    doNotPromptBelowUsd: Optional[float] = None
    projectBudgetUsd: Optional[float] = None
    dailyBudgetUsd: Optional[float] = None
    monthlyBudgetUsd: Optional[float] = None
    providerBudgets: Optional[dict[str, float]] = None
    categoryBudgets: Optional[dict[str, float]] = None
    onExceed: Optional[str] = None
    askBeforeSpending: Optional[bool] = None


@router.get("/summary")
def summary(projectId: Optional[str] = None, providerId: Optional[str] = None):
    return {"ok": True, **ledger.summarize_spend(project_id=projectId, provider_id=providerId)}


@router.get("/records")
def records(projectId: Optional[str] = None, providerId: Optional[str] = None, limit: int = 100):
    return {
        "ok": True,
        "records": ledger.list_usage(project_id=projectId, provider_id=providerId, limit=limit),
        "mock": False,
    }


@router.post("/records")
def post_record(body: RecordBody):
    rec = ledger.record_usage(
        provider_id=body.providerId,
        model_id=body.modelId,
        capability=body.capability,
        project_id=body.projectId,
        job_id=body.jobId,
        tool=body.tool,
        user_action=body.userAction,
        workspace_origin=body.workspaceOrigin,
        units=body.units,
        estimated_cost=body.estimatedCost,
        confirmed_cost=body.confirmedCost,
        currency=body.currency,
        pricing_source=body.pricingSource,
        status=body.status,
        billing_status=body.billingStatus,
        failure_stage=body.failureStage,
        metadata=body.metadata,
    )
    return {"ok": True, "record": rec, "mock": False}


@router.get("/budgets")
def get_budgets():
    return {"ok": True, "budgets": budgets.load_budgets(), "mock": False}


@router.put("/budgets")
def put_budgets(body: BudgetsBody):
    patch = body.model_dump(exclude_none=True)
    return {"ok": True, "budgets": budgets.save_budgets(patch), "mock": False}


@router.post("/preflight")
def preflight(body: PreflightBody):
    est = body.estimatedCost
    if est is None:
        est = estimate_cost(body.providerId, capability=body.capability, units=body.units).get("estimatedCost")
    result = budgets.check_budget(
        estimated_cost=est,
        project_id=body.projectId,
        provider_id=body.providerId,
        capability=body.capability,
        approved=body.approved,
    )
    return {"ok": result.get("ok"), **result, "estimate": estimate_cost(body.providerId, capability=body.capability, units=body.units)}


@router.get("/rate-cards/{provider_id}")
def rate_card(provider_id: str):
    return {"ok": True, "rateCard": get_rate_card(provider_id), "mock": False}


@router.get("/dock")
def dock_spend(projectId: Optional[str] = None):
    """Compact dock payload: today / project spend + budget warnings."""
    summary_data = ledger.summarize_spend(project_id=projectId)
    b = budgets.load_budgets()
    return {
        "ok": True,
        "localLabel": "Local — No API charge",
        "projectSpend": summary_data,
        "budgets": b,
        "askBeforeSpending": bool(b.get("askBeforeSpending")),
        "silentPaidFallbackForbidden": True,
        "mock": False,
    }


@router.get("/codirector-summary")
def codirector_summary(projectId: Optional[str] = None):
    """Cost awareness for Co-Director — never includes secrets."""
    summary_data = ledger.summarize_spend(project_id=projectId)
    b = budgets.load_budgets()
    return {
        "ok": True,
        "spend": summary_data,
        "budgetPreference": b.get("budgetPreference"),
        "askBeforeSpending": bool(b.get("askBeforeSpending")),
        "guidance": (
            "You may recommend local, cheaper, or ask the creator for approval. "
            "Never silently substitute a paid model. Never request or echo API keys."
        ),
        "secretsIncluded": False,
        "mock": False,
    }
