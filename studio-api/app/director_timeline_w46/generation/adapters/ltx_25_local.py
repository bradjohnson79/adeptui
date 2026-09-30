"""LTX 2.5 Timeline/CREATE adapter — does not bind ltx-local (2.3)."""

from __future__ import annotations

from .ltx_local import LtxLocalAdapter, _capabilities
from ..contracts import VideoGeneratorCapabilities

GENERATOR_ID = "ltx-2.5-distilled"
ALIASES = frozenset(
    {
        "ltx-2.5-distilled",
        "ltx-2.5-full",
        "ltx-2.5-comfy",
        "ltx-2.5",
    }
)


def _ltx25_capabilities() -> VideoGeneratorCapabilities:
    base = _capabilities()
    return base.model_copy(
        update={
            "id": GENERATOR_ID,
            "label": "LTX 2.5",
            # Timeline stays R2V. CREATE T2V comes from workflowCapabilities.t2v, not this flag.
            "supportsTextToVideo": False,
            "supportedDurations": [float(s) for s in range(4, 21, 2)],
            "maxDurationSec": 20.0,
            "supportedResolutions": ["832x480", "1280x704", "1920x1088", "2560x1440", "480x832", "704x1248", "1088x1920", "1440x2560"],
            "draftResolution": "832x480",
            "finalResolution": "1280x704",
            "qualityControl": "ltx_quality",
            "notes": (
                "Local LTX 2.5. Timeline is one-cond Reference-to-Video via ltx_25.i2v — "
                "not LTX 2.3 Ingredients. CREATE Text to Video uses a separate ltx_25.t2v workflow. "
                "720p class is 1280×704. Adept will not silent-snap 1280×720."
            ),
        }
    )


class Ltx25LocalAdapter(LtxLocalAdapter):
    id = GENERATOR_ID
    capabilities = _ltx25_capabilities()
