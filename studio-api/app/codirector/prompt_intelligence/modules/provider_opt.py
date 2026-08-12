"""Provider-specific optimization notes folded into English refinement."""

from __future__ import annotations

from ..models import GenerationDomain
from ..profiles import PromptProfile


def refine(prompt: str, profile: PromptProfile, domain: GenerationDomain) -> str:
    bits: list[str] = []
    notes = " ".join(profile.notes or []).lower()
    if profile.generationDomain == "video" and "realistic" not in (prompt or "").lower():
        if "ltx" in profile.profileId or "wan" in profile.profileId or "hunyuan" in profile.profileId:
            bits.append("photorealistic detail with coherent lighting")
    if profile.defaultStrategy.startswith("bilingual") or "chinese" in notes:
        # Do not inject Chinese here — language modules own that.
        bits.append("precise production language suitable for the selected model")
    if domain == "image" and "flux" in profile.profileId:
        bits.append("clean subject separation and material detail")
    return "; ".join(bits)
