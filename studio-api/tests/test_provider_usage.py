"""Provider usage ledger, budgets, resolver budgetPreference."""

from __future__ import annotations

import pytest

from app.provider_usage import budgets, ledger
from app.hosted_providers import resolver
from app.hosted_providers.preferences import save_preferences


@pytest.fixture()
def usage_tmp(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(ledger.settings, "data_dir", data)
    monkeypatch.setattr(budgets.settings, "data_dir", data)
    return data


def test_record_estimated_vs_confirmed(usage_tmp):
    rec = ledger.record_usage(
        provider_id="fal",
        capability="image",
        units=1,
        project_id="proj-1",
        workspace_origin="Image Gen",
        status="estimated",
    )
    assert rec["estimatedCost"] is not None
    assert rec["confirmedCost"] is None
    assert "exact" not in (rec.get("disclaimer") or "").lower() or "not" in (rec.get("disclaimer") or "").lower()
    summary = ledger.summarize_spend(project_id="proj-1")
    assert summary["estimatedPending"] > 0
    assert summary["confirmedSpend"] == 0


def test_failure_does_not_assume_zero(usage_tmp):
    rec = ledger.record_usage(
        provider_id="kie",
        capability="video",
        units=2,
        status="failed",
        billing_status="unknown",
        failure_stage="after_accept",
    )
    assert rec["billingStatus"] == "unknown"
    assert rec["failureStage"] == "after_accept"


def test_budget_require_confirmation(usage_tmp):
    budgets.save_budgets(
        {
            "perRequestWarnUsd": 0.01,
            "doNotPromptBelowUsd": 0.0,
            "onExceed": "require_confirmation",
            "askBeforeSpending": True,
        }
    )
    gate = budgets.check_budget(estimated_cost=1.0, provider_id="fal", approved=False)
    assert gate["ok"] is False
    assert gate["action"] == "require_confirmation"
    assert gate["silentPaidFallbackForbidden"] is True
    allowed = budgets.check_budget(estimated_cost=1.0, provider_id="fal", approved=True)
    assert allowed["ok"] is True


def test_resolver_uses_budget_preference(monkeypatch):
    save_preferences(preferred_provider="automatic", budget_preference="low_cost")
    # All providers missing credentials → still returns budgetPreference in payload
    result = resolver.resolve_hosted_provider(
        capability=None,
        credential_states={"kie": "missing", "wavespeed": "missing", "fal": "missing"},
        prefer_configured=True,
    )
    assert result["budgetPreference"] == "low_cost"
    assert result["silentSwitchForbidden"] is True
