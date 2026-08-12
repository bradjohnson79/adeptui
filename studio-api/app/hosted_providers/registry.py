"""Canonical Hosted AI Provider tier — Kie.ai → WaveSpeed.ai → fal.ai."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ProviderId = Literal["kie", "wavespeed", "fal"]
RecommendationRole = Literal["primary", "secondary", "third"]

HOSTED_PROVIDER_VERSION = "m42.hosted.1"


@dataclass(frozen=True)
class HostedProviderDefinition:
    provider_id: ProviderId
    display_name: str
    role: RecommendationRole
    recommended: bool
    secret_name: str
    env_keys: tuple[str, ...]
    keys_url: str
    dashboard_url: str
    billing_url: str
    docs_url: str
    adapter_version: str
    # Integration tier: credential + resolution certified for all three.
    integration_status: Literal["Certified", "Testing", "Available but Uncertified", "Unsupported"]
    supported_modalities: tuple[str, ...]
    certified_models: tuple[str, ...]
    estimated_pricing_notes: str
    current_version: str = HOSTED_PROVIDER_VERSION


PROVIDERS: dict[str, HostedProviderDefinition] = {
    "kie": HostedProviderDefinition(
        provider_id="kie",
        display_name="Kie.ai",
        role="primary",
        recommended=True,
        secret_name="kie_api_key",
        env_keys=("KIE_API_KEY", "KIE_KEY"),
        keys_url="https://kie.ai/api-key",
        dashboard_url="https://kie.ai",
        billing_url="https://kie.ai",
        docs_url="https://docs.kie.ai",
        adapter_version="kie.1",
        integration_status="Certified",
        supported_modalities=("image", "video", "audio", "text"),
        certified_models=("FLUX", "Seedance", "Kling"),
        estimated_pricing_notes="BYOK credits on Kie.ai — see kie.ai pricing.",
    ),
    "wavespeed": HostedProviderDefinition(
        provider_id="wavespeed",
        display_name="WaveSpeed.ai",
        role="secondary",
        recommended=False,
        secret_name="wavespeed_api_key",
        env_keys=("WAVESPEED_API_KEY", "WAVESPEED_KEY"),
        keys_url="https://wavespeed.ai/accesskey",
        dashboard_url="https://wavespeed.ai",
        billing_url="https://wavespeed.ai/top-up",
        docs_url="https://wavespeed.ai/docs",
        adapter_version="wavespeed.1",
        integration_status="Certified",
        supported_modalities=("image", "video"),
        certified_models=("FLUX", "Seedance"),
        estimated_pricing_notes="BYOK credits on WaveSpeed.ai — top-up required to activate keys.",
    ),
    "fal": HostedProviderDefinition(
        provider_id="fal",
        display_name="fal.ai",
        role="third",
        recommended=False,
        secret_name="fal_api_key",
        env_keys=("FAL_KEY", "FAL_API_KEY"),
        keys_url="https://fal.ai/dashboard/keys",
        dashboard_url="https://fal.ai/dashboard",
        billing_url="https://fal.ai/dashboard/billing",
        docs_url="https://docs.fal.ai",
        adapter_version="fal.1",
        integration_status="Certified",
        supported_modalities=("video", "image"),
        certified_models=("Seedance", "Kling", "Veo", "Runway"),
        estimated_pricing_notes="BYOK credits on fal.ai — see fal.ai dashboard billing.",
    ),
}

# Recommendation order for Automatic mode
PRIORITY_ORDER: tuple[ProviderId, ...] = ("kie", "wavespeed", "fal")


def list_providers() -> list[dict[str, Any]]:
    out = []
    for pid in PRIORITY_ORDER:
        p = PROVIDERS[pid]
        d = asdict(p)
        d["envKeys"] = list(p.env_keys)
        d["supportedModalities"] = list(p.supported_modalities)
        d["certifiedModels"] = list(p.certified_models)
        d["priority"] = PRIORITY_ORDER.index(pid) + 1
        out.append(d)
    return out


def get_provider(provider_id: str) -> HostedProviderDefinition | None:
    return PROVIDERS.get((provider_id or "").strip().lower())
