"""Canonical ReferenceCapability registry — server source of truth."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .constants import REFERENCE_TYPES, USAGE_MODES


@dataclass(frozen=True)
class ReferenceCapability:
    workflow_key: str
    supported_types: frozenset[str]
    supported_modes: frozenset[str]
    max_count: int
    image_conditioning: bool
    identity_conditioning: bool
    frame_specific: bool
    negative_supported: bool
    prompt_fallback: bool
    capability_version: str
    support_class: str  # reference_conditioned | prompt_guided | unsupported

    def to_public(self) -> dict[str, Any]:
        d = asdict(self)
        d["supported_types"] = sorted(self.supported_types)
        d["supported_modes"] = sorted(self.supported_modes)
        return d


_ALL_TYPES = frozenset(REFERENCE_TYPES)
_COMMON_MODES = frozenset(USAGE_MODES)


CAPABILITY_REGISTRY: dict[str, ReferenceCapability] = {
    "text_to_video": ReferenceCapability(
        workflow_key="text_to_video",
        supported_types=_ALL_TYPES,
        supported_modes=_COMMON_MODES,
        max_count=6,
        image_conditioning=False,
        identity_conditioning=True,
        frame_specific=False,
        negative_supported=True,
        prompt_fallback=True,
        capability_version="w6p.1",
        support_class="prompt_guided",
    ),
    "one_frame": ReferenceCapability(
        workflow_key="one_frame",
        supported_types=_ALL_TYPES,
        supported_modes=_COMMON_MODES,
        max_count=8,
        image_conditioning=True,
        identity_conditioning=True,
        frame_specific=True,
        negative_supported=True,
        prompt_fallback=True,
        capability_version="w6p.1",
        support_class="reference_conditioned",
    ),
    "three_frame": ReferenceCapability(
        workflow_key="three_frame",
        supported_types=_ALL_TYPES,
        supported_modes=_COMMON_MODES,
        max_count=12,
        image_conditioning=True,
        identity_conditioning=True,
        frame_specific=True,
        negative_supported=True,
        prompt_fallback=True,
        capability_version="w6p.1",
        support_class="reference_conditioned",
    ),
    "timeline": ReferenceCapability(
        workflow_key="timeline",
        supported_types=_ALL_TYPES,
        supported_modes=_COMMON_MODES,
        max_count=10,
        image_conditioning=True,
        identity_conditioning=True,
        frame_specific=False,
        negative_supported=True,
        prompt_fallback=True,
        capability_version="w6p.1",
        support_class="reference_conditioned",
    ),
    "storyboard": ReferenceCapability(
        workflow_key="storyboard",
        supported_types=_ALL_TYPES,
        supported_modes=_COMMON_MODES,
        max_count=6,
        image_conditioning=True,
        identity_conditioning=True,
        frame_specific=False,
        negative_supported=False,
        prompt_fallback=True,
        capability_version="w6p.1",
        support_class="reference_conditioned",
    ),
}


def get_capability(workflow_key: str) -> ReferenceCapability | None:
    return CAPABILITY_REGISTRY.get(workflow_key)


def list_capabilities() -> list[dict[str, Any]]:
    return [c.to_public() for c in CAPABILITY_REGISTRY.values()]


def support_status_for(workflow_key: str) -> str:
    cap = get_capability(workflow_key)
    if not cap:
        return "unsupported"
    return cap.support_class
