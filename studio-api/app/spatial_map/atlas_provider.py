"""Atlas-capability resolver.

Atlas creation is a specialized capability. Ordinary still-image preference
must not silently become the Atlas provider.
"""

from __future__ import annotations

from typing import Any

GPT_HOSTED_ID = "gpt-image-2-kie"
GPT_T2I_ID = "gpt-image-2-text-to-image"
GPT_I2I_ID = "gpt-image-2-image-to-image"

ATLAS_UNAVAILABLE = (
    "GPT Image 2 is required for Spatial Map generation. "
    "Configure GPT Image 2 in your API settings to continue."
)


def _blob(*values: Any) -> str:
    return " ".join(str(v) for v in values if v).lower()


def gpt_image2_requested(*values: Any) -> bool:
    blob = _blob(*values)
    return "gpt-image-2" in blob or "gpt_image_2" in blob


def gpt_image2_configured(db: Any = None) -> bool:
    """True when a Kie key exists so GPT Image 2 can be offered."""
    try:
        from ..secrets_store import get_secret

        key = (get_secret("KIE_API_KEY") or get_secret("kie_api_key") or "").strip()
        if key:
            return True
    except Exception:
        pass
    try:
        import os

        if (os.environ.get("KIE_API_KEY") or "").strip():
            return True
    except Exception:
        pass
    return False


def resolve_atlas_design_provider(
    *,
    explicit: str = "",
    stored_preference: str = "",
    style_reference: bool = False,
    configured: bool | None = None,
) -> dict[str, Any]:
    """Resolve the Atlas designer/renderer for a designed environment.

    Order: explicit Atlas provider → stored Atlas preference → recommended
    certified provider (GPT Image 2 when configured). No silent Qwen or
    Z-Image substitute on the design route.
    """
    requested = _blob(explicit, stored_preference)
    if requested and not gpt_image2_requested(requested):
        return {
            "ok": False,
            "code": "ATLAS_PROVIDER_NOT_CERTIFIED",
            "message": (
                "That image engine is not certified for Atlas design. "
                "Use GPT Image 2."
            ),
            "requested": requested,
        }
    ready = gpt_image2_configured() if configured is None else bool(configured)
    if not ready:
        return {
            "ok": False,
            "code": "GPT_IMAGE_2_NOT_CONFIGURED",
            "message": ATLAS_UNAVAILABLE,
            "hostedModelId": "",
            "officialModelId": "",
        }
    official = GPT_I2I_ID if style_reference else GPT_T2I_ID
    return {
        "ok": True,
        "code": "GPT_IMAGE_2",
        "hostedModelId": GPT_HOSTED_ID,
        "officialModelId": official,
        "recommended": True,
        "paidApi": True,
        "styleReference": style_reference,
    }


LOCAL_ATLAS_UNAVAILABLE = (
    "Local Atlas design is deferred. Use GPT Image 2 to create a Spatial Map."
)

# Retired camera-reconstruction graphs must never be selected.
RETIRED_LOCAL_ATLAS_KEYS = frozenset({"qwen2512.atlas", "qwen2512.atlas_direct"})

# Historical Local Atlas keys. Deferred / not production-certified. Never selected.
LOCAL_ATLAS_CANDIDATES: tuple[dict[str, Any], ...] = ()


def resolve_local_atlas_design_provider(
    *,
    style_reference: bool = False,
    require_ready: bool = True,
    explicit: str = "",
) -> dict[str, Any]:
    """Local Atlas design is deferred. Production never selects these keys."""
    requested = _blob(explicit)
    if requested and (gpt_image2_requested(requested) or requested.startswith("gpt")):
        return {
            "ok": False,
            "code": "LOCAL_ATLAS_NO_GPT",
            "message": "Local Atlas design cannot use GPT Image 2. Use GPT Image 2 on the API Spatial Map path.",
        }
    return {
        "ok": False,
        "code": "LOCAL_ATLAS_NOT_PRODUCTION_CERTIFIED",
        "message": LOCAL_ATLAS_UNAVAILABLE,
        "requested": requested,
        "hostedModelId": "",
        "officialModelId": "",
        "workflowKey": "",
        "certified": False,
    }
