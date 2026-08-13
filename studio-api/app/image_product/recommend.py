"""Image family recommendation + cost/resource intelligence + whyThisModel (M42 W3)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..image_runtime.certified_registry import get_workflow, production_ready_keys

_REPO = Path(__file__).resolve().parents[3]
_PRICE = _REPO / "config" / "image-runtime" / "cloud-price-table.json"

_ANIME = re.compile(r"\b(anime|manga|cel.?shaded|illustration|cartoon|stylized)\b", re.I)
_PHOTO = re.compile(
    r"\b(photoreal|cinematic|production still|live.?action|realistic|portrait|film)\b", re.I
)
_EDIT = re.compile(r"\b(edit|inpaint|outpaint|refine|relight|upscale)\b", re.I)


def _price_table() -> dict[str, Any]:
    if _PRICE.is_file():
        return json.loads(_PRICE.read_text(encoding="utf-8"))
    return {"perImage": {}, "localDefaults": {}}


def _family_status(family: str) -> str:
    """Best status among family keys; Certified wins."""
    keys = {
        "zimage": ["zimage.txt2img", "zimage.ref_edit"],
        "flux": ["flux.txt2img", "flux.edit", "flux.reference"],
        # Canonical default open-weight family (Qwen-Image-2512).
        "qwen2512": ["qwen2512.txt2img", "qwen2512.character_concept", "qwen2512.character_profile"],
        "qwen-image-2512": ["qwen2512.txt2img", "qwen2512.character_concept", "qwen2512.character_profile"],
        # Legacy deferred Qwen checkpoint family (not the 2512 default).
        "qwen": ["qwen.txt2img", "qwen.edit", "qwen.reference"],
        "imagen": ["imagen.txt2img", "imagen.edit", "imagen.reference"],
        # Install/detect slots — honest Unknown until certified workflows land
        "hidream": ["hidream.txt2img"],
        "flux-schnell": ["flux.schnell.txt2img", "flux.txt2img"],
        "flux-dev": ["flux.dev.txt2img", "flux.txt2img"],
        # Krea 2 workflow keys land with the Phase B builders; Unknown until then.
        "krea2": ["krea2.turbo_txt2img", "krea2.raw_txt2img"],
        # Illustrious XL (SDXL anime engine) — single txt2img workflow.
        "illustrious": ["illustrious.txt2img"],
    }.get(family, [])
    statuses = []
    for k in keys:
        wf = get_workflow(k)
        if wf:
            statuses.append(wf.status)
    if "Certified" in statuses:
        return "Certified"
    if "Draft" in statuses:
        return "Draft"
    if "Deferred" in statuses:
        return "Deferred"
    if "Blocked" in statuses:
        return "Blocked"
    return "Unknown"


def _executable(family: str) -> bool:
    return _family_status(family) == "Certified"


def _estimates(family: str) -> dict[str, Any]:
    table = _price_table()
    local = (table.get("localDefaults") or {}).get(family) or {"generationTimeSec": 12, "vramGb": 12}
    cloud = (table.get("perImage") or {}).get(family)
    if family == "imagen":
        return {
            "generationTimeSec": 12,
            "vramGb": None,
            "costUsd": float(cloud or 0.04),
            "costLabel": f"${float(cloud or 0.04):.2f}",
            "providerKind": "cloud",
        }
    # Prefer registry VRAM when present
    if family in {"qwen2512", "qwen-image-2512"}:
        key = "qwen2512.txt2img"
    elif family == "zimage":
        key = "zimage.txt2img"
    elif family == "illustrious":
        key = "illustrious.txt2img"
    else:
        key = f"{family}.txt2img"
    wf = get_workflow(key)
    vram = None
    if wf and wf.vram_profile:
        vram = wf.vram_profile.get("recommendedGb") or wf.vram_profile.get("minimumGb")
    return {
        "generationTimeSec": int(local.get("generationTimeSec") or 12),
        "vramGb": float(vram if vram is not None else local.get("vramGb") or 12),
        "costUsd": 0.0,
        "costLabel": "Local GPU",
        "providerKind": "local",
    }


def _why(family: str, purpose: str, prompt: str) -> str:
    reasons = {
        "qwen2512": "Recommended open-weight image model (Qwen-Image-2512) — human realism, detail, and text rendering.",
        "qwen-image-2512": "Recommended open-weight image model (Qwen-Image-2512) — human realism, detail, and text rendering.",
        "flux": "Alternative open-weight image model for cinematic photorealistic stills.",
        "qwen": "Legacy Qwen Image family (deferred) — prefer Qwen-Image-2512.",
        "imagen": "Best match for high-quality cloud editing and polished stills.",
        "zimage": "Certified local fallback workflow when Qwen-Image-2512 is not yet executable.",
        "illustrious": "Illustrious XL 1.0 — preferred SDXL anime/animation/stylized/realistic-anime engine for anime-leaning styles.",
    }
    base = reasons.get(family, reasons["qwen2512"])
    if purpose:
        base = f"{base} Purpose: {purpose}."
    return base


def _display_name(family: str) -> str:
    if family in {"qwen2512", "qwen-image-2512"}:
        return "Qwen-Image-2512"
    if family == "illustrious":
        return "Illustrious XL 1.0"
    return family


def _family_supports_references(family: str) -> bool:
    """True when the family has a Certified workflow that can consume reference pixels."""
    try:
        from ..image_runtime.certified_registry import list_workflows

        for wf in list_workflows(model_family=family):
            if wf.status != "Certified":
                continue
            if bool((wf.capabilities or {}).get("supportsReferences", False)):
                return True
    except Exception:
        return False
    return False


# Families that are text-only (cannot consume reference pixels). When a
# reference image is attached, the recommender must never silently route to one
# of these — reference fidelity overrides style routing (Amendment 3 / Phase 5).
_TEXT_ONLY_FAMILIES: frozenset[str] = frozenset({"illustrious"})


def recommend_image_family(
    *,
    prompt: str = "",
    purpose: str = "",
    operation: str = "image.generate",
    model_family_preference: str | None = None,
    quality: str = "standard",
    style: str | None = None,
    reference_asset_id: str | None = None,
) -> dict[str, Any]:
    text = f"{purpose} {prompt}"
    preferred = (model_family_preference or "").strip().lower() or None
    if preferred in {"qwen-image-2512", "qwen_image_2512"}:
        preferred = "qwen2512"

    # Reference-first hierarchy (Amendment 3 / Phase 5): when a reference image
    # is attached it is the visual authority. Reference-capable Certified
    # families take precedence over style routing, and a reference-locked
    # request NEVER routes to a text-only family (e.g. Illustrious) that would
    # silently drop reference conditioning. This mirrors the guard in
    # ``character_identity.visual_sheet._build_candidate_routing_plan``.
    reference_locked = bool(reference_asset_id)
    if reference_locked:
        # zimage.ref_edit is the only Certified reference-capable workflow today.
        # If the style-preferred or caller-preferred family is text-only, refuse
        # it for reference conditioning and prefer a reference-capable family.
        ref_capable_default = "zimage" if _family_supports_references("zimage") else "qwen2512"
        if preferred and (preferred in _TEXT_ONLY_FAMILIES or not _family_supports_references(preferred)):
            preferred = ref_capable_default
        if style:
            try:
                from ..style_intelligence.registry import preferred_family_for_style

                style_pref = (preferred_family_for_style(style) or "").strip().lower()
            except Exception:
                style_pref = ""
            if style_pref and (style_pref in _TEXT_ONLY_FAMILIES or not _family_supports_references(style_pref)):
                # Style preference is text-only; reference fidelity overrides it.
                style_pref = ""
            # When reference-locked, style only refines within reference-capable
            # families — do not let a text-only style family win.
            if not preferred:
                preferred = style_pref or ref_capable_default

    # Data-driven style→engine routing: consult the style registry's
    # preferredFamily (e.g. anime/realistic_anime → illustrious) and the
    # Certified registry's styleTags. Only Certified-executable families are
    # preferred; otherwise we fall back to the default recommender.
    style_preferred = ""
    if style:
        try:
            from ..style_intelligence.registry import preferred_family_for_style

            style_preferred = (preferred_family_for_style(style) or "").strip().lower()
        except Exception:
            style_preferred = ""
    if not style_preferred and style:
        try:
            from .certified_registry import certified_families_for_style

            candidates = certified_families_for_style(style)
            if candidates:
                style_preferred = candidates[0]
        except Exception:
            pass

    # Reference-locked: never let a text-only family win, even via style routing.
    if reference_locked and style_preferred in _TEXT_ONLY_FAMILIES:
        style_preferred = ""

    if preferred in {"flux", "qwen", "qwen2512", "imagen", "zimage", "illustrious"}:
        primary = preferred
    elif style_preferred and _executable(style_preferred):
        primary = style_preferred
    elif _EDIT.search(text) or operation in {"image.edit", "image.reference"}:
        primary = "imagen" if _executable("imagen") or _family_status("imagen") == "Draft" else "qwen2512"
    elif _ANIME.search(text):
        primary = "illustrious" if _executable("illustrious") else "qwen2512"
    elif _PHOTO.search(text) or purpose in {"marketing", "poster", "production_still", "concept_art"}:
        # Photoreal intents still recommend Qwen-2512 by default; FLUX remains the open-weight alternative.
        primary = "qwen2512"
    else:
        primary = "qwen2512"

    # Reference-locked final guard: a text-only family must never be the primary
    # when a reference image is attached.
    if reference_locked and primary in _TEXT_ONLY_FAMILIES:
        primary = "zimage" if _executable("zimage") else "qwen2512"

    # Execution fallback: only Certified families execute in production
    exec_family = primary
    if not _executable(exec_family):
        for candidate in ("qwen2512", "zimage", "flux", "illustrious"):
            if candidate != primary and _executable(candidate):
                exec_family = candidate
                break
        if not _executable(exec_family) and _executable("zimage"):
            exec_family = "zimage"

    alts = []
    for fam in ("flux", "zimage", "qwen", "imagen", "illustrious"):
        if fam == primary:
            continue
        label_family = fam
        alts.append(
            {
                "family": label_family,
                "displayName": "FLUX" if fam == "flux" else fam,
                "role": "alternative" if fam == "flux" else "other",
                "status": _family_status(fam),
                "executable": _executable(fam),
                "whyThisModel": _why(fam, purpose, prompt),
                "estimates": _estimates(fam),
            }
        )

    return {
        "recommendedFamily": primary,
        "recommendedDisplayName": _display_name(primary),
        "executionFamily": exec_family,
        "status": _family_status(primary),
        "executable": _executable(primary),
        "fallbackApplied": exec_family != primary,
        "whyThisModel": _why(primary, purpose, prompt),
        "estimates": _estimates(primary),
        "executionEstimates": _estimates(exec_family),
        "alternatives": alts[:3],
        "overridable": True,
        "quality": quality,
        "defaultOpenWeight": "qwen-image-2512",
        "alternativeOpenWeight": "flux",
        "certifiedKeys": production_ready_keys(),
        "referenceLocked": reference_locked,
        "referenceAssetId": reference_asset_id,
    }
