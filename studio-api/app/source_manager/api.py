"""Source Manager HTTP API — /api/source-manager/*"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .migration import ensure_migrated
from .persistence import get_source, list_sources, remove_source
from .registry import detect_all, get_provider, select_provider
from .service import (
    get_overview,
    remove_component_source,
    save_verified_source_for_component,
    verify_and_select,
)
from ..setup.download_sources.service import verify_source_url

router = APIRouter(prefix="/source-manager", tags=["source-manager"])


class VoiceModelInstallBody(BaseModel):
    confirm: bool = True
    confirm_download_models: bool = Field(default=False, alias="confirmDownloadModels")

    model_config = {"populate_by_name": True}


@router.get("/overview")
def source_manager_overview():
    try:
        return get_overview()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, str(exc)) from exc


@router.get("/providers")
def source_manager_providers():
    ensure_migrated()
    return {"providers": [item.to_dict() for item in detect_all()]}


@router.post("/providers/{provider_id}/detect")
def source_manager_provider_detect(provider_id: str):
    provider = get_provider(provider_id)
    if not provider:
        raise HTTPException(404, f"Unknown provider: {provider_id}")
    return provider.detect().to_dict()


@router.get("/sources")
def source_manager_sources():
    ensure_migrated()
    return {"sources": list(list_sources().values())}


@router.get("/sources/{source_id}")
def source_manager_source(source_id: str):
    ensure_migrated()
    record = get_source(source_id)
    if not record:
        raise HTTPException(404, "Source not found")
    return record


@router.delete("/sources/{source_id}")
def source_manager_delete_source(source_id: str):
    ensure_migrated()
    if not remove_source(source_id):
        raise HTTPException(404, "Source not found")
    return {"ok": True, "sourceId": source_id}


@router.post("/sources/verify")
def source_manager_verify(body: dict):
    url = str(body.get("url") or body.get("sourceUrl") or "").strip()
    if not url:
        raise HTTPException(400, "url is required")
    component_id = body.get("componentId") or body.get("component_id")
    revision = body.get("revision")
    try:
        return verify_and_select(url, component_id=component_id, revision=revision)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, str(exc)) from exc


@router.post("/components/{component_id}/source")
def source_manager_assign_component_source(component_id: str, body: dict):
    """Verify (if needed) and assign a source to a component — dual-writes legacy override."""
    verification = body.get("verification")
    if verification is None:
        url = str(body.get("url") or body.get("sourceUrl") or "").strip()
        if not url:
            raise HTTPException(400, "url or verification is required")
        verification = verify_source_url(
            url=url,
            component_id=component_id,
            revision=body.get("revision"),
            asset_name=body.get("assetName") or body.get("asset_name"),
            selected_files=body.get("selectedFiles") or body.get("selected_files"),
        )
    try:
        return save_verified_source_for_component(component_id, verification)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/components/{component_id}/source")
def source_manager_remove_component_source(component_id: str):
    return remove_component_source(component_id)


@router.post("/select-provider")
def source_manager_select_provider(body: dict):
    from .contracts import SourceInput

    source_input = SourceInput(
        url=body.get("url"),
        local_path=body.get("localPath") or body.get("local_path"),
        provider_hint=body.get("providerHint") or body.get("provider_hint"),
        revision=body.get("revision"),
        component_id=body.get("componentId") or body.get("component_id"),
    )
    provider = select_provider(source_input)
    return {"providerId": provider.id, "provider": provider.detect().to_dict()}


@router.get("/voice-models")
def source_manager_voice_models():
    from .voice_models import list_voice_models

    return list_voice_models()


@router.post("/voice-models/{component_id}/install")
def source_manager_voice_model_install(
    component_id: str,
    body: VoiceModelInstallBody | None = None,
):
    from .voice_models import enqueue_voice_install

    payload = body or VoiceModelInstallBody()
    try:
        return enqueue_voice_install(
            component_id,
            confirm=bool(payload.confirm),
            confirm_download_models=bool(payload.confirm_download_models),
        )
    except KeyError as exc:
        raise HTTPException(404, f"Unknown voice model: {component_id}") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, str(exc)) from exc


@router.post("/voice-models/{component_id}/uninstall")
def source_manager_voice_model_uninstall(component_id: str):
    from .voice_models import uninstall_voice_model

    try:
        return uninstall_voice_model(component_id)
    except KeyError as exc:
        raise HTTPException(404, f"Unknown voice model: {component_id}") from exc
