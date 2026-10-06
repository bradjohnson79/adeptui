"""Typed image-route lock, availability, and fallback audit."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from ...production_control.image_generator_query import ImageGeneratorCandidate

LockLevel = Literal["UNLOCKED", "PREFERRED", "STRICT"]
LockScope = Literal["", "model", "provider"]
FundingState = Literal["sufficient", "low", "exhausted", "unknown"]
FailureClass = Literal[
    "",
    "model_unavailable",
    "provider_unavailable",
    "credentials_invalid",
    "insufficient_funds",
    "endpoint_unsupported",
    "temporary_provider_error",
]


@dataclass(frozen=True)
class RouteLock:
    level: LockLevel = "UNLOCKED"
    scope: LockScope = ""
    requested_provider: str = ""
    requested_model_id: str = ""
    restated: bool = False

    def blocks_other_models(self) -> bool:
        return self.level == "STRICT" and self.scope != "provider"

    def blocks_other_providers(self) -> bool:
        return self.level == "STRICT"


@dataclass
class ProviderAvailability:
    provider_id: str
    provider_configured: bool = False
    provider_reachable: bool = False
    provider_funded: bool = True
    funding_state: FundingState = "unknown"
    failure_class: FailureClass = ""
    probe: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "providerId": self.provider_id,
            "providerConfigured": self.provider_configured,
            "providerReachable": self.provider_reachable,
            "providerFunded": self.provider_funded,
            "fundingState": self.funding_state,
            "failureClass": self.failure_class,
            "probe": dict(self.probe),
        }


@dataclass
class CandidateAvailability:
    model_id: str
    provider: str
    locality: str
    provider_configured: bool = False
    provider_reachable: bool = False
    provider_funded: bool = True
    model_known: bool = False
    model_supported: bool = False
    model_available: bool = False
    request_valid: bool = True
    funding_state: FundingState = "unknown"
    failure_class: FailureClass = ""
    executable_catalog: bool = False
    why: str = ""
    label: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "modelId": self.model_id,
            "provider": self.provider,
            "locality": self.locality,
            "providerConfigured": self.provider_configured,
            "providerReachable": self.provider_reachable,
            "providerFunded": self.provider_funded,
            "modelKnown": self.model_known,
            "modelSupported": self.model_supported,
            "modelAvailable": self.model_available,
            "requestValid": self.request_valid,
            "fundingState": self.funding_state,
            "failureClass": self.failure_class,
            "executableCatalog": self.executable_catalog,
            "why": self.why,
            "label": self.label,
        }


@dataclass
class FallbackAudit:
    requested_provider: str = ""
    requested_model_id: str = ""
    lock_level: str = "UNLOCKED"
    lock_scope: str = ""
    probes: list[dict[str, Any]] = field(default_factory=list)
    candidates: list[dict[str, Any]] = field(default_factory=list)
    selected_model_id: str = ""
    selected_provider: str = ""
    selected_locality: str = ""
    why: str = ""
    funding_state: str = "unknown"
    disclose: str = ""
    attempted: list[str] = field(default_factory=list)
    step: str = ""
    failure_class: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "requestedProvider": self.requested_provider,
            "requestedModelId": self.requested_model_id,
            "lockLevel": self.lock_level,
            "lockScope": self.lock_scope,
            "probes": list(self.probes),
            "candidates": list(self.candidates),
            "selectedModelId": self.selected_model_id,
            "selectedProvider": self.selected_provider,
            "selectedLocality": self.selected_locality,
            "why": self.why,
            "funding_state": self.funding_state,
            "disclose": self.disclose,
            "attempted": list(self.attempted),
            "step": self.step,
            "failureClass": self.failure_class,
        }


@dataclass
class ImageRoutePlan:
    selected: ImageGeneratorCandidate | None
    blocked: bool = False
    error: str = ""
    disclose: str = ""
    lock: RouteLock = field(default_factory=RouteLock)
    audit: FallbackAudit = field(default_factory=FallbackAudit)
    hosted: bool = False
    step: str = ""
    attempted: set[str] = field(default_factory=set)

    def as_observability(self) -> dict[str, Any]:
        data = self.audit.as_dict()
        data["blocked"] = self.blocked
        data["error"] = self.error
        if self.selected is not None:
            data["selected"] = self.selected.as_observability()
        return data
