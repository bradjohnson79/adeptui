"""Deterministic referential language. No embeddings. No project-specific hints."""

from __future__ import annotations

import re

_REFERENTIAL_RE = re.compile(
    r"\b(?:"
    r"same prompt|same description|same one|same setup|"
    r"do that again|retry that|regenerate that|"
    r"another version|another one|same thing|"
    r"version of (?:that|this|it)|"
    r"(?:video|image|audio|sfx|sound)\s+version|"
    r"run that again|use the previous prompt|"
    r"retry with (?:the )?same|same prompt again|"
    r"regenerate the previous|use the prompt|"
    r"retry(?:\s+(?:that|the|this))?(?:\s+(?:image|video|audio|shot))?"
    r"|do the exact same thing|exact same (?:thing|prompt|one)|"
    r"same (?:visual )?reference|that same (?:visual )?reference|"
    r"use that (?:same )?(?:visual )?reference|same attached|"
    r"use the (?:last|previous|latest)\s+(?:\w+\s+){0,3}prompt"
    r")\b",
    re.I,
)

_LAST_IMAGE_RE = re.compile(r"\b(?:last|previous|latest)\s+(?:\w+\s+){0,3}image\b", re.I)
_LAST_VIDEO_RE = re.compile(r"\b(?:last|previous|latest)\s+(?:\w+\s+){0,3}video\b", re.I)
_LAST_AUDIO_RE = re.compile(
    r"\b(?:last|previous|latest)\s+(?:\w+\s+){0,2}(?:audio|sfx|sound(?:\s+effect)?|footsteps?|music|ambience)\b",
    re.I,
)
_IMAGE_GENERATOR_RE = re.compile(
    r"\b(?:flux|qwen|z-?image|gpt[\s-]*image|imagen|illustrious)\b",
    re.I,
)
_IMAGE_INDEX_RE = re.compile(r"\bimage\s+(\d+)\b", re.I)
_GPT_IMAGE_MODEL_RE = re.compile(r"\bgpt[\s-]*image[\s-]*\d+\b", re.I)
_GENERATOR_OR_ASPECT_RESTATE_RE = re.compile(
    r"^(?:please\s+)?(?:"
    r"(?:use|try|switch to|go with|make it)\s+"
    r"(?:flux|qwen|z-?image|gpt[\s-]*image(?:\s*\d+)?|imagen|illustrious|fal(?:\.ai)?)"
    r"(?:\s+(?:this\s+time|instead|now|local|again))?"
    r"|"
    r"(?:make it|use|set(?:\s+it)?\s+to)\s+\d+\s*[:x×]\s*\d+"
    r")[.!]?\s*$",
    re.I,
)

_NAVIGATE_SURFACE_RE = re.compile(
    r"\b(?:open|show|switch to|take me to|go to|bring up|launch)\b.+\b"
    r"(?:audio studio|voice creator|character creator|spatial map|timeline|script writer)\b",
    re.I,
)

_STOP = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "for",
        "this",
        "that",
        "these",
        "those",
        "last",
        "previous",
        "latest",
        "retry",
        "same",
        "prompt",
        "again",
        "use",
        "with",
        "from",
        "make",
        "another",
        "version",
        "short",
        "long",
        "tiny",
        "full",
        "wide",
        "cinematic",
        "image",
        "video",
        "audio",
        "shot",
        "please",
        "create",
        "time",
        "instead",
        "now",
        "switch",
        "try",
        "again",
        "generate",
        "do",
        "it",
        "one",
        "only",
        "but",
        "flux",
        "qwen",
        "fal",
        "gpt",
        "kie",
        "local",
        "hosted",
        "auto",
    }
)


def names_excluded_surface(user_message: str) -> bool:
    """True only for an explicit navigate speech act — not production recall."""
    return bool(_NAVIGATE_SURFACE_RE.search(user_message or ""))


_VIDEO_VERSION_RE = re.compile(
    r"\b(?:make|create|generate|do)\s+(?:a\s+)?(?:short\s+)?video\b"
    r"|\bvideo\s+version\b",
    re.I,
)
_AUDIO_VERSION_RE = re.compile(
    r"\b(?:audio|sfx|sound(?:\s+effect)?|footsteps?|music|ambience)\s+version\b",
    re.I,
)
_IMAGE_VERSION_RE = re.compile(r"\bimage\s+version\b", re.I)


def requested_artifact_type(user_message: str) -> str:
    text = user_message or ""
    if _LAST_VIDEO_RE.search(text):
        return "video"
    if _LAST_AUDIO_RE.search(text):
        return "audio"
    if _LAST_IMAGE_RE.search(text):
        return "image"
    if _GENERATOR_OR_ASPECT_RESTATE_RE.search(text.strip()):
        return "image"
    if _IMAGE_GENERATOR_RE.search(text) and not _VIDEO_VERSION_RE.search(text):
        return "image"
    return ""


def target_artifact_type(user_message: str) -> str:
    """What the creator wants made. Distinct from the referent being reused."""

    text = user_message or ""
    if _VIDEO_VERSION_RE.search(text):
        return "video"
    if _AUDIO_VERSION_RE.search(text):
        return "audio"
    if _IMAGE_VERSION_RE.search(text):
        return "image"
    return requested_artifact_type(text)


def source_artifact_type(user_message: str) -> str:
    """Which stored production object 'that' / last X refers to."""

    explicit = requested_artifact_type(user_message)
    if explicit:
        return explicit
    target = target_artifact_type(user_message)
    if target == "video":
        return "image"
    return ""


def is_referential_generation(user_message: str) -> bool:
    text = (user_message or "").strip()
    if not text or names_excluded_surface(text):
        return False
    return bool(
        _REFERENTIAL_RE.search(text)
        or _LAST_IMAGE_RE.search(text)
        or _LAST_VIDEO_RE.search(text)
        or _LAST_AUDIO_RE.search(text)
        or _GENERATOR_OR_ASPECT_RESTATE_RE.search(text)
    )


def wants_last_image(user_message: str) -> bool:
    return requested_artifact_type(user_message) == "image"


def image_index_hint(user_message: str) -> int | None:
    text = _GPT_IMAGE_MODEL_RE.sub(" ", user_message or "")
    match = _IMAGE_INDEX_RE.search(text)
    if not match:
        return None
    return int(match.group(1))


def named_hints(user_message: str) -> list[str]:
    """Content words from the utterance. Never a hardcoded project/scene list."""
    text = user_message or ""
    if _GENERATOR_OR_ASPECT_RESTATE_RE.search(text.strip()):
        return []
    out: list[str] = []
    for word in re.findall(r"[A-Za-z][A-Za-z0-9'-]{2,}", text):
        key = word.lower()
        if key in _STOP or key.isdigit():
            continue
        if key not in out:
            out.append(key)
    return out
