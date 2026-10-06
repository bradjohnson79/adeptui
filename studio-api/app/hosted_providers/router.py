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


class CatalogReviewBody(BaseModel):
    action: Literal["approved", "hidden", "pending_review"]


class CatalogRefreshBody(BaseModel):
    providers: Optional[list[str]] = None


@router.get("/catalog")
def get_provider_catalog(provider: Optional[str] = None, reviewStatus: Optional[str] = None):
    """Stored provider video catalog + review flags. Reads disk only."""
    from .catalog_sync import list_catalog

    return {"ok": True, **list_catalog(provider=provider, review_status=reviewStatus), "mock": False}


@router.post("/catalog/refresh")
async def refresh_provider_catalog(body: Optional[CatalogRefreshBody] = None):
    """Admin/developer: re-enumerate all keyed provider video catalogs.

    Read-only against providers (catalog/schema reads only — never a
    generation call). Newly discovered endpoints are flagged
    ``pending_review`` and are never auto-exposed to creators.
    """
    from .catalog_sync import refresh_all

    return await refresh_all(providers=(body.providers if body else None))


@router.post("/catalog/review/{row_id:path}")
def review_catalog_endpoint(row_id: str, body: CatalogReviewBody):
    """Admin review decision for one catalog row (approve/hide).

    Approval makes the row ELIGIBLE for registry merge; it never exposes
    the endpoint to creators by itself.
    """
    from .catalog_sync import review_endpoint

    row = review_endpoint(row_id, body.action)
    if row is None:
        raise HTTPException(404, f"Unknown catalog row: {row_id}")
    return {"ok": True, "row": row, "mock": False}




@router.get("/elevenlabs/availability")
def elevenlabs_availability():
    """Direct ElevenLabs capability. The response never includes the API key."""
    from .elevenlabs_capability import elevenlabs_availability as _avail

    return _avail()


@router.get("/elevenlabs/voices")
def elevenlabs_voices():
    """Usable ElevenLabs voices. Identity is voice_id, not the display name."""
    from .elevenlabs_capability import require_route_or_raise
    from .adapters.elevenlabs_adapter import list_voices

    route = require_route_or_raise(capability="elevenlabs.voice", surface="voice-studio.voices")
    return list_voices(api_key=route["apiKey"])


@router.get("/elevenlabs/models")
def elevenlabs_models():
    """Models reported by ElevenLabs for this key."""
    from .elevenlabs_capability import require_route_or_raise
    from .adapters.elevenlabs_adapter import list_models

    route = require_route_or_raise(capability="elevenlabs.voice", surface="voice-studio.models")
    return list_models(api_key=route["apiKey"])

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
