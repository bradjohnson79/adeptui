"""LTX 2.5 Timeline/CREATE adapter — does not bind ltx-local (2.3)."""

from __future__ import annotations

from .ltx_local import LtxLocalAdapter, _capabilities
from ..contracts import VideoGeneratorCapabilities

GENERATOR_ID = "ltx-2.5-distilled"


def normalize_ltx_mode(value: str | None) -> str:
    """Map stored and legacy labels onto text, one_frame, start_end, or three_frame.

    three_frame stays a distinct token so it can fail closed. It is not
    treated as Start + End Frame.
    """

    raw = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return {
        "": "text",
        "text": "text",
        "text_to_video": "text",
        "t2v": "text",
        "one_frame": "one_frame",
        "start_frame": "one_frame",
        "1_frame": "one_frame",
        "1frame": "one_frame",
        "start_end": "start_end",
        "start_end_frame": "start_end",
        "start_and_end_frame": "start_end",
        "first_last": "start_end",
        "three_frame": "three_frame",
        "3_frame": "three_frame",
        "3frame": "three_frame",
    }.get(raw, "text")
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
            "supportsTextToVideo": True,
            "supportsReferenceToVideo": False,
            "supportsMultipleImageReferences": False,
            "supportsEndFrame": True,
            "supportsThreeFrame": False,
            "maximumReferenceImages": 0,
            "supportedDurations": [float(s) for s in range(4, 21, 2)],
            "maxDurationSec": 20.0,
            "supportedResolutions": ["832x480", "1280x704", "1920x1088", "2560x1440", "480x832", "704x1248", "1088x1920", "1440x2560"],
            "draftResolution": "832x480",
            "finalResolution": "1280x704",
            "qualityControl": "ltx_quality",
            "continuationMode": "hard",
            "notes": (
                "Local LTX 2.5. Text to Video uses ltx_25.t2v. "
                "Start Frame writes one image with LTXVImgToVideoInplace. "
                "Start + End Frame uses LTXVAddGuide at frame 0 and frame -1, then LTXVCropGuides. "
                "Three-frame guidance is not a Timeline mode. "
                "Character, place, and prop references are not generation inputs. "
                "720p class is 1280×704."
            ),
        }
    )


class Ltx25LocalAdapter(LtxLocalAdapter):
    id = GENERATOR_ID
    capabilities = _ltx25_capabilities()

    def validate(self, request):
        from ..contracts import ValidationResult

        opts = request.providerOptions or {}
        mode = normalize_ltx_mode(str(opts.get("ltxMode") or ""))
        if mode == "three_frame":
            return ValidationResult(
                ok=False,
                errors=[
                    "LTX_THREE_FRAME_UNSUPPORTED: LTX 2.5 on Timeline does not take a third frame. "
                    "Use Text to Video, Start Frame, or Start + End Frame."
                ],
            )
        if mode == "start_end":
            if not str(request.startImageAssetId or "").strip():
                return ValidationResult(
                    ok=False,
                    errors=["LTX_START_FRAME_REQUIRED: Choose a start picture for this LTX shot."],
                )
            if not str(request.endImageAssetId or "").strip():
                return ValidationResult(
                    ok=False,
                    errors=["LTX_END_FRAME_REQUIRED: Choose an end picture for this LTX shot."],
                )
        elif request.generationMode != "text_to_video" and not str(request.startImageAssetId or "").strip():
            return ValidationResult(
                ok=False,
                errors=["LTX_START_FRAME_REQUIRED: Choose a start picture for this LTX shot."],
            )
        return super().validate(request)
