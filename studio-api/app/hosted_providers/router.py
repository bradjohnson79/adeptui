"""HTTP API for Hosted AI Providers (Setup → AI Providers)."""

from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import service
from .models import list_canonical_models
from .preferences import load_preferences, save_preferences
from .resolver import describe_for_codirector

router = APIRouter(prefix="/hosted-providers", tags=["hosted-providers"])


class ConnectBody(BaseModel):
    api_key: str = Field(..., min_length=1)


class PreferencesBody(BaseModel):
    preferredProvider: Literal["kie", "wavespeed", "fal", "automatic"] = "automatic"
    budgetPreference: Optional[str] = None


class ResolveBody(BaseModel):
    capability: Optional[str] = None
    canonicalModel: Optional[str] = None


class OpenAICompatConnectBody(BaseModel):
    displayName: str = "OpenAI-compatible"
    baseUrl: str = Field(..., min_length=1)
    api_key: str = Field(..., min_length=1)
    modelsPath: str = "/v1/models"
    chatPath: str = "/v1/chat/completions"
    billingCurrency: str = "USD"
    endpointId: Optional[str] = None


@router.get("")
def list_hosted():
    return service.catalog()


@router.get("/registry")
def registry():
    return service.registry_snapshot()


@router.get("/models")
def models(includeMappings: bool = False):
    return {
        "models": list_canonical_models(include_mappings=includeMappings),
        "note": "Users see canonical model names (e.g. FLUX), not provider-suffixed labels.",
        "mock": False,
    }


@router.get("/capabilities")
def capabilities():
    from .capabilities import capability_matrix

    return capability_matrix()


@router.get("/preferences")
def get_prefs():
    return load_preferences()


@router.put("/preferences")
def put_prefs(body: PreferencesBody):
    return save_preferences(
        preferred_provider=body.preferredProvider,
        budget_preference=body.budgetPreference,
    )


@router.post("/preferences/preferred")
def set_preferred(body: PreferencesBody):
    return service.set_preferred(body.preferredProvider)


@router.get("/discovery")
def get_discovery():
    from .discovery import discovery_status

    return discovery_status()


@router.post("/discovery")
async def post_discovery(providerId: Optional[str] = None):
    """Run Dynamic API Model Discovery for active or specified provider."""
    from .discovery import discover_active_provider, discover_provider

    if providerId:
        return await discover_provider(providerId, persist_as_active=True)
    return await discover_active_provider()


@router.get("/discovered-models")
def get_discovered_models(modality: Optional[str] = None, scope: Optional[str] = None):
    from .discovery import dock_api_models
    from .model_store import load_catalog

    if modality:
        return {"ok": True, "modality": modality, **dock_api_models(modality, scope=scope), "mock": False}
    cat = load_catalog()
    return {"ok": True, **cat, "mock": False}


@router.get("/openai-compatible")
def list_openai_compatible():
    from .custom_llm import list_endpoints

    return {"ok": True, "endpoints": list_endpoints(), "mock": False}


@router.post("/openai-compatible")
async def connect_openai_compatible(body: OpenAICompatConnectBody):
    from .custom_llm import connect_endpoint

    result = await connect_endpoint(
        display_name=body.displayName,
        base_url=body.baseUrl,
        api_key=body.api_key,
        models_path=body.modelsPath,
        chat_path=body.chatPath,
        billing_currency=body.billingCurrency,
        endpoint_id=body.endpointId,
    )
    if not result.get("ok"):
        raise HTTPException(400, result.get("message") or "Connect failed")
    return result


@router.delete("/openai-compatible/{endpoint_id}")
def delete_openai_compatible(endpoint_id: str):
    from .custom_llm import delete_endpoint

    if not delete_endpoint(endpoint_id):
        raise HTTPException(404, "Endpoint not found")
    return {"ok": True, "mock": False}


@router.post("/resolve")
def resolve(body: ResolveBody):
    resolution = service.resolve(capability=body.capability, canonical_model=body.canonicalModel)
    return {**resolution, "codirector": describe_for_codirector(resolution)}


@router.get("/{provider_id}")
def get_provider(provider_id: str):
    from .registry import PROVIDERS

    if provider_id not in PROVIDERS:
        raise HTTPException(404, f"Unknown provider: {provider_id}")
    return service.provider_card(provider_id)


@router.put("/{provider_id}/key")
async def connect(provider_id: str, body: ConnectBody):
    result = await service.connect_and_verify(provider_id, body.api_key)
    if not result.get("ok"):
        raise HTTPException(400, result.get("message") or "Connect failed")
    return result


@router.post("/{provider_id}/test")
async def test(provider_id: str):
    result = await service.test_provider(provider_id)
    if result.get("error") == "NOT_CONFIGURED":
        raise HTTPException(404, result.get("message"))
    if result.get("error") == "UNKNOWN_PROVIDER":
        raise HTTPException(404, result.get("message"))
    return result


@router.delete("/{provider_id}/key")
def clear_key(provider_id: str):
    result = service.clear_provider(provider_id)
    if not result.get("ok"):
        raise HTTPException(404, result.get("error") or "Unknown provider")
    return result
