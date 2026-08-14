from __future__ import annotations

"""Model-agnostic ImageGen Comfy workflow builders (FLUX-class default)."""

from typing import Any

# Creator-facing labels for local generator families. Keyed by the canonical
# family id used across routing/recommendation. Falls back to the registry
# modelFamily / _display_name when a family is not listed here.
_FAMILY_LABELS: dict[str, str] = {
    "qwen2512": "Qwen Image 2512",
    "illustrious": "Illustrious XL 1.0 (Anime)",
    "zimage": "Z-Image Turbo",
    "flux": "FLUX.1 Kontext [dev]",
    "krea2": "Local Krea 2",
}

# Preferred dropdown ordering for known families (Auto Select is always first).
_FAMILY_ORDER: tuple[str, ...] = ("qwen2512", "zimage", "illustrious", "flux", "krea2")


def _family_label(family: str, variant: str) -> str:
    if family in _FAMILY_LABELS:
        return _FAMILY_LABELS[family]
    base = family.replace("-", " ").replace("_", " ").title()
    return f"{base} {variant}".strip() if variant else base


def build_local_generator_models() -> list[dict[str, Any]]:
    """Authoritative Local Generator roster sourced from the Certified registry.

    The Character Creator / Character Creator Express dropdown must reflect
    installed + READY + Certified + capability-compatible local generators —
    never a hardcoded list. Each entry carries readiness/capability metadata so
    the selector can apply reference-aware eligibility (e.g. disable a
    text-to-image-only family when a Character Reference is attached).
    """
    from .image_runtime.certified_registry import list_workflows

    def _is_txt2img(wf) -> bool:
        return wf.operation in {"image.generate", "txt2img"} or "txt2img" in (
            wf.supported_operations or ()
        )

    # family -> aggregated option. ``_gen`` tracks whether the family has a
    # Certified text-to-image/generation workflow (what makes it a generator).
    families: dict[str, dict[str, Any]] = {}
    for wf in list_workflows():
        if (wf.provider_kind or "local").lower() != "local":
            continue
        canonical = "qwen2512" if wf.model_family in {"qwen-image-2512", "qwen_image_2512"} else wf.model_family
        entry = families.setdefault(
            canonical,
            {
                "id": canonical,
                "label": _family_label(canonical, wf.model_variant),
                "group": "local",
                "status": "Unknown",
                "supportsReferences": False,
                "supportsEditing": False,
                "executable": False,
                "_gen": False,
            },
        )
        # Certified wins for status.
        if wf.status == "Certified":
            entry["status"] = "Certified"
        elif entry["status"] == "Unknown":
            entry["status"] = wf.status
        # Executable as a generator requires a Certified txt2img/generation key.
        if wf.status == "Certified" and _is_txt2img(wf):
            entry["executable"] = True
            entry["_gen"] = True
        # Reference capability is a family-level property: any Certified
        # reference-capable workflow in the family (e.g. zimage.ref_edit) makes
        # the family reference-capable even though its txt2img key is not.
        if wf.status == "Certified" and bool((wf.capabilities or {}).get("supportsReferences", False)):
            entry["supportsReferences"] = True
        # Editing capability is a family-level property: any Certified editing
        # workflow (img2img/edit/inpaint/outpaint/fill) makes the family eligible
        # as a Stage 2 style-refinement engine.
        if wf.status == "Certified" and bool((wf.capabilities or {}).get("supportsEditing", False)):
            entry["supportsEditing"] = True

    # Keep only Certified generators (production-safe) by default; drop the
    # internal _gen marker from the public payload.
    ready = [
        {k: v for k, v in f.items() if k != "_gen"}
        for f in families.values()
        if f["_gen"] and f["executable"] and f["status"] == "Certified"
    ]

    # Character Sheet candidate source: Local Krea 2 is a real local family.
    # Workflows may still be Draft — keep status honest and never make it Auto default.
    krea_entry = families.get("krea2")
    if krea_entry and not any(o.get("id") == "krea2" for o in ready):
        executable = bool(krea_entry["_gen"] and krea_entry["executable"])
        if not executable:
            try:
                from .setup.diagnostics import verify_component

                executable = bool(verify_component("krea2_models").healthy)
            except Exception:
                executable = False
        ready.append(
            {
                "id": "krea2",
                "label": _family_label("krea2", ""),
                "group": "local",
                "status": krea_entry["status"],
                "supportsReferences": bool(krea_entry["supportsReferences"]),
                "supportsEditing": bool(krea_entry["supportsEditing"]),
                "executable": executable,
            }
        )

    def _sort(opt: dict[str, Any]) -> tuple[int, str]:
        try:
            return (_FAMILY_ORDER.index(opt["id"]), opt["label"])
        except ValueError:
            return (len(_FAMILY_ORDER), opt["label"])

    ready.sort(key=_sort)
    return [{"id": "auto", "label": "Auto Select", "group": "auto"}] + ready


# Backwards-compatible static snapshot. Prefer build_local_generator_models()
# for the live, registry-sourced roster.
IMAGEGEN_MODELS = build_local_generator_models()


def build_txt2img_workflow(
    *,
    checkpoint: str,
    positive: str,
    negative: str,
    width: int,
    height: int,
    seed: int,
    steps: int = 20,
    cfg: float = 3.5,
    filename_prefix: str = "studio/imagegen",
) -> dict[str, Any]:
    """
    Minimal checkpoint txt2img graph compatible with standard Comfy CheckpointLoaderSimple.
    Swap checkpoint for FLUX/SD3.5/HiDream weights as configured.
    """
    return {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": checkpoint},
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": positive, "clip": ["1", 1]},
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative or "blurry, low quality, watermark", "clip": ["1", 1]},
        },
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed if seed >= 0 else 0,
                "steps": max(4, steps),
                "cfg": cfg,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
            },
        },
        "6": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["5", 0], "vae": ["1", 2]},
        },
        "7": {
            "class_type": "SaveImage",
            "inputs": {"images": ["6", 0], "filename_prefix": filename_prefix},
        },
    }


def build_img2img_edit_stub(
    *,
    checkpoint: str,
    positive: str,
    negative: str,
    image_name: str,
    denoise: float = 0.45,
    seed: int = 0,
    steps: int = 16,
    filename_prefix: str = "studio/imagegen_edit",
) -> dict[str, Any]:
    """Simple img2img path used for edit operations until specialized graphs land."""
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint}},
        "2": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": positive, "clip": ["1", 1]}},
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative or "blurry, low quality", "clip": ["1", 1]},
        },
        "5": {"class_type": "VAEEncode", "inputs": {"pixels": ["2", 0], "vae": ["1", 2]}},
        "6": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed if seed >= 0 else 0,
                "steps": max(4, steps),
                "cfg": 3.5,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": denoise,
                "model": ["1", 0],
                "positive": ["3", 0],
                "negative": ["4", 0],
                "latent_image": ["5", 0],
            },
        },
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["1", 2]}},
        "8": {
            "class_type": "SaveImage",
            "inputs": {"images": ["7", 0], "filename_prefix": filename_prefix},
        },
    }



IMAGEGEN_MODELS = build_local_generator_models()
