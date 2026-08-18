"""LoRA compatibility taxonomy — data-driven family + modality rules.

One authoritative mapping from Adept model-family ids (as exposed by the
generator rosters and video engines) onto canonical LoRA model families.
Every UI selector and every generation adapter asks the registry through
:func:`compatible_loras`; nothing hardcodes filtering per surface.
"""

from __future__ import annotations

from typing import Iterable

# ── Canonical LoRA model families ────────────────────────────────────────
# A LoRA is compatible with a generator only when the generator's model
# family appears in the LoRA's compatible_model_families (or equals its
# model_family). Families are deliberately coarse so a LoRA trained for any
# member of a family (e.g. any SDXL/SD checkpoint) is exposed consistently.
LORA_FAMILY_SDXL = "sdxl"
LORA_FAMILY_FLUX = "flux"
LORA_FAMILY_QWEN_IMAGE = "qwen-image"
LORA_FAMILY_ZIMAGE = "zimage"
LORA_FAMILY_KREA2 = "krea2"
LORA_FAMILY_LTX = "ltx"
LORA_FAMILY_WAN = "wan"
LORA_FAMILY_HUNYUAN = "hunyuan"
LORA_FAMILY_UNASSIGNED = "unassigned"

CANONICAL_LORA_FAMILIES: tuple[str, ...] = (
    LORA_FAMILY_SDXL,
    LORA_FAMILY_FLUX,
    LORA_FAMILY_QWEN_IMAGE,
    LORA_FAMILY_ZIMAGE,
    LORA_FAMILY_KREA2,
    LORA_FAMILY_LTX,
    LORA_FAMILY_WAN,
    LORA_FAMILY_HUNYUAN,
    LORA_FAMILY_UNASSIGNED,
)

# ── Modality ─────────────────────────────────────────────────────────────
MODALITY_IMAGE = "image"
MODALITY_VIDEO = "video"
MODALITY_ANY = "any"

# ── Categories (coarse; do not over-engineer) ────────────────────────────
LORA_CATEGORIES: tuple[str, ...] = (
    "Style",
    "Character / Identity",
    "Environment",
    "Lighting",
    "Camera / Cinematic",
    "Motion",
    "Performance",
    "Technical",
    "Other",
)

# ── Adept model-family ids -> canonical LoRA families ────────────────────
# Keys are the family ids emitted by build_local_generator_models()
# (qwen2512 / zimage / illustrious / flux / krea2) plus the video engine ids
# used by Scene/Timeline (ltx / wan / hunyuan) and any alias spellings.
APP_FAMILY_TO_LORA_FAMILIES: dict[str, tuple[str, ...]] = {
    # SDXL / SD family (Illustrious XL is the current SDXL engine)
    "illustrious": (LORA_FAMILY_SDXL,),
    "illustrious-xl": (LORA_FAMILY_SDXL,),
    "sdxl": (LORA_FAMILY_SDXL,),
    "sd": (LORA_FAMILY_SDXL,),
    "sd3.5": (LORA_FAMILY_SDXL,),
    "sd3_5": (LORA_FAMILY_SDXL,),
    "hidream": (LORA_FAMILY_SDXL,),
    # FLUX
    "flux": (LORA_FAMILY_FLUX,),
    "flux1": (LORA_FAMILY_FLUX,),
    "flux-kontext": (LORA_FAMILY_FLUX,),
    # Qwen Image 2512
    "qwen2512": (LORA_FAMILY_QWEN_IMAGE,),
    "qwen-image-2512": (LORA_FAMILY_QWEN_IMAGE,),
    "qwen_image_2512": (LORA_FAMILY_QWEN_IMAGE,),
    "qwen": (LORA_FAMILY_QWEN_IMAGE,),
    # Z-Image
    "zimage": (LORA_FAMILY_ZIMAGE,),
    # Krea 2
    "krea2": (LORA_FAMILY_KREA2,),
    "krea-2": (LORA_FAMILY_KREA2,),
    # Video engines
    "ltx": (LORA_FAMILY_LTX,),
    "ltx-2.3": (LORA_FAMILY_LTX,),
    "ltx-2.5": (LORA_FAMILY_LTX,),
    "ltx2.3": (LORA_FAMILY_LTX,),
    "ltx2.5": (LORA_FAMILY_LTX,),
    "ltx23": (LORA_FAMILY_LTX,),
    "ltx_2_5": (LORA_FAMILY_LTX,),
    "wan": (LORA_FAMILY_WAN,),
    "wan2.2": (LORA_FAMILY_WAN,),
    "hunyuan": (LORA_FAMILY_HUNYUAN,),
    "hunyuan-video": (LORA_FAMILY_HUNYUAN,),
    # Closed / unknown providers never accept LoRAs (empty tuple).
    "fal": (),
    "kie": (),
    "cloud": (),
    "auto": (),
    "unknown": (),
}

# Fallback: unknown app families resolve to no compatible LoRA families.
UNKNOWN_FAMILY_FALLBACK: tuple[str, ...] = ()


def normalize_app_family(model_family: str | None) -> str:
    """Normalize an app family id to a stable lowercase key."""
    return str(model_family or "").strip().lower().replace(" ", "-")


def lora_families_for_app_family(model_family: str | None) -> tuple[str, ...]:
    """Canonical LoRA families compatible with an Adept model family id.

    Deterministic, data-driven: the UI and the generation adapters both call
    this (through `compatible_loras`) so a LoRA never leaks into a surface
    whose model family cannot load it.
    """
    key = normalize_app_family(model_family)
    if not key:
        return UNKNOWN_FAMILY_FALLBACK
    if key in APP_FAMILY_TO_LORA_FAMILIES:
        return APP_FAMILY_TO_LORA_FAMILIES[key]
    # Strip workflow-style suffixes (e.g. "ltx.scene" -> "ltx").
    base = key.split(".", 1)[0]
    if base in APP_FAMILY_TO_LORA_FAMILIES:
        return APP_FAMILY_TO_LORA_FAMILIES[base]
    return UNKNOWN_FAMILY_FALLBACK


def modality_matches(record_modality: str | None, requested: str | None) -> bool:
    """True when a record modality satisfies the requested modality filter."""
    if not requested:
        return True
    rm = str(record_modality or MODALITY_ANY).strip().lower()
    if rm == MODALITY_ANY:
        return True
    return rm == str(requested).strip().lower()


def infer_family_from_filename(filename: str) -> str:
    """Heuristic family inference for discovered LoRA files.

    Only used for auto-discovery registration; explicit registration always
    wins. Unknown files register as `unassigned` and stay out of every
    generator selector until the user assigns a family in management UI.
    """
    name = str(filename or "").lower()
    if "ltx" in name:
        return LORA_FAMILY_LTX
    if "wan" in name or "wan2" in name:
        return LORA_FAMILY_WAN
    if "hunyuan" in name:
        return LORA_FAMILY_HUNYUAN
    if "flux" in name:
        return LORA_FAMILY_FLUX
    if "qwen" in name:
        return LORA_FAMILY_QWEN_IMAGE
    if "zimage" in name or "z-image" in name:
        return LORA_FAMILY_ZIMAGE
    if "krea" in name:
        return LORA_FAMILY_KREA2
    if any(tag in name for tag in ("sdxl", "illustrious", "xl-v1", "sd_xl", "pony", "anime")):
        return LORA_FAMILY_SDXL
    return LORA_FAMILY_UNASSIGNED
