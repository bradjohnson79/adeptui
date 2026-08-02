"""Closed, versioned performance tag registry — unknown tags never silently affect runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

REGISTRY_VERSION = 1

EMOTIONS = [
    "neutral",
    "amused",
    "playful",
    "sarcastic",
    "annoyed",
    "defiant",
    "angry",
    "concerned",
    "protective",
    "vulnerable",
    "sincere",
    "excited",
    "afraid",
    "sad",
    "relieved",
]

REACTIONS = [
    "laugh",
    "scoff",
    "sigh",
    "gasp",
    "grunt",
    "breath",
    "sob",
    "whisper",
    "shout",
    "effort",
    "disgust",
    "surprise",
    "silence",
    "custom",
    "amused_scoff",
    "sarcastic_scoff",
]


@dataclass(frozen=True)
class PerformanceTagDefinition:
    key: str
    category: str
    value_type: str
    allowed_values: Optional[tuple[str, ...]] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    unit: Optional[str] = None
    nesting_allowed: bool = False
    provider_support_required: bool = False
    prompt_fallback_allowed: bool = True
    description: str = ""
    schema_version: int = REGISTRY_VERSION


_TAGS: tuple[PerformanceTagDefinition, ...] = (
    PerformanceTagDefinition(
        "emotion", "emotion", "enum", allowed_values=tuple(EMOTIONS), description="Primary emotional state"
    ),
    PerformanceTagDefinition(
        "delivery", "delivery", "string", description="Delivery quality chips (dry, teasing, soft, …)"
    ),
    PerformanceTagDefinition(
        "pause", "timing", "duration_ms", minimum=0, maximum=30_000, unit="ms", description="Measurable break"
    ),
    PerformanceTagDefinition(
        "beat", "timing", "string", description="Dramatic beat (realization, hesitation, …)"
    ),
    PerformanceTagDefinition(
        "silence", "timing", "duration_ms", minimum=0, maximum=60_000, unit="ms", description="Explicit silence"
    ),
    PerformanceTagDefinition(
        "reaction", "reaction", "enum", allowed_values=tuple(REACTIONS), description="Character reaction"
    ),
    PerformanceTagDefinition("pronunciation", "pronunciation", "string", description="Per-line pronunciation override"),
    PerformanceTagDefinition("emphasis", "delivery", "string", description="Emphasized word or phrase"),
    PerformanceTagDefinition(
        "pace", "delivery", "string", description="fast | moderate | slow | numeric rate"
    ),
    PerformanceTagDefinition("volume", "delivery", "string", description="soft | normal | loud | numeric"),
    PerformanceTagDefinition("pitch", "delivery", "string", description="Pitch direction where supported"),
    PerformanceTagDefinition("breath", "delivery", "string", description="Breath type"),
    PerformanceTagDefinition("whisper", "delivery", "flag", description="Whispered delivery"),
    PerformanceTagDefinition("shout", "delivery", "flag", description="Shouted delivery"),
    PerformanceTagDefinition("interrupt", "interaction", "string", description="Interrupts target speaker"),
    PerformanceTagDefinition("interrupts", "interaction", "string", description="Alias of interrupt"),
    PerformanceTagDefinition("overlap", "interaction", "string", description="Overlap group / target speaker"),
    PerformanceTagDefinition("cut_off", "interaction", "flag", description="Line cut off mid-phrase"),
    PerformanceTagDefinition("resume", "interaction", "flag", description="Resume after interrupt"),
    PerformanceTagDefinition("timing", "timing", "string", description="Timing note"),
    PerformanceTagDefinition(
        "relationship_tone", "relationship", "string", description="Relationship-informed tone hint"
    ),
)

# Unsafe / injection-prone keys — always rejected
BLOCKED_KEYS = frozenset(
    {
        "provider_instruction",
        "bypass",
        "consent",
        "system",
        "exec",
        "eval",
        "raw_provider",
        "api_key",
    }
)


def all_definitions() -> list[PerformanceTagDefinition]:
    return list(_TAGS)


def get_definition(key: str) -> PerformanceTagDefinition | None:
    k = (key or "").strip().lower()
    for t in _TAGS:
        if t.key == k:
            return t
    return None


def is_blocked_key(key: str) -> bool:
    k = (key or "").strip().lower()
    if k in BLOCKED_KEYS:
        return True
    return any(b in k for b in ("bypass", "api_key", "provider_instruction"))


def registry_snapshot() -> dict[str, Any]:
    return {
        "schemaVersion": REGISTRY_VERSION,
        "tags": [
            {
                "key": t.key,
                "category": t.category,
                "valueType": t.value_type,
                "allowedValues": list(t.allowed_values) if t.allowed_values else None,
                "promptFallbackAllowed": t.prompt_fallback_allowed,
                "description": t.description,
            }
            for t in _TAGS
        ],
        "blockedKeys": sorted(BLOCKED_KEYS),
        "mock": False,
    }
