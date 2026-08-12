#!/usr/bin/env python3
"""M42 W1 — probe local Comfy model dirs + config for runtime inventory."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "studio-api"))
ART = REPO / "artifacts" / "m42" / "w1"
ART.mkdir(parents=True, exist_ok=True)

# Typical Comfy Desktop shared models root (Windows Adept install)
_CANDIDATE_MODELS_ROOTS = [
    Path(r"C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Shared\models"),
    Path(r"C:\Users\bradj\AppData\Local\Programs\ComfyUI\models"),
    Path(r"C:\ComfyUI\models"),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _list_files(root: Path, *subdirs: str, suffixes: tuple[str, ...] = (".safetensors", ".ckpt", ".pt", ".pth", ".bin")) -> list[dict]:
    out: list[dict] = []
    for sub in subdirs:
        d = root / sub
        if not d.is_dir():
            continue
        for p in d.rglob("*"):
            if p.is_file() and p.suffix.lower() in suffixes:
                rel = str(p.relative_to(root)).replace("\\", "/")
                out.append({"name": p.name, "path": rel, "bytes": p.stat().st_size, "subdir": sub})
    return sorted(out, key=lambda x: x["path"].lower())


def _classify_checkpoints(files: list[dict]) -> dict[str, list[dict]]:
    buckets: dict[str, list[dict]] = {
        "flux": [],
        "sdxl": [],
        "sd35": [],
        "pony": [],
        "illustrious": [],
        "juggernaut": [],
        "dreamshaper": [],
        "realvis": [],
        "hidream": [],
        "zimage": [],
        "other": [],
    }
    for f in files:
        n = f["name"].lower()
        if "z_image" in n or "zimage" in n:
            buckets["zimage"].append(f)
        elif "flux" in n:
            buckets["flux"].append(f)
        elif "sd3.5" in n or "sd35" in n:
            buckets["sd35"].append(f)
        elif "hidream" in n:
            buckets["hidream"].append(f)
        elif "pony" in n:
            buckets["pony"].append(f)
        elif "illustrious" in n:
            buckets["illustrious"].append(f)
        elif "juggernaut" in n:
            buckets["juggernaut"].append(f)
        elif "dreamshaper" in n:
            buckets["dreamshaper"].append(f)
        elif "realvis" in n:
            buckets["realvis"].append(f)
        elif "sdxl" in n or "xl" in n:
            buckets["sdxl"].append(f)
        else:
            buckets["other"].append(f)
    return buckets


def _probe_comfy_object_info(url: str) -> dict:
    try:
        import urllib.request

        with urllib.request.urlopen(url.rstrip("/") + "/object_info", timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if not isinstance(data, dict):
            return {"ok": False, "nodes": []}
        return {"ok": True, "nodes": sorted(data.keys()), "count": len(data)}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "nodes": []}


def main() -> int:
    from app.config import settings

    roots = [r for r in _CANDIDATE_MODELS_ROOTS if r.is_dir()]
    # Also try sibling of comfy input
    shared = settings.comfy_input_dir.parent / "models"
    if shared.is_dir() and shared not in roots:
        roots.insert(0, shared)

    models_root = roots[0] if roots else None
    inventory: dict = {
        "generatedAt": _now(),
        "modelsRoot": str(models_root) if models_root else None,
        "modelsRootExists": bool(models_root),
        "configDeclared": {
            "zimage_unet": settings.zimage_unet,
            "zimage_clip": settings.zimage_clip,
            "zimage_vae": settings.zimage_vae,
            "zimage_clip_vision": settings.zimage_clip_vision,
            "imagegen_flux_checkpoint": settings.imagegen_flux_checkpoint,
            "imagegen_hidream_checkpoint": settings.imagegen_hidream_checkpoint,
            "imagegen_sd35_checkpoint": settings.imagegen_sd35_checkpoint,
        },
        "checkpoints": [],
        "diffusionModels": [],
        "loras": [],
        "vaes": [],
        "controlnets": [],
        "upscaleModels": [],
        "clipVision": [],
        "textEncoders": [],
        "classifiedCheckpoints": {},
        "comfyObjectInfo": {},
        "customNodeHints": [],
        "notInstalledFamilies": [],
    }

    if models_root:
        inventory["checkpoints"] = _list_files(models_root, "checkpoints")
        inventory["diffusionModels"] = _list_files(models_root, "diffusion_models", "unet", "unets")
        inventory["loras"] = _list_files(models_root, "loras", "Lora", "LoRA")
        inventory["vaes"] = _list_files(models_root, "vae", "vaes")
        inventory["controlnets"] = _list_files(models_root, "controlnet", "controlnets")
        inventory["upscaleModels"] = _list_files(models_root, "upscale_models", "upscale")
        inventory["clipVision"] = _list_files(models_root, "clip_vision")
        inventory["textEncoders"] = _list_files(models_root, "text_encoders", "clip")
        all_ckpt = inventory["checkpoints"] + inventory["diffusionModels"]
        inventory["classifiedCheckpoints"] = _classify_checkpoints(all_ckpt)

    # Families requested in mission — mark presence
    classified = inventory.get("classifiedCheckpoints") or {}
    for fam in ("flux", "sdxl", "pony", "illustrious", "juggernaut", "dreamshaper", "realvis", "zimage", "sd35", "hidream"):
        if not classified.get(fam):
            inventory["notInstalledFamilies"].append(fam)

    inventory["comfyObjectInfo"] = _probe_comfy_object_info(settings.comfy_url)
    nodes = set(inventory["comfyObjectInfo"].get("nodes") or [])
    for hint in (
        "UNETLoader",
        "CheckpointLoaderSimple",
        "CLIPTextEncode",
        "VAEDecode",
        "KSampler",
        "ControlNetApply",
        "ControlNetLoader",
        "IPAdapterModelLoader",
        "ImageUpscaleWithModel",
        "UpscaleModelLoader",
        "TextEncodeZImageOmni",
    ):
        inventory["customNodeHints"].append({"node": hint, "present": hint in nodes})

    path = ART / "runtime_inventory.json"
    path.write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    print(f"wrote {path}")
    print(f"modelsRoot={inventory['modelsRoot']} checkpoints={len(inventory['checkpoints'])} loras={len(inventory['loras'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
