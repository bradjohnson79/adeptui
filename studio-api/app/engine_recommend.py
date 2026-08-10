from __future__ import annotations

import re
from typing import Any

from .fal_catalog import is_fal_engine
from .secrets_store import secret_status
from .vram_profiles import get_profile, normalize_vram_tier


MOTION_RE = re.compile(
    r"\b(camera\s+(pan|tilt|dolly|truck|orbit|push|pull)|tracking\s+shot|whip\s+pan|"
    r"slow[\s-]?mo|action|fight|chase|runn(?:ing|er)|dance|spin|fly(?:ing)?)\b",
    re.I,
)


def recommend_engine(
    *,
    project: Any,
    scene: Any,
    prompt: str | None = None,
) -> dict[str, Any]:
    """Local-first engine recommendation. fal.ai is never selected for `auto`.

    Cloud engines appear only as optional alternatives in warnings when a fal key
    exists. User must explicitly choose a fal engine and approve paid fallback.
    """
    vram = normalize_vram_tier(getattr(project, "vram_gb", 32))
    profile = get_profile(vram)
    duration = float(getattr(scene, "duration_sec", 5) or 5)
    lipsync = bool(getattr(scene, "lipsync_enabled", 0))
    text = (prompt or getattr(scene, "prompt", "") or "") + " " + (getattr(project, "global_prompt", "") or "")
    fal_ok = bool(secret_status("fal_api_key").get("configured"))
    motion = bool(MOTION_RE.search(text))
    has_start = bool(getattr(scene, "start_asset_id", None))

    reasons: list[str] = []
    warnings: list[str] = []
    engine = profile.recommended_engine
    confidence = 0.55
    local = True

    if vram <= 8:
        engine = "minimax-h3"
        confidence = 0.75
        reasons.append(f"{vram} GB VRAM tier — MiniMax H3 is the Adept UI default (may require setup)")
        if duration > profile.max_duration_sec:
            warnings.append(
                f"Duration {duration:.1f}s exceeds {profile.max_duration_sec}s profile max — expect clamping"
            )
    elif vram <= 16:
        engine = "minimax-h3"
        confidence = 0.78
        reasons.append("16 GB class: MiniMax H3 is the Adept UI default video engine")
    else:
        if motion and duration >= 6:
            engine = "minimax-h3"
            confidence = 0.8
            reasons.append("Longer clip with motion — MiniMax H3 default (WAN remains selectable)")
        else:
            engine = "minimax-h3"
            confidence = 0.85
            reasons.append("24–32 GB: MiniMax H3 is the studio default video engine")

    if lipsync:
        reasons.append("Lip sync enabled — keep a local engine so LatentSync can follow")
        if is_fal_engine(engine):
            engine = "minimax-h3"
            local = True
            confidence = min(confidence, 0.6)
            warnings.append("Cloud engines skipped because lip sync is enabled")

    if not has_start and engine in ("ltx", "wan"):
        warnings.append(
            "Local LTX/WAN need a start frame — generate a local still first "
            "(do not silently route to fal)"
        )
        reasons.append("Local-first I2V chain: ImageGen still → LTX/WAN")

    # Soft cloud alternatives only — never auto-select fal for recommend/auto.
    if fal_ok and not lipsync:
        if motion and duration <= 10 and vram <= 16:
            warnings.append(
                "Optional paid fal.ai Kling available if local path is exhausted; "
                "requires explicit approval"
            )
        elif "cinematic" in text.lower() and duration <= 12:
            warnings.append(
                "Optional paid fal.ai Seedance/Veo available as cinematic cloud fallback; "
                "requires explicit approval"
            )

    mil_meta: dict[str, Any] = {}
    try:
        from .codirector.model_intelligence.compiler import normalize_audio_from_text
        from .codirector.model_intelligence.schemas import NormalizedGenerationIntent
        from .codirector.model_intelligence.selector import recommend as mil_recommend
        from .codirector.model_intelligence.registry import BINDINGS

        audio = normalize_audio_from_text(text)
        mil_intent = NormalizedGenerationIntent(
            userPrompt=text.strip(),
            mode="image_to_video" if has_start else "text_to_video",
            mediaType="video",
            hasSourceImage=has_start,
            durationSec=duration,
            audioIntent=audio,
        )
        mil = mil_recommend(
            mil_intent,
            provider_health={"fal.api": 0.9 if fal_ok else 0.2, "comfy.local": 0.95},
        )
        binding = BINDINGS.get(mil.recommendedModel)
        # Local-first: only accept MIL recommendations that stay on comfy.local.
        if (
            binding
            and binding.engineId
            and binding.capabilityIds
            and binding.providerId == "comfy.local"
            and not is_fal_engine(binding.engineId)
        ):
            engine = binding.engineId
            local = True
            confidence = max(confidence, float(mil.confidence))
            reasons.append(f"Model Intelligence recommends local {mil.recommendedModel}")
            mil_meta = {
                "modelId": mil.recommendedModel,
                "explanation": mil.explanation,
                "confidence": mil.confidence,
            }
        elif binding and binding.providerId == "fal.api" and fal_ok:
            warnings.append(
                f"Model Intelligence also scored {mil.recommendedModel} (fal) — "
                "not auto-applied; paid approval required"
            )
            mil_meta = {
                "modelId": mil.recommendedModel,
                "explanation": mil.explanation,
                "confidence": mil.confidence,
                "notApplied": "local_first_policy",
            }
    except Exception:
        mil_meta = {}

    # Hard guard: auto recommendation must never return fal.
    if is_fal_engine(engine):
        engine = "minimax-h3"
        local = True
        confidence = 0.7
        reasons.append(f"Local-first guard remapped auto away from fal → {engine}")

    out = {
        "engineId": engine,
        "confidence": round(confidence, 2),
        "reasons": reasons,
        "warnings": warnings,
        "local": local,
        "vram_tier": vram,
        "profile_engine": profile.recommended_engine,
        "requiresStartFrame": engine in ("ltx", "wan") and not has_start,
        "paidFallbackAvailable": fal_ok,
    }
    if mil_meta:
        out["modelIntelligence"] = mil_meta
    return out


def resolve_engine_id(engine: str | None, project: Any, scene: Any) -> str:
    """Resolve scene engine, expanding `auto` via recommend_engine (local-first)."""
    raw = (engine or getattr(scene, "engine", None) or "minimax-h3").strip().lower()
    if raw != "auto":
        return raw
    rec = recommend_engine(project=project, scene=scene)
    return str(rec["engineId"])
