"""Budget preferences and enforcement gates (notify / confirm / block)."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Literal

from ..config import settings
from .ledger import summarize_spend

_LOCK = threading.RLock()

BudgetAction = Literal["notify", "require_confirmation", "block"]


def budgets_path() -> Path:
    return settings.data_dir / "provider_usage_budgets.json"


def _defaults() -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "budgetPreference": "balanced",  # low_cost | balanced | quality
        "perRequestWarnUsd": 0.50,
        "doNotPromptBelowUsd": 0.05,
        "projectBudgetUsd": None,
        "dailyBudgetUsd": None,
        "monthlyBudgetUsd": None,
        "providerBudgets": {},
        "categoryBudgets": {},
        "onExceed": "require_confirmation",  # notify | require_confirmation | block
        "askBeforeSpending": True,
        "silentPaidFallbackForbidden": True,
    }


def load_budgets() -> dict[str, Any]:
    with _LOCK:
        path = budgets_path()
        if not path.exists():
            # Seed from hosted_providers preferences when present
            base = _defaults()
            try:
                from ..hosted_providers.preferences import load_preferences

                pref = load_preferences()
                if pref.get("budgetPreference"):
                    base["budgetPreference"] = pref["budgetPreference"]
            except Exception:
                pass
            return base
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            out = _defaults()
            if isinstance(raw, dict):
                out.update({k: v for k, v in raw.items() if k in out or k.endswith("Usd") or k in ("providerBudgets", "categoryBudgets")})
            return out
        except (OSError, ValueError, TypeError):
            return _defaults()


def save_budgets(patch: dict[str, Any]) -> dict[str, Any]:
    with _LOCK:
        current = load_budgets()
        for k, v in (patch or {}).items():
            if k in current or k.endswith("Usd") or k in ("providerBudgets", "categoryBudgets", "onExceed", "budgetPreference"):
                current[k] = v
        path = budgets_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        try:
            with tmp.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(current, handle, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, path)
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
        # Mirror budgetPreference into hosted preferences for resolver
        try:
            from ..hosted_providers.preferences import save_preferences

            save_preferences(budget_preference=str(current.get("budgetPreference") or "balanced"))
        except Exception:
            pass
        return current


def check_budget(
    *,
    estimated_cost: float | None,
    project_id: str | None = None,
    provider_id: str | None = None,
    capability: str | None = None,
    approved: bool = False,
) -> dict[str, Any]:
    """Preflight budget gate. Never cancels in-flight jobs — only blocks new submits."""
    budgets = load_budgets()
    warnings: list[str] = []
    action: str = "allow"
    cost = float(estimated_cost) if isinstance(estimated_cost, (int, float)) else None
    floor = float(budgets.get("doNotPromptBelowUsd") or 0)
    warn_at = float(budgets.get("perRequestWarnUsd") or 0.5)
    on_exceed = str(budgets.get("onExceed") or "require_confirmation")

    if cost is None:
        return {
            "ok": True,
            "action": "allow_with_disclaimer",
            "warnings": ["Pricing unknown — check provider billing before proceeding."],
            "requiresConfirmation": bool(budgets.get("askBeforeSpending")),
            "budgets": budgets,
            "silentPaidFallbackForbidden": True,
            "mock": False,
        }

    if cost < floor:
        return {
            "ok": True,
            "action": "allow",
            "warnings": [],
            "requiresConfirmation": False,
            "estimatedCost": cost,
            "budgets": budgets,
            "silentPaidFallbackForbidden": True,
            "mock": False,
        }

    if cost >= warn_at:
        warnings.append(f"This request may cost about ${cost:.4f} (estimate, not exact).")
        action = on_exceed if on_exceed in ("notify", "require_confirmation", "block") else "require_confirmation"

    summary = summarize_spend(project_id=project_id, provider_id=provider_id)
    projected = float(summary.get("totalProjected") or 0) + cost
    project_cap = budgets.get("projectBudgetUsd")
    if isinstance(project_cap, (int, float)) and projected > float(project_cap):
        warnings.append(f"Project budget ${project_cap} would be exceeded (projected ${projected:.4f}).")
        action = on_exceed

    if provider_id:
        p_cap = (budgets.get("providerBudgets") or {}).get(provider_id)
        if isinstance(p_cap, (int, float)):
            p_sum = summarize_spend(project_id=project_id, provider_id=provider_id)
            if float(p_sum.get("totalProjected") or 0) + cost > float(p_cap):
                warnings.append(f"Provider budget for {provider_id} would be exceeded.")
                action = on_exceed

    if capability:
        c_cap = (budgets.get("categoryBudgets") or {}).get(capability)
        if isinstance(c_cap, (int, float)):
            c_sum = summarize_spend(project_id=project_id)
            cat = (c_sum.get("byCapability") or {}).get(capability) or {}
            cat_total = float(cat.get("confirmed") or 0) + float(cat.get("estimated") or 0) + cost
            if cat_total > float(c_cap):
                warnings.append(f"Category budget for {capability} would be exceeded.")
                action = on_exceed

    if action == "block" and not approved:
        return {
            "ok": False,
            "action": "block",
            "warnings": warnings,
            "requiresConfirmation": False,
            "estimatedCost": cost,
            "message": "Blocked by budget settings. Raise the budget or approve a one-time override.",
            "budgets": budgets,
            "silentPaidFallbackForbidden": True,
            "mock": False,
        }
    if action == "require_confirmation" and not approved:
        return {
            "ok": False,
            "action": "require_confirmation",
            "warnings": warnings,
            "requiresConfirmation": True,
            "estimatedCost": cost,
            "message": "Confirm before spending — Adept will not silently charge a paid API.",
            "budgets": budgets,
            "silentPaidFallbackForbidden": True,
            "mock": False,
        }
    return {
        "ok": True,
        "action": "allow" if action == "notify" or approved else action,
        "warnings": warnings,
        "requiresConfirmation": False,
        "estimatedCost": cost,
        "budgets": budgets,
        "silentPaidFallbackForbidden": True,
        "mock": False,
    }
