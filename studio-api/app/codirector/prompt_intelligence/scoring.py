"""Prompt Quality Analyzer — deterministic heuristics + recommendations."""

from __future__ import annotations

from .intent import PromptIntent
from .models import GenerationDomain, PromptQualityRecommendation, PromptQualityReport
from .profiles import PromptProfile


def _clamp(score: int) -> int:
    return max(0, min(100, int(score)))


def analyze_quality(
    prompt: str,
    intent: PromptIntent,
    *,
    domain: GenerationDomain,
    profile: PromptProfile,
    modules_enabled_zh: bool = False,
) -> PromptQualityReport:
    text = (prompt or "").strip()
    words = len(text.split())
    dims: dict[str, int] = {}
    recs: list[PromptQualityRecommendation] = []

    # Subject clarity
    subject = 55
    if intent.subject:
        subject += 25
    if words >= 8:
        subject += 10
    if words >= 20:
        subject += 8
    dims["subjectClarity"] = _clamp(subject)
    if dims["subjectClarity"] < 75:
        recs.append(
            PromptQualityRecommendation(
                code="SUBJECT_WEAK",
                message="Clarify the primary subject and action in the first clause.",
                suggestedModule="production",
                severity="suggest",
            )
        )

    # Camera
    camera = 40 if domain in ("image", "video") else 80
    if intent.camera:
        camera = 92
    elif domain in ("image", "video"):
        recs.append(
            PromptQualityRecommendation(
                code="CAMERA_MISSING",
                message="Add shot size or camera language (e.g. wide shot, slow push-in).",
                suggestedModule="cinematic",
                severity="suggest",
            )
        )
        camera = 55
    dims["cameraLanguage"] = _clamp(camera)

    # Motion
    motion = 45 if domain == "video" else (85 if domain == "image" else 70)
    if intent.motion or domain != "video":
        motion = 90 if intent.motion else motion
    elif domain == "video":
        recs.append(
            PromptQualityRecommendation(
                code="MOTION_THIN",
                message="Describe subject or camera motion for stronger temporal coherence.",
                suggestedModule="motion",
                severity="important",
            )
        )
    dims["motionDescription"] = _clamp(motion)

    # Lighting
    lighting = 50 if domain in ("image", "video") else 80
    if intent.lighting:
        lighting = 93
    elif domain in ("image", "video"):
        recs.append(
            PromptQualityRecommendation(
                code="LIGHTING_THIN",
                message="Add lighting or atmosphere cues (soft key, golden hour, rim light).",
                suggestedModule="cinematic",
                severity="info",
            )
        )
        lighting = 60
    dims["lightingDetail"] = _clamp(lighting)

    # Character continuity
    continuity = 70
    if intent.continuity:
        continuity = 100
    elif intent.subject and any(ch.isupper() for ch in intent.subject):
        continuity = 88
    dims["characterConsistency"] = _clamp(continuity)
    if continuity < 80 and domain in ("image", "video", "voice"):
        recs.append(
            PromptQualityRecommendation(
                code="CONTINUITY_HINT",
                message="Bind character identity / continuity terms from the Production Bible when available.",
                suggestedModule="continuity",
                severity="info",
            )
        )

    # Provider optimization
    provider = 70
    if profile.certificationStatus in ("supported", "experimental", "certified"):
        provider += 15
    if profile.bilingualCertified and modules_enabled_zh:
        provider += 10
    elif "zh" in (profile.recommendedLanguageModules or []) and not modules_enabled_zh:
        provider -= 8
        recs.append(
            PromptQualityRecommendation(
                code="BILINGUAL_RECOMMENDED",
                message=(
                    f"{profile.profileId} @{profile.profileVersion} recommends "
                    f"{(profile.recommendedBalance or 'balanced')} Chinese enhancement — not auto-enabled."
                ),
                suggestedModule="language.zh",
                severity="info",
            )
        )
    dims["providerOptimization"] = _clamp(provider)

    if domain in ("audio", "music", "sfx", "voice"):
        audio = 60
        if intent.audioIntent:
            audio = 90
        else:
            recs.append(
                PromptQualityRecommendation(
                    code="AUDIO_INTENT_THIN",
                    message="Specify source character, texture, space, or emotional tone for audio.",
                    suggestedModule="audio",
                    severity="suggest",
                )
            )
        dims["audioFidelity"] = _clamp(audio)

    overall = _clamp(round(sum(dims.values()) / max(1, len(dims))))
    return PromptQualityReport(overall=overall, dimensions=dims, recommendations=recs)
