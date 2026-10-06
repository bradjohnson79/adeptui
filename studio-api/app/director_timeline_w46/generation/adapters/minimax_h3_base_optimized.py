"""MiniMax H3 Base Optimized — the same Ref2Video path, turbo LoRA, fewer steps.

Standard MiniMax H3 — Local is a different adapter and stays on 20 steps
with no turbo LoRA.
"""

from __future__ import annotations

from ..contracts import (
    NormalizedJobSubmission,
    TimelineGenerationRequest,
    VideoGeneratorCapabilities,
)
from .comfy_render_scene import submit_render_scene
from .minimax_h3_i2v_local import ENGINE, MiniMaxH3I2VLocalAdapter

GENERATOR_ID = "minimax-h3-base-optimized"
ALIASES = frozenset({GENERATOR_ID})


def _capabilities() -> VideoGeneratorCapabilities:
    base = MiniMaxH3I2VLocalAdapter.capabilities
    return base.model_copy(
        update={
            "id": GENERATOR_ID,
            "label": "MiniMax H3 Base Optimized",
            "supportsTextToVideo": False,
            "supportsImageToVideo": False,
            "supportsStartFrame": False,
            "supportsEndFrame": False,
            "supportsReferenceToVideo": True,
            "notes": (
                "MiniMax H3 Base Optimized. Reference to video only, using the "
                "same character, place, and prop pictures as MiniMax H3 — Local, "
                "with a faster step count. Text to Video, Start Frame, and "
                "Start + End Frame are not modes of this model."
            ),
        }
    )


class MiniMaxH3BaseOptimizedAdapter(MiniMaxH3I2VLocalAdapter):
    id = GENERATOR_ID
    capabilities = _capabilities()

    def submit(self, request: TimelineGenerationRequest) -> NormalizedJobSubmission:
        validation = self.validate(request)
        if not validation.ok:
            raise ValueError("; ".join(validation.errors) or "MiniMax H3 Base Optimized validation failed.")
        from .minimax_h3_local import apply_h3_speech_authority_honesty

        apply_h3_speech_authority_honesty(request)
        return submit_render_scene(
            request,
            engine=ENGINE,
            generator_id=GENERATOR_ID,
            queue_message="Timeline batch MiniMax H3 Base Optimized queued",
        )
