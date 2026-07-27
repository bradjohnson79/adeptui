"""Canonical modelId ↔ engine/provider/capability bindings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .loader import active_packs, discover_packs
from .schemas import PackStatus, ProductionReadiness


@dataclass(frozen=True)
class ModelBinding:
    modelId: str
    engineId: str
    providerId: str
    capabilityIds: tuple[str, ...]
    mediaType: str


# Bound to existing platform identities — not a parallel registry.
BINDINGS: dict[str, ModelBinding] = {
    "z_image": ModelBinding(
        "z_image", "zimage", "comfy.local", ("generation.image.queue",), "image"
    ),
    "ltx_2_3": ModelBinding(
        "ltx_2_3", "ltx", "comfy.local", ("generation.video.queue",), "video"
    ),
    "wan_2_2": ModelBinding(
        "wan_2_2", "wan", "comfy.local", ("generation.video.queue",), "video"
    ),
    "fal_seedance": ModelBinding(
        "fal_seedance", "fal_seedance", "fal.api", ("generation.video.queue",), "video"
    ),
    "fal_kling": ModelBinding(
        "fal_kling", "fal_kling", "fal.api", ("generation.video.queue",), "video"
    ),
    "fal_veo": ModelBinding(
        "fal_veo", "fal_veo", "fal.api", ("generation.video.queue",), "video"
    ),
    "fal_runway": ModelBinding(
        "fal_runway", "fal_runway", "fal.api", ("generation.video.queue",), "video"
    ),
    "seedream": ModelBinding(
        "seedream", "seedream", "fal.api", (), "image"
    ),
    "nano_banana_pro": ModelBinding(
        "nano_banana_pro", "nano_banana_pro", "fal.api", (), "image"
    ),
    "gpt_image_fal": ModelBinding(
        "gpt_image_fal", "gpt_image_fal", "fal.api", (), "image"
    ),
}

ENGINE_TO_MODEL: dict[str, str] = {
    b.engineId: b.modelId for b in BINDINGS.values() if b.engineId
}
ENGINE_TO_MODEL["auto"] = "fal_seedance"  # default motion preference when MIL scores


def binding_for_model(model_id: str) -> Optional[ModelBinding]:
    return BINDINGS.get(model_id)


def binding_for_engine(engine_id: str) -> Optional[ModelBinding]:
    mid = ENGINE_TO_MODEL.get(engine_id)
    return BINDINGS.get(mid) if mid else None


def list_registry_rows() -> list[dict]:
    packs = discover_packs()
    rows = []
    for mid, binding in BINDINGS.items():
        pack = packs.get(mid)
        manifest = pack["manifest"] if pack else None
        rows.append(
            {
                "modelId": mid,
                "engineId": binding.engineId,
                "providerId": binding.providerId,
                "mediaType": binding.mediaType,
                "capabilityIds": list(binding.capabilityIds),
                "packStatus": manifest.status.value if manifest else PackStatus.DRAFT.value,
                "runtimeStatus": (
                    manifest.runtimeStatus.value
                    if manifest
                    else ProductionReadiness.UNAVAILABLE.value
                ),
                "knowledgePackVersion": manifest.knowledgePackVersion if manifest else None,
                "modelVersion": manifest.modelVersion if manifest else None,
                "hasPack": pack is not None,
                "influencesProduction": bool(
                    pack
                    and manifest
                    and manifest.status in (PackStatus.ACTIVE, PackStatus.VERIFIED)
                    and manifest.status != PackStatus.QUARANTINED
                    and binding.capabilityIds
                ),
            }
        )
    return rows


def production_model_ids() -> list[str]:
    return [mid for mid, pack in active_packs().items() if BINDINGS.get(mid)]
