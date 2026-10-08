"""HTTP API for the shared LoRA Registry (one registry, all surfaces)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from . import registry
from .catalog import catalog_items, get_catalog_item
from .compat import LORA_CATEGORIES, CANONICAL_LORA_FAMILIES, modality_matches

router = APIRouter(prefix="/loras", tags=["loras"])


def _not_found(lora_id: str) -> HTTPException:
    return HTTPException(404, f"Unknown LoRA {lora_id}")


@router.get("")
def list_loras(
    category: Optional[str] = None,
    modality: Optional[str] = None,
    include_disabled: bool = True,
):
    """Full registry listing (management surface)."""
    records = registry.list_loras(include_disabled=include_disabled)
    if category:
        records = [r for r in records if (r.category or "").lower() == category.lower()]
    if modality:
        records = [r for r in records if modality_matches(r.modality, modality)]
    return {
        "loras": [r.public_dict() for r in records],
        "count": len(records),
        "families": list(CANONICAL_LORA_FAMILIES),
        "categories": list(LORA_CATEGORIES),
    }


@router.get("/catalog")
def list_catalog():
    """Curated optional downloads (Setup Wizard LoRA section)."""
    return {"items": [i.public_dict() for i in catalog_items()]}


@router.get("/compatible")
def compatible(
    modelFamily: str = Query("", description="Active Adept model family id"),
    modality: Optional[str] = None,
):
    """Enabled LoRAs compatible with the active model — the only selector feed.

    Deterministic data-driven filtering; never returns incompatible LoRAs.
    """
    records = registry.compatible_loras(modelFamily, modality=modality)
    return {
        "modelFamily": modelFamily,
        "modality": modality,
        "loras": [r.public_dict() for r in records],
        "count": len(records),
    }


@router.get("/scan")
def scan():
    """Discover installed LoRA files under shared model storage (no mutation)."""
    return {"candidates": registry.scan_for_loras()}


@router.post("/detect")
def detect(auto_enable: bool = True):
    """Register discovered files (idempotent; existing registrations kept)."""
    created = registry.register_detected_files(auto_enable=auto_enable)
    return {"registered": [r.public_dict() for r in created], "count": len(created)}


@router.post("/resolve")
def resolve_source(body: dict):
    """Resolve a Hugging Face or Civitai page. Does not download."""
    from .sources import resolve_lora_source

    try:
        resolved = resolve_lora_source(str(body.get("url") or ""))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return resolved.public_dict()


@router.post("/install-url")
def install_url(body: dict):
    """Download one resolved LoRA into Adept-managed storage."""
    if not body.get("confirm"):
        raise HTTPException(400, "Confirm the install before Adept UI downloads this LoRA.")
    try:
        return registry.install_from_url(
            str(body.get("url") or ""),
            filename=str(body.get("filename") or ""),
            allow_update=bool(body.get("update")),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/import")
async def import_lora(
    file: UploadFile = File(...),
    modelFamily: str = Form(""),
):
    """Import one local .safetensors file. The upload is weights only."""
    from .metadata import MAX_LORA_BYTES

    suffix = Path(file.filename or "").suffix.lower()
    if suffix != ".safetensors":
        raise HTTPException(400, "Choose a .safetensors LoRA file.")
    tmp = Path(tempfile.mkdtemp(prefix="adept-lora-")) / "upload.safetensors"
    size = 0
    try:
        with open(tmp, "wb") as handle:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_LORA_BYTES:
                    raise HTTPException(400, "That file is larger than Adept UI will install as a LoRA.")
                handle.write(chunk)
        return registry.import_local_file(tmp, original_name=file.filename or "lora.safetensors", model_family=modelFamily)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        try:
            tmp.parent.rmdir()
        except OSError:
            pass


@router.get("/token-status")
def token_status():
    from .sources import token_configured

    return token_configured()


@router.put("/token")
def save_token(body: dict):
    """Store a provider token outside the LoRA registry. The token is not returned."""
    provider = str(body.get("provider") or "").strip().lower()
    if provider not in {"huggingface", "civitai"}:
        raise HTTPException(400, "Choose Hugging Face or Civitai.")
    from ..secrets_store import set_secret

    secret_name = "hf_token" if provider == "huggingface" else "civitai_api_token"
    set_secret(secret_name, str(body.get("token") or ""))
    return {"provider": provider, "configured": bool(str(body.get("token") or "").strip())}


@router.post("/register")
def register(body: dict):
    """Register one LoRA from a local weights file (or catalog metadata)."""
    try:
        rec = registry.register_lora(
            name=str(body.get("name") or ""),
            file_path=str(body.get("path") or ""),
            model_family=str(body.get("modelFamily") or ""),
            compatible_model_families=body.get("compatibleModelFamilies") or body.get("compatible_model_families") or [],
            category=str(body.get("category") or "Other"),
            modality=str(body.get("modality") or "any"),
            version=str(body.get("version") or "1.0"),
            enabled=bool(body.get("enabled", True)),
            recommended_strength=body.get("recommendedStrength"),
            strength_min=body.get("strengthMin"),
            strength_max=body.get("strengthMax"),
            source_url=str(body.get("sourceUrl") or body.get("source_url") or ""),
            license=str(body.get("license") or ""),
            download_size_bytes=body.get("downloadSizeBytes"),
            checksum_sha256=str(body.get("checksumSha256") or body.get("checksum_sha256") or ""),
            catalog_id=str(body.get("catalogId") or body.get("catalog_id") or ""),
            notes=str(body.get("notes") or ""),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return rec.public_dict()


@router.post("/{lora_id}/enable")
def enable(lora_id: str):
    try:
        return registry.set_lora_enabled(lora_id, True).public_dict()
    except KeyError as exc:
        raise _not_found(lora_id) from exc


@router.post("/{lora_id}/disable")
def disable(lora_id: str):
    try:
        return registry.set_lora_enabled(lora_id, False).public_dict()
    except KeyError as exc:
        raise _not_found(lora_id) from exc


@router.delete("/{lora_id}")
def remove(lora_id: str, delete_file: bool = Query(False), approved: bool = Query(False)):
    """Remove from registry. File deletion (Adept-managed storage only)
    requires delete_file=true AND approved=true (model-manager convention)."""
    if delete_file and not approved:
        raise HTTPException(400, "File deletion requires explicit approval (approved=true).")
    try:
        return registry.unregister_lora(lora_id, delete_file=delete_file)
    except KeyError as exc:
        raise _not_found(lora_id) from exc


@router.post("/{lora_id}/download")
def download(lora_id: str, approved: bool = Query(False)):
    """Download a curated catalog LoRA (optional; explicit approval required)."""
    item = get_catalog_item(lora_id)
    if item is None:
        raise _not_found(lora_id)
    try:
        return registry.download_lora(lora_id, approved=approved)
    except PermissionError as exc:
        raise HTTPException(400, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except KeyError as exc:
        raise _not_found(lora_id) from exc


@router.get("/{lora_id}")
def get_lora_detail(lora_id: str):
    """One registry record (management detail / reload checks)."""
    rec = registry.get_lora(lora_id)
    if rec is None:
        raise _not_found(lora_id)
    return rec.public_dict()


@router.post("/refresh")
def refresh():
    """Re-validate file existence for every registered LoRA."""
    registry.refresh_installed_status()
    return {"ok": True, "loras": [r.public_dict() for r in registry.list_loras()]}
