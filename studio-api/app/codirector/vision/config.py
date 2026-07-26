"""Configurable weights and score thresholds for M2.5 vision validation."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class VisionWeights:
    identity: float = 30.0
    continuity: float = 25.0
    technical: float = 20.0
    lighting: float = 10.0
    camera: float = 5.0
    composition: float = 5.0
    color: float = 5.0
    motion: float = 10.0  # applied for video profiles only

    def as_dict(self, *, include_motion: bool = False) -> dict[str, float]:
        base = {
            "identity": self.identity,
            "continuity": self.continuity,
            "technical": self.technical,
            "lighting": self.lighting,
            "camera": self.camera,
            "composition": self.composition,
            "color": self.color,
        }
        if include_motion:
            base["motion"] = self.motion
        return base


@dataclass(frozen=True)
class VisionThresholds:
    """Bands: >=approve, review, corrections_required, reject below corrections."""

    approve: float = 95.0
    review: float = 90.0
    corrections_required: float = 80.0


@dataclass(frozen=True)
class VisionConfig:
    weights: VisionWeights = field(default_factory=VisionWeights)
    thresholds: VisionThresholds = field(default_factory=VisionThresholds)
    default_provider: str = "local"
    blocking_validators: tuple[str, ...] = ("technical", "identity")


DEFAULT_VISION_CONFIG = VisionConfig()
