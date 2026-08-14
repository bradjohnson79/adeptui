"""Map Production Dock model ids → runtime engine/family keys.

Dock registry ids are preference-layer identifiers. Image/video compilers and
queue workers speak family/engine ids (qwen2512, ltx, wan, fal_*). This module
is the only translation surface — no silent substitute when unmapped.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException

from .resolve import resolve_modality

# Dock model id → image recommend/compile family
IMAGE_FAMILY_BY_MODEL: dict[str, str] = {
    "qwen-image-2512-local": "qwen2512",
    "flux-local": "flux",
    "zimage-local": "zimage",
    "krea2-turbo-local": "krea2",
    "krea2-raw-local": "krea2",
    "flux-kie": "flux",
    "flux-fal": "flux",
    "nano-banana-kie": "imagen",
    "krea2-turbo-fal": "krea2",
    "krea2-medium-fal": "krea2",
    "krea2-large-fal": "krea2",
}

# Dock model id → video engine id used by resolve_engine_id / workflow_resolver
VIDEO_ENGINE_BY_MODEL: dict[str, str] = {
    "minimax-h3": "minimax-h3",
    "minimax-h3-t2v-local": "minimax-h3",
    "minimax-h3-i2v-local": "minimax-h3",
    "ltx-local": "ltx",
    "wan-local": "wan",
    "hunyuan-video-1.5-local": "hunyuan15",
    "hunyuan-video-13b-local": "hunyuan13b",
    "kling-kie": "fal_kling",
    "kling-fal": "fal_kling",
    "seedance-fal": "fal_seedance",
    "veo-fal": "fal_veo",
}

# Dock LLM id → Ollama / config selectedModel
LLM_OLLAMA_BY_MODEL: dict[str, str] = {
    "ollama-gemma4-31b": "gemma4:31b-it-qat",
    "ollama-gemma4-12b": "gemma4:12b",
    "qwen-local": "qwen2.5:14b",
    "qwen": "qwen2.5:14b",
    "gemma-local": "gemma2:9b",
    "llama-local": "llama3.1:8b",
    "mistral-local": "mistral:7b",
}

# Live Ollama tags use a reversible dock id so ":" is never mangled to "-".
OLLAMA_TAG_DOCK_PREFIX = "ollama-tag:"


def dock_id_for_ollama_tag(tag: str) -> str:
    """Build a dock model id that round-trips to the exact Ollama tag."""
    name = (tag or "").strip()
    if not name:
        return ""
    return f"{OLLAMA_TAG_DOCK_PREFIX}{name}"


def image_family_for_dock_model(model_id: Optional[str]) -> Optional[str]:
    if not model_id:
        return None
    return IMAGE_FAMILY_BY_MODEL.get(model_id)


def video_engine_for_dock_model(model_id: Optional[str]) -> Optional[str]:
    if not model_id:
        return None
    return VIDEO_ENGINE_BY_MODEL.get(model_id)


def llm_ollama_for_dock_model(model_id: Optional[str]) -> Optional[str]:
    if not model_id:
        return None
    if model_id in LLM_OLLAMA_BY_MODEL:
        return LLM_OLLAMA_BY_MODEL[model_id]
    if model_id.startswith(OLLAMA_TAG_DOCK_PREFIX):
        return model_id[len(OLLAMA_TAG_DOCK_PREFIX) :]
    # Legacy static ids only — do not invent tags by stripping "ollama-"
    # (that mangled live tags like qwen3.6:35b-a3b → qwen3.6-35b-a3b).
    return None


def require_executable_route(project_id: str, modality: str) -> dict[str, Any]:
    """Resolve dock selection; raise 409 when not executable (degraded-mode block)."""
    selection = resolve_modality(project_id or "_global", modality)  # type: ignore[arg-type]
    if not selection.executable:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "NO_EXECUTABLE_ROUTE",
                "message": selection.blockedReason or f"No executable {modality} route",
                "modality": modality,
                "activeModelId": selection.activeModelId,
                "source": selection.source,
                "provenance": selection.provenance.model_dump() if selection.provenance else None,
            },
        )
    return {
        "activeModelId": selection.activeModelId,
        "activeLabel": selection.activeLabel,
        "source": selection.source,
        "runtime": selection.runtime,
        "providerId": selection.providerId,
        "executable": selection.executable,
        "gpu": selection.gpu,
        "blockedReason": selection.blockedReason,
        "provenance": selection.provenance.model_dump() if selection.provenance else None,
        "imageFamily": image_family_for_dock_model(selection.activeModelId),
        "videoEngine": video_engine_for_dock_model(selection.activeModelId),
    }


def _style_preferred_family(creative_context: Any) -> str:
    """Resolve a creator-chosen visualStyle → data-driven preferred family.

    Mirrors the recommender's style→engine routing (e.g. anime/realistic_anime →
    illustrious) so the Production Dock can defer to style routing when the
    creator expressed an explicit style. Returns "" when no style or no mapping.
    """
    ctx = creative_context if isinstance(creative_context, dict) else {}
    style = (
        ctx.get("visualStyle")
        or (ctx.get("style_layers") or {}).get("user")
        or ""
    )
    style = str(style or "").strip()
    if not style:
        return ""
    try:
        from ..style_intelligence.registry import preferred_family_for_style

        fam = (preferred_family_for_style(style) or "").strip().lower()
        if fam:
            return fam
    except Exception:
        pass
    try:
        from ..image_runtime.certified_registry import certified_families_for_style

        candidates = certified_families_for_style(style)
        if candidates:
            return candidates[0]
    except Exception:
        pass
    return ""


def _family_executable(family: str) -> bool:
    """True only when the family has a Certified workflow (production-ready)."""
    if not family:
        return False
    try:
        from ..image_product.recommend import _executable

        return bool(_executable(family))
    except Exception:
        return False


def apply_image_dock_preference(project_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Gate + inject dock image family when request has no explicit family override.

    Style-aware: when the creator expressed a visualStyle that maps to a
    Certified-executable preferred family (e.g. anime → illustrious), that
    style routing takes priority over the dock's generic default family —
    unless the caller explicitly locked a model family. This keeps the
    Production Dock as the fallback for unstyled requests while honoring the
    data-driven style→engine routing for styled anime/realistic-anime work.
    """
    dock = require_executable_route(project_id, "image")
    out = dict(body or {})
    explicit = out.get("modelFamilyPreference") or out.get("model")
    # Treat legacy hardcodes as non-override when caller left default zimage without lock.
    locked = bool(out.get("lockModelFamily") or out.get("modelLocked"))
    if not explicit or (not locked and explicit in ("zimage", "auto", "default")):
        style_family = _style_preferred_family(out.get("creativeContext"))
        chosen = (
            style_family
            if (style_family and _family_executable(style_family))
            else dock.get("imageFamily")
        )
        if chosen:
            out["modelFamilyPreference"] = chosen
    out.setdefault("productionDock", dock)
    return out


def apply_video_dock_preference(project_id: str, *, engine_hint: Optional[str] = None) -> dict[str, Any]:
    """Gate + return video engine from dock when hint is empty/auto."""
    dock = require_executable_route(project_id, "video")
    engine = engine_hint
    if not engine or str(engine).lower() in ("auto", "default", ""):
        engine = dock.get("videoEngine") or engine_hint or "minimax-h3"
    return {**dock, "engine": engine}
