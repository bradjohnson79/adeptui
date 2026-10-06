"""Evaluate one catalog candidate. Catalog row is not availability."""

from __future__ import annotations

from typing import Any

from ...production_control.image_generator_query import (
    ImageGeneratorCandidate,
    required_supports_for_task,
)
from .contracts import CandidateAvailability, FailureClass, FundingState, ProviderAvailability

_HOSTED_IDS = ("kie", "wavespeed", "fal")


def _supports_task(supports: tuple[str, ...] | list[str], task: str) -> bool:
    required = required_supports_for_task(task)
    have = {str(item or "").strip() for item in supports}
    return any(tag in have for tag in required)


def observe_hosted_provider_state(provider_id: str) -> ProviderAvailability:
    """Read Production Control / hosted cards. Never invent a zero balance."""

    pid = (provider_id or "").strip().lower()
    if pid in {"hosted", "api"}:
        pid = "fal"
    if pid not in _HOSTED_IDS:
        return ProviderAvailability(
            provider_id=pid or "unknown",
            provider_configured=pid == "local" or pid == "comfy",
            provider_reachable=pid in {"local", "comfy"},
            provider_funded=True,
            funding_state="sufficient" if pid in {"local", "comfy"} else "unknown",
        )
    try:
        from ...hosted_providers.service import provider_card

        card = provider_card(pid)
    except Exception as exc:
        return ProviderAvailability(
            provider_id=pid,
            provider_configured=False,
            provider_reachable=False,
            provider_funded=True,
            funding_state="unknown",
            failure_class="provider_unavailable",
            probe={"error": str(exc), "balance": None},
        )
    status = card.get("apiKeyStatus") or {}
    configured = bool(status.get("configured"))
    state = str(status.get("state") or "missing")
    invalid = state == "invalid"
    reachable = configured and not invalid
    balance = card.get("availableBalance")
    funding: FundingState = "unknown"
    funded = True
    failure: FailureClass = ""
    if not configured:
        failure = "provider_unavailable"
    elif invalid:
        failure = "credentials_invalid"
    if balance is None:
        funding = "unknown"
        funded = True
    else:
        try:
            amount = float(balance)
        except (TypeError, ValueError):
            funding = "unknown"
            funded = True
        else:
            if amount <= 0:
                funding = "exhausted"
                funded = False
                failure = failure or "insufficient_funds"
            elif amount < 1:
                funding = "low"
                funded = True
            else:
                funding = "sufficient"
                funded = True
    return ProviderAvailability(
        provider_id=pid,
        provider_configured=configured,
        provider_reachable=reachable,
        provider_funded=funded,
        funding_state=funding,
        failure_class=failure,
        probe={
            "connectionStatus": card.get("connectionStatus"),
            "healthStatus": card.get("healthStatus"),
            "balance": balance,
            "state": state,
        },
    )


def evaluate_candidate(
    candidate: ImageGeneratorCandidate | None,
    *,
    task: str,
    provider_state: ProviderAvailability | None = None,
    local_runtime_ready: bool = True,
    named: str = "",
) -> CandidateAvailability:
    if candidate is None:
        return CandidateAvailability(
            model_id=named or "",
            provider="",
            locality="",
            model_known=False,
            model_supported=False,
            model_available=False,
            request_valid=True,
            funding_state="unknown",
            failure_class="model_unavailable",
            why="catalog has no matching generator",
            label=named,
        )

    supported = _supports_task(candidate.supports, task)
    catalog_exec = bool(candidate.executable)
    if candidate.is_local:
        configured = True
        reachable = bool(local_runtime_ready)
        funded = True
        funding: FundingState = "sufficient"
        failure: FailureClass = ""
        if not catalog_exec:
            failure = "model_unavailable"
        elif not supported:
            failure = "endpoint_unsupported"
        elif not reachable:
            failure = "provider_unavailable"
        available = catalog_exec and supported and reachable
        why = (
            "local executable and runtime ready"
            if available
            else (
                "catalog row is not executable"
                if not catalog_exec
                else ("task not supported" if not supported else "local runtime is not ready")
            )
        )
        return CandidateAvailability(
            model_id=candidate.model_id,
            provider=candidate.provider or "comfy",
            locality="local",
            provider_configured=configured,
            provider_reachable=reachable,
            provider_funded=funded,
            model_known=True,
            model_supported=supported,
            model_available=available,
            request_valid=True,
            funding_state=funding,
            failure_class=failure,
            executable_catalog=catalog_exec,
            why=why,
            label=candidate.label or candidate.model_id,
        )

    pid = (candidate.provider or "").strip().lower() or "hosted"
    state = provider_state or observe_hosted_provider_state(pid)
    if not catalog_exec:
        failure = "model_unavailable"
    elif not supported:
        failure = "endpoint_unsupported"
    elif not state.provider_configured:
        failure = "provider_unavailable"
    elif not state.provider_reachable:
        failure = state.failure_class or "credentials_invalid"
    elif not state.provider_funded or state.funding_state == "exhausted":
        failure = "insufficient_funds"
    else:
        failure = ""
    available = bool(
        catalog_exec
        and supported
        and state.provider_configured
        and state.provider_reachable
        and state.provider_funded
        and state.funding_state != "exhausted"
    )
    why = (
        "hosted executable, provider ready"
        if available
        else (
            "catalog row is not executable"
            if not catalog_exec
            else (
                "task not supported"
                if not supported
                else (
                    f"provider {pid} not configured"
                    if not state.provider_configured
                    else (
                        f"provider {pid} not reachable"
                        if not state.provider_reachable
                        else f"provider {pid} funding={state.funding_state}"
                    )
                )
            )
        )
    )
    return CandidateAvailability(
        model_id=candidate.model_id,
        provider=pid,
        locality="hosted",
        provider_configured=state.provider_configured,
        provider_reachable=state.provider_reachable,
        provider_funded=state.provider_funded,
        model_known=True,
        model_supported=supported,
        model_available=available,
        request_valid=True,
        funding_state=state.funding_state,
        failure_class=failure,
        executable_catalog=catalog_exec,
        why=why,
        label=candidate.label or candidate.model_id,
    )
