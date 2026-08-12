"""Capability snapshot helpers for the MiniMax H3 surface."""

from __future__ import annotations

from typing import Any

from .contracts import H3Deployment
from .private_access import (
    best_match_enabled,
    general_routing_enabled,
    private_local_enabled,
    public_creator_enabled,
)

# Community License excluded territories. Unknown territory fails closed.
EXCLUDED_TERRITORY_SENTINELS = frozenset({"US", "USA", "EU", "GB", "UK", "KR", "KOR"})
EU_MEMBER_ALPHA2 = frozenset(
    {
        "AT",
        "BE",
        "BG",
        "HR",
        "CY",
        "CZ",
        "DK",
        "EE",
        "FI",
        "FR",
        "DE",
        "GR",
        "HU",
        "IE",
        "IT",
        "LV",
        "LT",
        "LU",
        "MT",
        "NL",
        "PL",
        "PT",
        "RO",
        "SK",
        "SI",
        "ES",
        "SE",
    }
)


def is_excluded_territory(territory_code: str) -> bool:
    code = str(territory_code or "").strip().upper()
    if not code:
        return True
    return code in EXCLUDED_TERRITORY_SENTINELS or code in EU_MEMBER_ALPHA2


def capability_snapshot(*, territory: str, deployment: H3Deployment) -> dict[str, Any]:
    excluded = is_excluded_territory(territory)
    private_active = private_local_enabled() and not public_creator_enabled()
    if deployment == "local_weights":
        if private_active:
            # Private owner-only Route A: T2VA + one-frame I2VA. Three Frame /
            # PoseCraft / ERS remain unsupported so creators are never misled.
            capability = "Testing"
            status = "ready"
            notes = [
                "MiniMax H3 is available for private local use on the Experimental Private Profile "
                "(text-to-video and one-frame image-to-video with native audio).",
                "Timeline Re-take is supported for text-to-video continuity variations (Private Local / Route A only).",
                "Three Frame, PoseCraft, and ERS are not supported on this profile yet.",
                "Three-frame requests are assembled as two guided passes rather than one native three-keyframe run.",
            ]
            if excluded:
                # Private owner access is territory-agnostic (local owner machine);
                # the community-license territory block does not apply to the
                # private owner path, but we still disclose it for honesty.
                notes.append("Community-license territory limits do not apply to private owner use.")
            return {
                "modelId": "minimax-h3",
                "label": "MiniMax H3",
                "deployment": deployment,
                "territory": str(territory or "").strip().upper(),
                "capability": capability,
                "status": status,
                "territoryAllowed": True,
                "privateLocal": True,
                "ownerOnly": True,
                "experimental": True,
                "creatorEnabled": public_creator_enabled(),
                "bestMatchEnabled": best_match_enabled(),
                "automaticRoutingEnabled": general_routing_enabled(),
                "threeFrameNative": False,
                "threeFrameStrategyDefault": "segmented-a",
                "supports2k": False,
                "supportsStartEndFrame": False,
                "supportsStartFrame": True,
                "supportsTextToVideo": True,
                "supportsNativeAudio": True,
                "supportsImageToVideo": True,
                "supportsRetake": True,
                "supportsPoseCraft": False,
                "supportsErs": False,
                "permanentFallback": "ltx",
                "approvalRequired": False,
                "executable": True,
                "profile": "Experimental Private Profile",
                "notes": notes,
            }
        capability = "Unavailable" if excluded else "Requires Setup"
        status = "blocked" if excluded else "setup_required"
        notes = [
            "Local MiniMax H3 remains disabled in this build until license and runtime certification are complete.",
            "Three-frame requests are assembled as two guided passes rather than one native three-keyframe run.",
        ]
        if excluded:
            notes.insert(0, "Local MiniMax H3 weights are not licensed for this territory.")
    else:
        capability = "Available"
        status = "approval_required"
        notes = [
            "Hosted MiniMax H3 may be prepared on this surface, but each generation requires explicit creator approval.",
            "Three-frame requests are assembled as two guided passes rather than one native three-keyframe run.",
        ]
    return {
        "modelId": "minimax-h3",
        "label": "MiniMax H3",
        "deployment": deployment,
        "territory": str(territory or "").strip().upper(),
        "capability": capability,
        "status": status,
        "territoryAllowed": not excluded if deployment == "local_weights" else True,
        "privateLocal": private_active,
        "ownerOnly": private_active,
        "experimental": private_active,
        "creatorEnabled": public_creator_enabled(),
        "bestMatchEnabled": best_match_enabled(),
        "automaticRoutingEnabled": general_routing_enabled(),
        "threeFrameNative": False,
        "threeFrameStrategyDefault": "segmented-a",
        "supports2k": False if deployment == "local_weights" else None,
        "supportsStartEndFrame": True if deployment == "api" else False,
        "supportsTextToVideo": True,
        "supportsNativeAudio": True,
        "supportsImageToVideo": deployment == "api",
        "permanentFallback": "ltx",
        "approvalRequired": deployment == "api",
        "executable": False,
        "notes": notes,
    }


def capability_matrix(territory: str) -> dict[str, Any]:
    return {
        "territory": str(territory or "").strip().upper(),
        "local": capability_snapshot(territory=territory, deployment="local_weights"),
        "api": capability_snapshot(territory=territory, deployment="api"),
    }
