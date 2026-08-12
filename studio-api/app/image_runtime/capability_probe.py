"""Runtime capability detection from inspection — not hard-coded assumptions (M42 W2)."""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path
from typing import Any

from .model_discovery import discover_modern_image_models
from .provider_registry import provider_inventory

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _comfy_object_info() -> dict[str, Any] | None:
    url = (os.environ.get("COMFY_URL") or "http://127.0.0.1:8188").rstrip("/")
    try:
        with urllib.request.urlopen(f"{url}/object_info", timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def probe_runtime_capabilities() -> dict[str, Any]:
    discovery = discover_modern_image_models()
    families = discovery.get("families") or {}
    object_info = _comfy_object_info()
    nodes = set(object_info.keys()) if isinstance(object_info, dict) else set()

    has_controlnet = bool(nodes & {"ControlNetLoader", "ControlNetApply", "ControlNetApplyAdvanced"})
    has_lora = bool(nodes & {"LoraLoader", "LoraLoaderModelOnly"})
    has_inpaint = bool(nodes & {"VAEEncodeForInpaint", "SetLatentNoiseMask", "InpaintModelConditioning"})
    has_upscale = bool(nodes & {"UpscaleModelLoader", "ImageUpscaleWithModel"})
    has_zimage = bool(nodes & {"TextEncodeZImageOmni", "UNETLoader"})
    has_clip_vision = bool(nodes & {"CLIPVisionLoader", "CLIPVisionEncode"}) or "clip_vision" in str(nodes).lower()

    z_ok = bool((families.get("zimage") or {}).get("installed")) and has_zimage
    flux_ok = bool((families.get("flux") or {}).get("installed"))
    qwen_ok = bool((families.get("qwen") or {}).get("installed"))
    imagen_ok = bool((families.get("imagen") or {}).get("credentialConfigured"))

    caps = {
        "supportsReferenceEditing": z_ok or flux_ok or qwen_ok or has_clip_vision,
        "supportsControlNet": has_controlnet,
        "supportsLoRA": has_lora,
        "supportsICLoRA": "ICLoRA" in str(nodes) or "ic_lora" in str(nodes).lower(),
        "supportsIdentityPreservation": False,  # Wave 5
        "supportsInpainting": has_inpaint,
        "supportsOutpainting": has_inpaint,
        "supportsFill": flux_ok and ("fill" in str((families.get("flux") or {}).get("sampleFiles") or []).lower()),
        "supportsBatchGeneration": True if nodes else False,
        "supportsUpscale": has_upscale,
        "supportsZImage": z_ok,
        "supportsFlux": flux_ok,
        "supportsQwenImage": qwen_ok,
        "supportsImagen": imagen_ok,
        "comfyNodesObserved": len(nodes),
        "comfyReachable": object_info is not None,
    }

    return {
        "phase": "M42-W2",
        "capabilities": caps,
        "source": "runtime_inspection",
        "families": {k: {"installed": v.get("installed"), "statusHint": v.get("statusHint")} for k, v in families.items()},
        "providers": provider_inventory(),
    }


def write_capabilities_artifact(path: Path | None = None) -> Path:
    out = path or (_REPO_ROOT / "artifacts" / "m42" / "w2" / "runtime_capabilities.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    data = probe_runtime_capabilities()
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return out
