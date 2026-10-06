"""Canonical Co-Director still-image generation defaults.

If the creator asks for an image and does not specify settings, execute
immediately: AUTO (local-first), 16:9, 1920×1080. Explicit current
instructions, then established conversation choices, then project
preference, then these defaults. Not a second preference store.

Generator inventory lives in Production Control. This module only owns
request defaults and parsing of creator-named settings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any

DEFAULT_ROUTE = "AUTO"
DEFAULT_ASPECT = "16:9"
DEFAULT_WIDTH = 1920
DEFAULT_HEIGHT = 1080

LOCAL_UNAVAILABLE_ASK = (
    "No compatible local image generator is currently available. I can use fal.ai instead—proceed?"
)

_ASPECT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b21\s*[:x×]\s*9\b", re.I), "21:9"),
    (re.compile(r"\b16\s*[:x×]\s*9\b", re.I), "16:9"),
    (re.compile(r"\b9\s*[:x×]\s*16\b", re.I), "9:16"),
    (re.compile(r"\b4\s*[:x×]\s*3\b", re.I), "4:3"),
    (re.compile(r"\b3\s*[:x×]\s*2\b", re.I), "3:2"),
    (re.compile(r"\b1\s*[:x×]\s*1\b", re.I), "1:1"),
    (re.compile(r"\bsquare(?:\s+image)?\b", re.I), "1:1"),
    (re.compile(r"\bportrait(?:\s+(?:9\s*[:x×]\s*16|image))?\b", re.I), "9:16"),
)

_RES_RE = re.compile(r"\b(\d{3,5})\s*[x×]\s*(\d{3,5})\b", re.I)

_HOSTED_RE = re.compile(
    r"\b(?:use|with|via|on)\s+(?:fal(?:\.ai)?|hosted(?:\s+(?:api|generation))?|(?:the\s+)?api)\b",
    re.I,
)
_FAL_BARE_RE = re.compile(r"\bfal\.ai\b", re.I)
_GPT_IMAGE_RE = re.compile(r"\bgpt[\s-]*image[\s-]*2\b", re.I)

_USE_NAME_RE = re.compile(
    r"\b(?:use|with|via)\s+([A-Za-z][\w.\-]{1,40}(?:\s+[A-Za-z][\w.\-]{1,20}){0,3})",
    re.I,
)

_NAME_STOP = frozenset(
    {
        "the",
        "this",
        "that",
        "a",
        "an",
        "my",
        "our",
        "these",
        "those",
        "it",
        "image",
        "images",
        "shot",
        "shots",
        "frame",
        "camera",
        "style",
        "prompt",
        "model",
        "generator",
        "local",
        "hosted",
        "api",
        "for",
        "from",
        "at",
        "on",
        "in",
        "to",
        "as",
        "please",
        "now",
        "and",
        "or",
        "plus",
        "with",
        "via",
        "using",
        "by",
    }
)

_ASPECT_PIXELS: dict[str, tuple[int, int]] = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "21:9": (1920, 824),
    "4:3": (1440, 1080),
    "3:2": (1620, 1080),
    "1:1": (1080, 1080),
}


@dataclass(frozen=True)
class ImageGenerationProfile:
    route: str = DEFAULT_ROUTE
    local_first: bool = True
    provider_kind: str = "local"
    explicit_provider: str = ""
    aspect_ratio: str = DEFAULT_ASPECT
    width: int = DEFAULT_WIDTH
    height: int = DEFAULT_HEIGHT
    source: str = "default"
    clarification_count: int = 0

    @property
    def is_hosted(self) -> bool:
        return self.provider_kind in {"fal", "hosted", "api"}

    def acknowledgement(self) -> str:
        if self.is_hosted:
            return f"Got it — generating that with fal.ai at {self.aspect_ratio} now."
        return f"Got it — generating that locally at {self.aspect_ratio} now."


def pixels_for_aspect(aspect: str) -> tuple[int, int]:
    return _ASPECT_PIXELS.get((aspect or "").strip() or DEFAULT_ASPECT, (DEFAULT_WIDTH, DEFAULT_HEIGHT))


def _aspect_from_pixels(width: int, height: int) -> str:
    if width <= 0 or height <= 0:
        return DEFAULT_ASPECT
    ratio = width / height
    best = DEFAULT_ASPECT
    best_err = 99.0
    for key, (w, h) in _ASPECT_PIXELS.items():
        err = abs(ratio - (w / h))
        if err < best_err:
            best_err = err
            best = key
    return best


def normalize_explicit_generator_name(name: str) -> str:
    """Strip filler words. Does not map names to families — Production Control does that."""

    cleaned = re.sub(r"\s+local\s*$", "", (name or "").strip(), flags=re.I)
    token = re.sub(r"[^a-z0-9]+", "", cleaned.lower()).removesuffix("local")
    return token


def _extract_explicit_generator_name(blob: str) -> str:
    try:
        from ...project_grounding import route_parse_surface

        blob = route_parse_surface(blob)
    except Exception:
        pass
    match = _USE_NAME_RE.search(blob or "")
    if not match:
        return ""
    raw = match.group(1).strip()
    parts: list[str] = []
    for word in re.split(r"\s+", raw):
        if word.lower() in _NAME_STOP:
            if parts:
                break
            return ""
        parts.append(word)
    raw = " ".join(parts)
    token = normalize_explicit_generator_name(raw)
    if len(token) < 3 or token in _NAME_STOP:
        return ""
    return token


def parse_image_generation_overrides(text: str) -> dict[str, Any]:
    """Return only settings the text actually named."""

    blob = text or ""
    found: dict[str, Any] = {}
    res = _RES_RE.search(blob)
    if res:
        found["width"] = int(res.group(1))
        found["height"] = int(res.group(2))
        found["aspect_ratio"] = _aspect_from_pixels(found["width"], found["height"])
    for pattern, aspect in _ASPECT_PATTERNS:
        if pattern.search(blob):
            found["aspect_ratio"] = aspect
            if "width" not in found:
                found["width"], found["height"] = pixels_for_aspect(aspect)
            break
    if _GPT_IMAGE_RE.search(blob):
        found["explicit_provider"] = "gptimage2"
        found["route"] = "explicit"
    elif _HOSTED_RE.search(blob) or _FAL_BARE_RE.search(blob):
        found["provider_kind"] = "fal"
        found["explicit_provider"] = "fal"
        found["route"] = "explicit"
        found["local_first"] = False
    elif name := _extract_explicit_generator_name(blob):
        found["explicit_provider"] = name
        found["provider_kind"] = "local"
        found["route"] = "explicit"
        found["local_first"] = True
    return found


def _apply(profile: ImageGenerationProfile, overrides: dict[str, Any], *, source: str) -> ImageGenerationProfile:
    if not overrides:
        return profile
    data = {k: v for k, v in overrides.items() if v is not None}
    data["source"] = source
    return replace(profile, **data)


def _message_role_content(item: object) -> tuple[str, str]:
    if isinstance(item, dict):
        return str(item.get("role") or ""), str(item.get("content") or "")
    return str(getattr(item, "role", "") or ""), str(getattr(item, "content", "") or "")


def resolve_image_generation_profile(
    user_message: str,
    recent_messages: list[object] | None = None,
) -> ImageGenerationProfile:
    """Precedence: current instruction → conversation choice → defaults."""

    profile = ImageGenerationProfile()
    for item in recent_messages or []:
        role, content = _message_role_content(item)
        if role != "user" or not (content or "").strip():
            continue
        profile = _apply(profile, parse_image_generation_overrides(content), source="conversation")
    current = parse_image_generation_overrides(user_message)
    profile = _apply(profile, current, source="current" if current else profile.source)
    if "width" not in current and "height" not in current:
        w, h = pixels_for_aspect(profile.aspect_ratio)
        profile = replace(profile, width=w, height=h)
    return profile
