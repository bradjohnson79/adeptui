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
    """Heuristic engine recommendation. User must confirm before apply."""
    vram = normalize_vram_tier(getattr(project, "vram_gb", 32))
    profile = get_profile(vram)
    duration = float(getattr(scene, "duration_sec", 5) or 5)
    lipsync = bool(getattr(scene, "lipsync_enabled", 0))
    text = (prompt or getattr(scene, "prompt", "") or "") + " " + (getattr(project, "global_prompt", "") or "")
    fal_ok = bool(secret_status("fal_api_key").get("configured"))
    motion = bool(MOTION_RE.search(text))

    reasons: list[str] = []
    warnings: list[str] = []
    engine = profile.recommended_engine
    confidence = 0.55
    local = True

    if vram <= 8:
        engine = "ltx"
        confidence = 0.8
        reasons.append(f"{vram} GB VRAM tier favors LTX with reduced budgets")
        if duration > profile.max_duration_sec:
            warnings.append(f"Duration {duration:.1f}s exceeds {profile.max_duration_sec}s profile max — expect clamping")
    elif vram <= 16:
        engine = "ltx"
        confidence = 0.7
        reasons.append("16 GB class: LTX is the safer local default")
    else:
        if motion and duration >= 6:
            engine = "wan"
            confidence = 0.62
            reasons.append("Longer clip with motion keywords — WAN local path")
        else:
            engine = "ltx"
            confidence = 0.68
            reasons.append("24–32 GB: LTX quality path is the studio default")

    if lipsync:
        reasons.append("Lip sync enabled — keep a local engine so LatentSync can follow")
        if is_fal_engine(engine):
            engine = "ltx"
            local = True
            confidence = min(confidence, 0.6)
            warnings.append("Cloud engines skipped because lip sync is enabled")

    if fal_ok and not lipsync and motion and duration <= 10 and vram <= 16:
        engine = "fal_kling"
        local = False
        confidence = 0.58
        reasons.append("fal.ai key present + motion on modest VRAM — Kling cloud suggested")
        warnings.append("Cloud render uses fal.ai credits; confirm before apply")
    elif fal_ok and not lipsync and "cinematic" in text.lower() and duration <= 12:
        # Soft cloud hint only when local is fine but cinematic asked
        if vram >= 24:
            reasons.append("fal.ai available for cinematic cloud alternatives (Seedance/Veo)")
        else:
            engine = "fal_seedance"
            local = False
            confidence = 0.52
            reasons.append("Cinematic brief + fal key — Seedance suggested")
            warnings.append("Confirm cloud engine before enqueue")

    if not fal_ok and engine.startswith("fal_"):
        engine = profile.recommended_engine
        local = True
        confidence = 0.65
        warnings.append("fal.ai key not configured — fell back to local")
        reasons.append(f"Local fallback: {engine}")

    return {
        "engineId": engine,
        "confidence": round(confidence, 2),
        "reasons": reasons,
        "warnings": warnings,
        "local": local,
        "vram_tier": vram,
        "profile_engine": profile.recommended_engine,
    }


def resolve_engine_id(engine: str | None, project: Any, scene: Any) -> str:
    """Resolve scene engine, expanding `auto` via recommend_engine."""
    raw = (engine or getattr(scene, "engine", None) or "ltx").strip().lower()
    if raw != "auto":
        return raw
    rec = recommend_engine(project=project, scene=scene)
    return str(rec["engineId"])
