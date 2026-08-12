"""Certified Provider Resolver — Automatic Recommendation never silently switches mid-job."""

from __future__ import annotations

from typing import Any

from .capabilities import provider_supports
from .models import providers_for_model, resolve_model_mapping
from .preferences import is_automatic, load_preferences, pinned_provider
from .registry import PRIORITY_ORDER, PROVIDERS, get_provider


def resolve_hosted_provider(
    *,
    capability: str | None = None,
    canonical_model: str | None = None,
    credential_states: dict[str, str] | None = None,
    prefer_configured: bool = True,
) -> dict[str, Any]:
    """Resolve which hosted provider should execute a request.

    Rules (Automatic):
      Can Kie execute? → Kie
      else WaveSpeed → WaveSpeed
      else fal → fal
      else → no certified hosted provider

    Pinned preference: use that provider if it can execute; else explain and propose next.
    Never silently switches after submission — callers must treat a different provider as a new option.
    """
    prefs = load_preferences()
    states = credential_states or {}
    candidates: list[dict[str, Any]] = []
    reasons: list[str] = []

    order = list(PRIORITY_ORDER)
    budget_pref = str(prefs.get("budgetPreference") or "balanced").lower()
    # low_cost prefers later (often cheaper) providers when multiple can execute;
    # quality keeps primary-first order; balanced keeps PRIORITY_ORDER.
    if budget_pref == "low_cost":
        order = list(reversed(PRIORITY_ORDER))
    elif budget_pref == "quality":
        order = list(PRIORITY_ORDER)
    pinned = pinned_provider(prefs)
    automatic = is_automatic(prefs)

    def _can_execute(pid: str) -> tuple[bool, str]:
        if capability and not provider_supports(pid, capability, min_status="Testing"):
            return False, f"{PROVIDERS[pid].display_name} does not support capability '{capability}' at Testing/Certified."
        if canonical_model:
            mapping = resolve_model_mapping(canonical_model, pid)
            if not mapping:
                return False, f"{PROVIDERS[pid].display_name} has no mapping for model '{canonical_model}'."
            status = mapping.get("status")
            if status == "Unsupported":
                return False, f"{PROVIDERS[pid].display_name} mapping for '{canonical_model}' is Unsupported."
            if status == "Available but Uncertified":
                # Allowed as alternative recommendation with disclosure, not Automatic primary pick
                return False, (
                    f"{PROVIDERS[pid].display_name} mapping for '{canonical_model}' is Available but Uncertified."
                )
        state = states.get(pid) or "missing"
        if prefer_configured and state not in ("verified", "unverified"):
            return False, f"{PROVIDERS[pid].display_name} API key is not configured ({state})."
        if state == "invalid":
            return False, f"{PROVIDERS[pid].display_name} API key is invalid."
        return True, f"{PROVIDERS[pid].display_name} can execute this request."

    for pid in order:
        ok, reason = _can_execute(pid)
        entry = {
            "providerId": pid,
            "displayName": PROVIDERS[pid].display_name,
            "role": PROVIDERS[pid].role,
            "recommended": PROVIDERS[pid].recommended,
            "canExecute": ok,
            "reason": reason,
            "credentialState": states.get(pid) or "missing",
            "modelMapping": resolve_model_mapping(canonical_model, pid) if canonical_model else None,
        }
        candidates.append(entry)
        if ok:
            reasons.append(reason)

    selected = None
    explanation = ""
    alternatives: list[dict[str, Any]] = []

    if not automatic and pinned:
        pinned_entry = next((c for c in candidates if c["providerId"] == pinned), None)
        if pinned_entry and pinned_entry["canExecute"]:
            selected = pinned_entry
            explanation = (
                f"Using preferred provider {pinned_entry['displayName']} "
                f"(user preference). Automatic recommendation is off."
            )
        else:
            why = (pinned_entry or {}).get("reason") or "preferred provider unavailable"
            # Propose next Automatic-capable provider without silent switch
            auto_pick = next((c for c in candidates if c["canExecute"]), None)
            if auto_pick:
                selected = None  # do not auto-switch
                alternatives = [auto_pick] + [
                    c for c in candidates if c["canExecute"] and c["providerId"] != auto_pick["providerId"]
                ]
                explanation = (
                    f"Preferred provider {PROVIDERS[pinned].display_name} cannot satisfy this request: {why}. "
                    f"{auto_pick['displayName']} is available as an alternative — "
                    f"present as a new execution option (do not silently switch)."
                )
            else:
                explanation = (
                    f"Preferred provider {PROVIDERS[pinned].display_name} cannot satisfy this request: {why}. "
                    "No certified hosted provider currently supports this workflow."
                )
    else:
        # Automatic: first in priority that can execute
        selected = next((c for c in candidates if c["canExecute"]), None)
        if selected:
            alternatives = [c for c in candidates if c["canExecute"] and c["providerId"] != selected["providerId"]]
            order_note = {
                "low_cost": "budget preference low_cost (prefer lower-cost capable providers)",
                "quality": "budget preference quality (prefer primary certified providers)",
                "balanced": "Automatic Recommendation order (Kie.ai → WaveSpeed.ai → fal.ai)",
            }.get(budget_pref, "Automatic Recommendation order")
            explanation = (
                f"This request is best executed using {selected['displayName']} because it supports "
                f"the selected certified model/capability and matches {order_note}."
            )
            if alternatives:
                explanation += " " + "; ".join(
                    f"{a['displayName']} is also compatible" for a in alternatives
                ) + "."
        else:
            explanation = "No certified hosted provider currently supports this workflow."

    return {
        "ok": selected is not None,
        "mode": "automatic" if automatic else "preferred",
        "preferredProvider": prefs.get("preferredProvider"),
        "budgetPreference": budget_pref,
        "selected": selected,
        "alternatives": alternatives,
        "candidates": candidates,
        "capability": capability,
        "canonicalModel": canonical_model,
        "providersForModel": providers_for_model(canonical_model) if canonical_model else [],
        "explanation": explanation,
        "silentSwitchForbidden": True,
        "mock": False,
    }


def describe_for_codirector(resolution: dict[str, Any]) -> dict[str, Any]:
    sel = resolution.get("selected") or {}
    alts = resolution.get("alternatives") or []
    return {
        "summary": resolution.get("explanation"),
        "recommendedProvider": sel.get("displayName"),
        "recommendedProviderId": sel.get("providerId"),
        "alternatives": [
            {"providerId": a["providerId"], "displayName": a["displayName"], "reason": a.get("reason")}
            for a in alts
        ],
        "noProvider": not resolution.get("ok"),
        "guidance": (
            "Do not silently switch providers after a job is submitted. "
            "If another provider is appropriate, present it as a new execution option with "
            "capability differences and estimated cost."
        ),
        "mock": False,
    }
