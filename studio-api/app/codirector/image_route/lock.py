"""Parse UNLOCKED / PREFERRED / STRICT from the current utterance only."""

from __future__ import annotations

import re

from .contracts import RouteLock

_STRICT_RE = re.compile(
    r"(?:"
    r"\bdo(?:\s+not|n't)\s+(?:use\s+anything\s+else|switch)\b|"
    r"\bnothing\s+else\b|"
    r"\bonly\s+(?:use|with|via)\b|"
    r"\b(?:use|with|via)\b.{0,48}\bonly\b|"
    r"\bonly\b.{0,48}\b(?:use|with|via)\b"
    r")",
    re.I,
)
_AUTO_RE = re.compile(r"\b(?:use\s+auto(?:matic)?|automatically)\b", re.I)
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
        "only",
        "same",
        "and",
        "or",
        "plus",
        "with",
        "via",
        "using",
        "by",
        # Atmosphere / quality words must never become requestedModelId.
        "fallback",
        "nofallback",
        "denser",
        "fog",
        "cinematic",
        "warmer",
        "cooler",
        "practicals",
        "corridor",
        "venture",
    }
)

# Generators accepted after bare "with …" (not free English noun phrases).
_KNOWN_GENERATOR_TOKENS = frozenset(
    {
        "flux",
        "fluxlocal",
        "fluxfal",
        "qwen",
        "qwen2512",
        "gptimage2",
        "gptimage2kie",
        "imagen",
        "illustrious",
        "zimage",
        "fal",
        "falai",
        "kie",
        "wavespeed",
    }
)
_PROVIDER_TOKENS = {
    "fal": "fal",
    "falai": "fal",
    "hosted": "fal",
    "api": "fal",
    "kie": "kie",
    "kieai": "kie",
    "wavespeed": "wavespeed",
    "local": "local",
}


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _extract_named_token(blob: str) -> str:
    if _GPT_IMAGE_RE.search(blob or ""):
        return "gptimage2"
    try:
        from ..project_grounding import route_parse_surface

        blob = route_parse_surface(blob)
    except Exception:
        pass
    match = _USE_NAME_RE.search(blob or "")
    if not match:
        return ""
    verb = (match.group(0).split()[0] if match.group(0) else "").lower()
    parts: list[str] = []
    for word in re.split(r"\s+", match.group(1).strip()):
        cleaned = re.sub(r"^[^\w]+|[^\w]+$", "", word).lower()
        if cleaned in _NAME_STOP:
            if parts:
                break
            return ""
        parts.append(cleaned)
    token = _norm(" ".join(parts))
    if len(token) < 3 or token in _NAME_STOP:
        return ""
    # "No fallback" / denser fog must never lock as a model id.
    if token in {"fallback", "nofallback"} or "fallback" in token:
        return ""
    # Bare "with <english phrase>" is content, not a route lock — only known generators.
    if verb == "with" and token not in _KNOWN_GENERATOR_TOKENS and not token.startswith("gptimage"):
        return ""
    return token


def parse_route_lock(text: str) -> RouteLock:
    """Lock comes from the current utterance. Retry lines only, not chat history."""

    blob = text or ""
    named = _extract_named_token(blob)
    hosted = bool(_HOSTED_RE.search(blob) or _FAL_BARE_RE.search(blob))
    auto = bool(_AUTO_RE.search(blob))
    strict = bool(_STRICT_RE.search(blob))
    provider = ""
    model_id = ""
    named_is_provider = named in _PROVIDER_TOKENS or named.startswith("fal")
    if named and not named_is_provider:
        model_id = "gptimage2" if named in {"gptimage2", "gptimage2kie"} else named
        # Keep a co-named hosted API. fal.ai + GPT Image 2 is a composed route,
        # not "drop fal and fail-forward as GPT Image 2 only."
        if hosted:
            provider = "fal"
    elif named_is_provider:
        provider = _PROVIDER_TOKENS.get(named, "fal")
    elif hosted:
        provider = "fal"

    restated = bool(strict or named or hosted or auto)
    if strict:
        level: str = "STRICT"
    elif named or hosted:
        level = "PREFERRED"
    else:
        level = "UNLOCKED"

    scope = ""
    if level in {"PREFERRED", "STRICT"}:
        if model_id:
            scope = "model"
        elif provider:
            scope = "provider"

    return RouteLock(
        level=level,  # type: ignore[arg-type]
        scope=scope,  # type: ignore[arg-type]
        requested_provider=provider,
        requested_model_id=model_id,
        restated=restated,
    )


def creator_route_label(name: str) -> str:
    token = _norm(name)
    labels = {
        "gptimage2": "GPT Image 2",
        "gptimage2kie": "GPT Image 2",
        "fal": "fal.ai",
        "falai": "fal.ai",
        "hosted": "that hosted image API",
        "api": "that image API",
        "kie": "Kie.ai",
        "wavespeed": "WaveSpeed",
        "flux": "Flux",
        "fluxlocal": "Flux Local",
        "fluxfal": "Flux on fal.ai",
        "qwen": "Qwen",
        "qwen2512": "Qwen",
    }
    if token in labels:
        return labels[token]
    cleaned = re.sub(r"[-_]+", " ", (name or "").strip())
    return cleaned or "That image generator"
