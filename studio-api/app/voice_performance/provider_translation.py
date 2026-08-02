"""Translate NormalizedPerformancePlan → provider requests with honest support modes."""

from __future__ import annotations

from typing import Any

from .provider_capabilities import classify_feature, get_capability
from .schemas import PerformanceSegmentOut


def translate_plan(
    *,
    provider_key: str,
    voice: dict[str, Any] | None,
    segments: list[PerformanceSegmentOut],
) -> dict[str, Any]:
    cap = get_capability(provider_key)
    if not cap:
        return {
            "provider_key": provider_key,
            "voice_id": (voice or {}).get("id"),
            "segments": [],
            "unsupported_features": ["provider_not_registered"],
            "warnings": [f"Provider {provider_key} is not in the capability registry."],
            "adapter_version": "none",
            "mock": False,
        }
    out_segs = []
    unsupported: list[str] = []
    warnings: list[str] = []
    fallbacks: list[str] = []
    for seg in segments:
        modes: dict[str, str] = {}
        if seg.emotion:
            modes["emotion"] = classify_feature(provider_key, "emotion")
            if modes["emotion"] == "Prompt-guided":
                fallbacks.append(f"segment {seg.orderIndex}: emotion via prompt guidance")
            elif modes["emotion"] == "Unsupported":
                unsupported.append(f"emotion:{seg.emotion.get('primary')}")
        if seg.delivery:
            modes["delivery"] = classify_feature(provider_key, "delivery")
        if seg.pauseMs is not None or seg.segmentType in ("pause", "silence"):
            modes["pause"] = classify_feature(provider_key, "pause")
        if seg.reactionKey:
            modes["reaction"] = classify_feature(
                provider_key, "reaction", has_asset=bool(seg.outputAssetId)
            )
        if seg.pronunciationOverrides:
            modes["pronunciation"] = classify_feature(provider_key, "pronunciation")
        if seg.pace:
            modes["pace"] = classify_feature(provider_key, "pace")

        # Build prompt guidance text for speech
        guidance_parts = []
        if seg.emotion and modes.get("emotion") == "Prompt-guided":
            guidance_parts.append(f"emotion={seg.emotion.get('primary')}")
        if seg.delivery and modes.get("delivery") in ("Prompt-guided", "Translated"):
            guidance_parts.append(f"delivery={seg.delivery.get('style')}")
        if seg.pace and modes.get("pace") == "Prompt-guided":
            guidance_parts.append(f"pace={seg.pace}")

        text = seg.text or ""
        if guidance_parts and text:
            # Do not mutate stored source; only provider request carries guidance
            provider_text = text
        else:
            provider_text = text

        out_segs.append(
            {
                "segmentId": seg.id,
                "orderIndex": seg.orderIndex,
                "segmentType": seg.segmentType,
                "text": provider_text,
                "supportModes": modes,
                "guidance": guidance_parts,
                "pauseMs": seg.pauseMs,
                "reactionKey": seg.reactionKey,
                "outputAssetId": seg.outputAssetId,
                "overlapGroup": seg.overlapGroup,
                "interruptTarget": seg.interruptTarget,
            }
        )

    return {
        "provider_key": provider_key,
        "voice_id": (voice or {}).get("id"),
        "voice_mode": (voice or {}).get("source_mode"),
        "segments": out_segs,
        "provider_parameters": {
            "model_id": (voice or {}).get("model_id"),
            "max_text_length": cap.maximum_text_length,
        },
        "fallback_directives": fallbacks,
        "unsupported_features": unsupported,
        "warnings": warnings,
        "adapter_version": cap.adapter_version,
        "capability_version": cap.capability_version,
        "mock": False,
    }
