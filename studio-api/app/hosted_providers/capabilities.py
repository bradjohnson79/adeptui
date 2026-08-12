"""Honest capability matrix per hosted provider — marketing claims are not certification."""

from __future__ import annotations

from typing import Any, Literal

CapabilityStatus = Literal["Certified", "Testing", "Available but Uncertified", "Unsupported"]

CAPABILITY_KEYS = (
    "text_to_image",
    "image_to_image",
    "image_editing",
    "multi_reference_generation",
    "character_consistency",
    "environment_references",
    "props",
    "identity_conditioning",
    "one_frame_workflows",
    "three_frame_workflows",
    "text_to_video",
    "image_to_video",
    "video_enhancement",
    "music",
    "voice",
    "audio",
    "inpainting",
    "outpainting",
    "upscaling",
    "background_removal",
    "relighting",
)

# Status reflects Adept UI certified execution paths — not vendor marketing pages.
_MATRIX: dict[str, dict[str, CapabilityStatus]] = {
    "kie": {
        "text_to_image": "Testing",
        "image_to_image": "Testing",
        "image_editing": "Available but Uncertified",
        "multi_reference_generation": "Testing",
        "character_consistency": "Testing",
        "environment_references": "Testing",
        "props": "Available but Uncertified",
        "identity_conditioning": "Testing",
        "one_frame_workflows": "Testing",
        "three_frame_workflows": "Available but Uncertified",
        "text_to_video": "Testing",
        "image_to_video": "Testing",
        "video_enhancement": "Unsupported",
        "music": "Available but Uncertified",
        "voice": "Available but Uncertified",
        "audio": "Available but Uncertified",
        "inpainting": "Available but Uncertified",
        "outpainting": "Available but Uncertified",
        "upscaling": "Available but Uncertified",
        "background_removal": "Available but Uncertified",
        "relighting": "Unsupported",
    },
    "wavespeed": {
        "text_to_image": "Testing",
        "image_to_image": "Testing",
        "image_editing": "Available but Uncertified",
        "multi_reference_generation": "Available but Uncertified",
        "character_consistency": "Available but Uncertified",
        "environment_references": "Available but Uncertified",
        "props": "Available but Uncertified",
        "identity_conditioning": "Available but Uncertified",
        "one_frame_workflows": "Available but Uncertified",
        "three_frame_workflows": "Unsupported",
        "text_to_video": "Testing",
        "image_to_video": "Testing",
        "video_enhancement": "Unsupported",
        "music": "Unsupported",
        "voice": "Unsupported",
        "audio": "Unsupported",
        "inpainting": "Available but Uncertified",
        "outpainting": "Available but Uncertified",
        "upscaling": "Available but Uncertified",
        "background_removal": "Available but Uncertified",
        "relighting": "Unsupported",
    },
    # fal: existing Adept queue adapters certify video engines; image inventory is not yet executable.
    "fal": {
        "text_to_image": "Available but Uncertified",
        "image_to_image": "Available but Uncertified",
        "image_editing": "Available but Uncertified",
        "multi_reference_generation": "Available but Uncertified",
        "character_consistency": "Available but Uncertified",
        "environment_references": "Available but Uncertified",
        "props": "Unsupported",
        "identity_conditioning": "Available but Uncertified",
        "one_frame_workflows": "Available but Uncertified",
        "three_frame_workflows": "Unsupported",
        "text_to_video": "Certified",
        "image_to_video": "Certified",
        "video_enhancement": "Available but Uncertified",
        "music": "Unsupported",
        "voice": "Unsupported",
        "audio": "Unsupported",
        "inpainting": "Unsupported",
        "outpainting": "Unsupported",
        "upscaling": "Available but Uncertified",
        "background_removal": "Unsupported",
        "relighting": "Unsupported",
    },
}


def capability_matrix() -> dict[str, Any]:
    return {
        "version": "m42.hosted.capabilities.1",
        "capabilities": list(CAPABILITY_KEYS),
        "providers": {pid: dict(caps) for pid, caps in _MATRIX.items()},
        "legend": {
            "Certified": "Adept UI certified execution path exists and is production-gated.",
            "Testing": "Adapter and credential path exist; workflow certification incomplete.",
            "Available but Uncertified": "Provider may offer the modality; Adept UI has not certified it.",
            "Unsupported": "Not available through this Adept UI hosted adapter.",
        },
        "mock": False,
    }


def provider_supports(provider_id: str, capability: str, *, min_status: CapabilityStatus = "Testing") -> bool:
    """True when provider can satisfy capability at or above min_status for Automatic resolution."""
    order = ["Unsupported", "Available but Uncertified", "Testing", "Certified"]
    caps = _MATRIX.get((provider_id or "").lower()) or {}
    status = caps.get(capability, "Unsupported")
    try:
        return order.index(status) >= order.index(min_status)
    except ValueError:
        return False


def executable_capabilities(provider_id: str) -> list[str]:
    """Capabilities considered runnable for Automatic recommendation (Certified or Testing)."""
    caps = _MATRIX.get((provider_id or "").lower()) or {}
    return [k for k, v in caps.items() if v in ("Certified", "Testing")]
