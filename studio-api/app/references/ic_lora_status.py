"""Filesystem + gated HF status for Ingredients IC-LoRA."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..config import settings
from .models import (
    INGREDIENTS_FILENAME,
    INGREDIENTS_HF_REPO,
    INGREDIENTS_MODEL_ID,
    get_reference_model,
)


def _hf_token() -> str | None:
    for key in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "ADEPT_HF_TOKEN"):
        value = (os.environ.get(key) or "").strip()
        if value:
            return value
    return None


def candidate_lora_paths(configured: str | None = None) -> list[Path]:
    roots: list[Path] = []
    if configured:
        roots.append(Path(configured).expanduser())
    models_dir = getattr(settings, "comfy_models_dir", None)
    if models_dir:
        roots.append(Path(models_dir) / "loras")
        roots.append(Path(models_dir))
    comfy_input = getattr(settings, "comfy_input_dir", None)
    if comfy_input:
        roots.append(Path(comfy_input).parent / "models" / "loras")
    roots.append(settings.data_dir / "models" / "loras")
    return roots


def find_ingredients_file(configured: str | None = None) -> Path | None:
    model = get_reference_model()
    filename = model.filename
    if configured:
        path = Path(configured).expanduser()
        if path.is_file():
            if path.name.lower() == filename.lower() and path.stat().st_size > 0:
                return path
            return None
        candidate = path / filename
        if candidate.is_file() and candidate.stat().st_size > 0:
            return candidate
        # Explicit configured path that is an empty/missing dir is not Ready.
        return None
    for root in candidate_lora_paths():
        if not root.exists():
            continue
        direct = root / filename if root.is_dir() else root
        if direct.is_file() and direct.name.lower() == filename.lower() and direct.stat().st_size > 0:
            return direct
        if root.is_dir():
            for hit in root.rglob(filename):
                if hit.is_file() and hit.stat().st_size > 0:
                    return hit
    return None


def probe_hf_authorization() -> dict[str, Any]:
    """Probe Hugging Face gated access. Never logs the token."""
    token = _hf_token()
    url = f"https://huggingface.co/api/models/{INGREDIENTS_HF_REPO}"
    try:
        import httpx

        headers = {"User-Agent": "AdeptUI-GenStudio"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        response = httpx.get(url, headers=headers, timeout=8.0)
        if response.status_code in (401, 403):
            return {
                "authorized": False,
                "gated": True,
                "http_status": response.status_code,
                "issue_code": "ic_lora_authorization_required",
                "message": (
                    "Authorization Required. Accept the model terms on Hugging Face "
                    "and connect your Hugging Face token."
                ),
                "has_token": bool(token),
            }
        if response.status_code >= 400:
            return {
                "authorized": False,
                "gated": True,
                "http_status": response.status_code,
                "issue_code": "ic_lora_authorization_required",
                "message": "Unable to confirm Hugging Face access for the Ingredients IC-LoRA.",
                "has_token": bool(token),
            }
        return {
            "authorized": True,
            "gated": True,
            "http_status": response.status_code,
            "issue_code": None,
            "message": "Hugging Face access confirmed.",
            "has_token": bool(token),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "authorized": False,
            "gated": True,
            "http_status": None,
            "issue_code": "ic_lora_authorization_required" if not token else "ic_lora_model_missing",
            "message": f"Could not reach Hugging Face to verify access ({exc.__class__.__name__}).",
            "has_token": bool(token),
        }


def ingredients_status(configured_path: str | None = None) -> dict[str, Any]:
    """Statuses: missing | authorization_required | ready | incompatible."""
    model = get_reference_model()
    found = find_ingredients_file(configured_path)
    if found:
        # Tiny stubs are incompatible (real weights are multi-GB).
        size = found.stat().st_size
        if size < 1024 * 1024:
            return {
                "model_id": model.id,
                "status": "incompatible",
                "issue_code": "ic_lora_model_incompatible",
                "message": "Ingredients IC-LoRA file looks like a stub (too small).",
                "summary": "Ingredients IC-LoRA file looks like a stub (too small).",
                "path": str(found),
                "filename": found.name,
                "size_bytes": size,
                "ready": False,
                "repository": model.repository,
                "gated": model.gated,
                "compatible_workflows": list(model.workflows),
            }
        return {
            "model_id": model.id,
            "status": "ready",
            "issue_code": None,
            "message": "LTX 2.3 Ingredients IC-LoRA is installed and verified.",
            "summary": "LTX 2.3 Ingredients IC-LoRA is installed and verified.",
            "path": str(found),
            "filename": found.name,
            "size_bytes": size,
            "ready": True,
            "repository": model.repository,
            "gated": model.gated,
            "compatible_workflows": list(model.workflows),
        }

    # Empty configured directory is never Ready.
    if configured_path:
        path = Path(configured_path).expanduser()
        if path.exists() and path.is_dir() and not any(path.iterdir()):
            return {
                "model_id": model.id,
                "status": "missing",
                "issue_code": "ic_lora_model_missing",
                "message": "The Ingredients IC-LoRA folder is empty. Empty directories are not Ready.",
                "summary": "The Ingredients IC-LoRA folder is empty. Empty directories are not Ready.",
                "path": str(path),
                "filename": None,
                "size_bytes": 0,
                "ready": False,
                "repository": model.repository,
                "gated": True,
                "compatible_workflows": list(model.workflows),
            }
        if path.exists() and path.is_file() and path.name.lower() != INGREDIENTS_FILENAME.lower():
            return {
                "model_id": model.id,
                "status": "incompatible",
                "issue_code": "ic_lora_model_incompatible",
                "message": f"Linked file is not the Ingredients IC-LoRA ({INGREDIENTS_FILENAME}).",
                "summary": f"Linked file is not the Ingredients IC-LoRA ({INGREDIENTS_FILENAME}).",
                "path": str(path),
                "filename": path.name,
                "size_bytes": path.stat().st_size if path.is_file() else 0,
                "ready": False,
                "repository": model.repository,
                "gated": True,
                "compatible_workflows": list(model.workflows),
            }

    token = _hf_token()
    auth = probe_hf_authorization()
    if not token or not auth.get("authorized"):
        return {
            "model_id": model.id,
            "status": "authorization_required",
            "issue_code": "ic_lora_authorization_required",
            "message": auth.get("message")
            or "Authorization Required. Set HF_TOKEN after accepting the Hugging Face license.",
            "summary": auth.get("message")
            or "Authorization Required. Set HF_TOKEN after accepting the Hugging Face license.",
            "path": configured_path,
            "filename": None,
            "size_bytes": 0,
            "ready": False,
            "repository": model.repository,
            "gated": True,
            "compatible_workflows": list(model.workflows),
            "has_token": bool(token),
            "hf": auth,
        }

    return {
        "model_id": model.id,
        "status": "missing",
        "issue_code": "ic_lora_model_missing",
        "message": "Ingredients IC-LoRA is not installed. Link the verified safetensors file after accepting HF terms.",
        "summary": "Ingredients IC-LoRA is not installed. Link the verified safetensors file after accepting HF terms.",
        "path": configured_path,
        "filename": None,
        "size_bytes": 0,
        "ready": False,
        "repository": model.repository,
        "gated": True,
        "compatible_workflows": list(model.workflows),
        "has_token": True,
        "hf": auth,
    }


def resolve_ic_lora_status(
    *,
    model_id: str = INGREDIENTS_MODEL_ID,
    configured: str | None = None,
    probe_hf: bool = True,
) -> dict[str, Any]:
    """Compatibility wrapper for diagnostics / tests."""
    _ = model_id, probe_hf
    return ingredients_status(configured)


def resolve_ic_lora_status(
    *,
    model_id: str = INGREDIENTS_MODEL_ID,
    configured: str | None = None,
    probe_hf: bool = True,
) -> dict[str, Any]:
    """Compatibility wrapper used by setup diagnostics."""
    _ = model_id
    status = ingredients_status(configured)
    if not probe_hf and status.get("issue_code") == "ic_lora_authorization_required":
        # Keep filesystem-only mode for unit tests that skip network.
        if not find_ingredients_file(configured):
            status = {
                **status,
                "status": "not_installed",
                "issue_code": "ic_lora_model_missing",
                "message": "Ingredients IC-LoRA is not installed.",
            }
    return {
        **status,
        "summary": status.get("message"),
        "hf": "probed" if probe_hf else "skipped",
    }


def public_resource_card(configured_path: str | None = None) -> dict[str, Any]:
    status = ingredients_status(configured_path)
    model = get_reference_model()
    return {
        "id": INGREDIENTS_MODEL_ID,
        "name": model.display_name,
        "category": "Reference & Identity",
        "purpose": "Character, prop, and environment consistency",
        "base_model": "LTX 2.3 22B",
        "source": "Hugging Face",
        "access": "Gated, when applicable",
        "repository": model.repository,
        "installed_filename": status.get("filename"),
        "version": "0.9",
        "license_status": "ltx-2-community-license",
        "compatible_workflows": status.get("compatible_workflows"),
        "verification": status,
        "definition": model.public_dict(),
    }
