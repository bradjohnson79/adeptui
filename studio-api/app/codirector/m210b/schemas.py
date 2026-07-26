"""Normalized request/result schemas for M2.10b sandbox audio generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypedDict


class TimelineIntent(TypedDict, total=False):
    startTimeSeconds: float
    trackRole: str
    syncEvent: str


@dataclass
class AudioGenerateRequest:
    capabilityId: str
    projectId: str
    sceneId: str | None = None
    prompt: str = ""
    durationSec: float = 2.0
    seed: int | None = None
    timelineIntent: dict[str, Any] | None = None
    providerKey: str | None = None
    registryId: str | None = None
    negativePrompt: str | None = None
    sampleRate: int = 48000
    channels: int = 1
    format: str = "wav"
    kind: str | None = None

    def resolved_registry_id(self) -> str | None:
        return self.registryId or self.providerKey


@dataclass
class AudioGenerateResult:
    assetPath: str
    sha256: str
    durationSec: float
    sampleRate: int
    sandboxOnly: bool = True
    provenance: dict[str, Any] = field(default_factory=dict)
    assetId: str | None = None
    providerId: str | None = None
    capabilityId: str | None = None
    prompt: str | None = None
    seed: int | None = None
    channels: int = 1
    format: str = "wav"
    fixture: bool = False
    productionApproved: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "assetPath": self.assetPath,
            "sha256": self.sha256,
            "durationSec": self.durationSec,
            "sampleRate": self.sampleRate,
            "sandboxOnly": self.sandboxOnly,
            "provenance": dict(self.provenance),
            "assetId": self.assetId,
            "providerId": self.providerId,
            "capabilityId": self.capabilityId,
            "prompt": self.prompt,
            "seed": self.seed,
            "channels": self.channels,
            "format": self.format,
            "fixture": self.fixture,
            "productionApproved": self.productionApproved,
        }
