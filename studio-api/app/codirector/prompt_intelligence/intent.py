"""Stage A — structured prompt intent (no chain-of-thought)."""

from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, Field

from .models import GenerationDomain


class PromptIntent(BaseModel):
    subject: str = ""
    action: str = ""
    setting: str = ""
    camera: str = ""
    composition: str = ""
    lighting: str = ""
    motion: str = ""
    performance: str = ""
    emotion: str = ""
    style: str = ""
    continuity: str = ""
    duration: str = ""
    audioIntent: str = ""
    negativeConstraints: list[str] = Field(default_factory=list)

    def summary(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for key, value in self.model_dump().items():
            if key == "negativeConstraints":
                if value:
                    out[key] = "; ".join(value)
                continue
            if isinstance(value, str) and value.strip():
                out[key] = value.strip()
        return out


_CAMERA = re.compile(
    r"\b(wide shot|medium shot|close[- ]?up|extreme close[- ]?up|tracking|dolly|pan|tilt|crane|steadicam|pov|aerial|over[- ]the[- ]shoulder|otS)\b",
    re.I,
)
_LIGHT = re.compile(
    r"\b(soft light|hard light|rim light|backlit|golden hour|blue hour|neon|volumetric|cinematic lighting|low key|high key|moonlight|sunset|dawn)\b",
    re.I,
)
_MOTION = re.compile(
    r"\b(walks?|runs?|turns?|looks?|reaches?|drifts?|flows?|moves?|camera (moves?|pushes?|pulls?)|slow motion|handheld)\b",
    re.I,
)
_EMOTION = re.compile(
    r"\b(calm|tense|joyful|melancholy|fear|anger|hope|restrained|anxious|warm|cold|intimate|lonely)\b",
    re.I,
)
_AUDIO = re.compile(
    r"\b(ambient|ambience|sfx|foley|music|score|drone|whisper|breath|footsteps|wind|rain|reverb|decay)\b",
    re.I,
)


def analyze_intent(
    prompt: str,
    *,
    domain: GenerationDomain = "video",
    continuity_hints: Optional[list[str]] = None,
    negative_prompt: Optional[str] = None,
) -> PromptIntent:
    text = (prompt or "").strip()
    intent = PromptIntent()
    if not text:
        return intent

    # Subject: first clause / sentence lead
    lead = re.split(r"[.,;\n]", text, maxsplit=1)[0].strip()
    intent.subject = lead[:160]
    intent.action = lead[:160] if _MOTION.search(lead) else ""
    intent.setting = text[:220]

    cam = _CAMERA.search(text)
    if cam:
        intent.camera = cam.group(0)
    light = _LIGHT.search(text)
    if light:
        intent.lighting = light.group(0)
    motion = _MOTION.search(text)
    if motion:
        intent.motion = motion.group(0)
    emotion = _EMOTION.search(text)
    if emotion:
        intent.emotion = emotion.group(0)
        intent.performance = emotion.group(0)

    if domain in ("audio", "music", "sfx", "voice") or _AUDIO.search(text):
        audio = _AUDIO.search(text)
        intent.audioIntent = audio.group(0) if audio else ("voice performance" if domain == "voice" else domain)

    if continuity_hints:
        intent.continuity = "; ".join(h for h in continuity_hints if h)[:240]

    # Style cue: words after "style" / "in the style of"
    style_m = re.search(r"(?:in the style of|style[:\s]+)([^\n.]{3,80})", text, re.I)
    if style_m:
        intent.style = style_m.group(1).strip()

    negs: list[str] = []
    if negative_prompt:
        negs.extend(p.strip() for p in re.split(r"[,;\n]", negative_prompt) if p.strip())
    for m in re.finditer(r"\bno\s+([a-z0-9 \-]{2,40})", text, re.I):
        negs.append(f"no {m.group(1).strip()}")
    intent.negativeConstraints = list(dict.fromkeys(negs))[:20]
    return intent
