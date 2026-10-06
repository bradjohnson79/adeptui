"""Split license facts for Setup components.

One string is not enough. Code license, weights license, license status, and
owner policy stay independent. Essential describes architectural role, not
whether weights are downloadable today.
"""

from __future__ import annotations

from typing import Any, Literal

LicenseStatus = Literal[
    "PUBLISHED_LICENSE_CONFIRMED",
    "LICENSE_PENDING_CLARIFICATION",
    "OWNER_PERMITTED_LICENSE_PENDING_CLARIFICATION",
    "TERMS_RESTRICTED",
    "LICENSE_BLOCKED",
    "REQUIRES_EXTERNAL_ACCEPTANCE",
    "MODEL_ACCESS_GATED",
]

OwnerPolicy = Literal["PERMITTED", "NOT_PERMITTED"]
ProductClass = Literal["ESSENTIAL", "RECOMMENDED", "OPTIONAL", "PERIPHERAL"]

LICENSE_STATUSES: tuple[str, ...] = (
    "PUBLISHED_LICENSE_CONFIRMED",
    "LICENSE_PENDING_CLARIFICATION",
    "OWNER_PERMITTED_LICENSE_PENDING_CLARIFICATION",
    "TERMS_RESTRICTED",
    "LICENSE_BLOCKED",
    "REQUIRES_EXTERNAL_ACCEPTANCE",
    "MODEL_ACCESS_GATED",
)

# Peripheral families that must never be silently promoted to Essential.
PERIPHERAL_COMPONENT_IDS: frozenset[str] = frozenset(
    {
        "comfyui",
        "qwen_image_2512_models",
        "qwen_image_edit_2509_models",
        "flux1_dev_local",
        "flux1_schnell_local",
        "flux1_kontext_dev_local",
        "instantx_flux_controlnet_union",
        "vjepa2_world_intelligence",
    }
)

_ROWS: dict[str, dict[str, Any]] = {
    "moge2_geometry": {
        "component_id": "moge2_geometry",
        "display": "MoGe-2 Geometry Reconstruction",
        "role": "Single-image environment geometry reconstruction",
        "product_class": "ESSENTIAL",
        "publisher": "Microsoft Research / MoGe authors",
        "source": "GitHub microsoft/MoGe first; official Hugging Face weights only when install is authorized",
        "code_source": "https://github.com/microsoft/MoGe",
        "model_source": "",
        "code_license": "MIT (DINOv2 subtree Apache-2.0)",
        "weights_license": "unconfirmed",
        "license_status": "OWNER_PERMITTED_LICENSE_PENDING_CLARIFICATION",
        "license_status_secondary": "",
        "owner_policy": "PERMITTED",
        "notes": (
            "Adept permits MoGe-2 under owner policy. Weight terms are pending "
            "official clarification. Do not label MoGe weights MIT or Apache-2.0."
        ),
    },
    "vggt_1b_commercial": {
        "component_id": "vggt_1b_commercial",
        "display": "VGGT-1B Commercial Geometry Reconstruction",
        "role": "Standard multi-view environment geometry reconstruction",
        "product_class": "ESSENTIAL",
        "publisher": "Meta",
        "source": "Official GitHub facebookresearch/vggt; production weights facebook/VGGT-1B-Commercial only",
        "code_source": "https://github.com/facebookresearch/vggt",
        "model_source": "facebook/VGGT-1B-Commercial",
        "code_license": "VGGT License (Meta research materials)",
        "weights_license": "VGGT License / commercial model card — external acceptance required",
        "license_status": "MODEL_ACCESS_GATED",
        "license_status_secondary": "REQUIRES_EXTERNAL_ACCEPTANCE",
        "owner_policy": "PERMITTED",
        "notes": (
            "Essential for multi-view geometry reconstruction. Gated access "
            "does not make it peripheral. Clone is not Ready. Never use facebook/VGGT-1B."
        ),
    },
    "videochat3_4b": {
        "component_id": "videochat3_4b",
        "display": "VideoChat3 4B",
        "role": "Co-Director Timeline visual review",
        "product_class": "ESSENTIAL",
        "publisher": "OpenGVLab",
        "source": "Hugging Face snapshot",
        "code_source": "",
        "model_source": "",
        "code_license": "",
        "weights_license": "",
        "license_status": "PUBLISHED_LICENSE_CONFIRMED",
        "license_status_secondary": "",
        "owner_policy": "PERMITTED",
        "notes": "",
    },
    "sam21_hiera_tiny": {
        "component_id": "sam21_hiera_tiny",
        "display": "SAM 2.1 Tiny",
        "role": "Intelligent selection masks",
        "product_class": "ESSENTIAL",
        "publisher": "Meta",
        "source": "Hugging Face snapshot",
        "code_source": "",
        "model_source": "",
        "code_license": "",
        "weights_license": "",
        "license_status": "PUBLISHED_LICENSE_CONFIRMED",
        "license_status_secondary": "",
        "owner_policy": "PERMITTED",
        "notes": "",
    },
    "grounding_dino_tiny": {
        "component_id": "grounding_dino_tiny",
        "display": "Grounding DINO Tiny",
        "role": "Intelligent selection boxes",
        "product_class": "ESSENTIAL",
        "publisher": "IDEA-Research",
        "source": "Hugging Face snapshot",
        "code_source": "",
        "model_source": "",
        "code_license": "",
        "weights_license": "",
        "license_status": "PUBLISHED_LICENSE_CONFIRMED",
        "license_status_secondary": "",
        "owner_policy": "PERMITTED",
        "notes": "",
    },
    "comfyui": {
        "component_id": "comfyui",
        "display": "ComfyUI",
        "role": "Local node graph runtime",
        "product_class": "PERIPHERAL",
        "publisher": "Comfy-Org / comfyanonymous",
        "source": "Local service",
        "code_source": "https://github.com/comfyanonymous/ComfyUI",
        "model_source": "",
        "code_license": "GPL-3.0",
        "weights_license": "",
        "license_status": "PUBLISHED_LICENSE_CONFIRMED",
        "license_status_secondary": "",
        "owner_policy": "PERMITTED",
        "notes": "Peripheral runtime. Not an Essential.",
    },
    "qwen_image_2512_models": {
        "component_id": "qwen_image_2512_models",
        "display": "Qwen Image",
        "role": "Still image generation",
        "product_class": "PERIPHERAL",
        "publisher": "Qwen / Alibaba",
        "source": "Comfy / Hugging Face",
        "code_source": "",
        "model_source": "",
        "code_license": "",
        "weights_license": "Apache-2.0 family where published",
        "license_status": "PUBLISHED_LICENSE_CONFIRMED",
        "license_status_secondary": "",
        "owner_policy": "PERMITTED",
        "notes": "Peripheral. Not an Essential.",
    },
    "qwen_image_edit_2509_models": {
        "component_id": "qwen_image_edit_2509_models",
        "display": "Qwen Image Edit",
        "role": "Reference image edit",
        "product_class": "PERIPHERAL",
        "publisher": "Qwen / Alibaba",
        "source": "Comfy / Hugging Face",
        "code_source": "",
        "model_source": "",
        "code_license": "",
        "weights_license": "Apache-2.0 family where published",
        "license_status": "PUBLISHED_LICENSE_CONFIRMED",
        "license_status_secondary": "",
        "owner_policy": "PERMITTED",
        "notes": "Peripheral. Not an Essential. Not an environment atlas camera.",
    },
    "flux1_dev_local": {
        "component_id": "flux1_dev_local",
        "display": "FLUX.1 Dev",
        "role": "Local still generation",
        "product_class": "PERIPHERAL",
        "publisher": "Black Forest Labs",
        "source": "Local / Hugging Face",
        "code_source": "",
        "model_source": "",
        "code_license": "",
        "weights_license": "FLUX.1-dev non-commercial / source-specific",
        "license_status": "TERMS_RESTRICTED",
        "license_status_secondary": "",
        "owner_policy": "PERMITTED",
        "notes": (
            "Peripheral. Not an Essential. R&D / local qualification only. "
            "Not Apache-2.0. Not approved for Adept redistribution or hosted commercial use."
        ),
    },
    "instantx_flux_controlnet_union": {
        "component_id": "instantx_flux_controlnet_union",
        "display": "InstantX FLUX.1-dev ControlNet Union",
        "role": "Local R&D structural control for FLUX.1-dev Atlas qualification",
        "product_class": "PERIPHERAL",
        "publisher": "InstantX",
        "source": "https://huggingface.co/InstantX/FLUX.1-dev-Controlnet-Union",
        "code_source": "",
        "model_source": "InstantX/FLUX.1-dev-Controlnet-Union",
        "code_license": "",
        "weights_license": "flux-1-dev-non-commercial-license (inherits FLUX.1-dev)",
        "license_status": "TERMS_RESTRICTED",
        "license_status_secondary": "MODEL_ACCESS_GATED",
        "owner_policy": "PERMITTED",
        "notes": (
            "R&D / local qualification only. Compatible with FLUX.1-dev, not Kontext. "
            "Not Apache-2.0. Not approved for Adept redistribution. "
            "Adept may later support user-supplied gated weights."
        ),
    },
    "vjepa2_world_intelligence": {
        "component_id": "vjepa2_world_intelligence",
        "display": "Co-Director World Intelligence",
        "role": "Advisory same-world check",
        "product_class": "RECOMMENDED",
        "publisher": "Meta",
        "source": "Hugging Face snapshot",
        "code_source": "",
        "model_source": "",
        "code_license": "",
        "weights_license": "",
        "license_status": "PUBLISHED_LICENSE_CONFIRMED",
        "license_status_secondary": "",
        "owner_policy": "PERMITTED",
        "notes": "Recommended, not Essential. Does not generate environment geometry.",
    },
}


def license_row(component_id: str) -> dict[str, Any]:
    row = _ROWS.get(component_id)
    if row:
        return dict(row)
    return {
        "component_id": component_id,
        "display": component_id,
        "role": "",
        "product_class": "PERIPHERAL" if component_id in PERIPHERAL_COMPONENT_IDS else "OPTIONAL",
        "publisher": "",
        "source": "",
        "code_source": "",
        "model_source": "",
        "code_license": "",
        "weights_license": "",
        "license_status": "LICENSE_PENDING_CLARIFICATION",
        "license_status_secondary": "",
        "owner_policy": "PERMITTED",
        "notes": "",
    }


def inspect_split_license(component_id: str) -> dict[str, Any]:
    row = license_row(component_id)
    return {
        "componentId": component_id,
        "code_license": row.get("code_license") or "",
        "weights_license": row.get("weights_license") or "",
        "license_status": row.get("license_status") or "",
        "license_status_secondary": row.get("license_status_secondary") or "",
        "owner_policy": row.get("owner_policy") or "",
        "product_class": row.get("product_class") or "",
        "publisher": row.get("publisher") or "",
        "source": row.get("source") or "",
        "code_source": row.get("code_source") or "",
        "model_source": row.get("model_source") or "",
        "notes": row.get("notes") or "",
        # Legacy single string — never the only field.
        "license": _legacy_license_string(row),
    }


def _legacy_license_string(row: dict[str, Any]) -> str:
    parts = [
        str(row.get("code_license") or "").strip(),
        str(row.get("weights_license") or "").strip(),
        str(row.get("license_status") or "").strip(),
    ]
    return " | ".join(part for part in parts if part)


def is_peripheral(component_id: str) -> bool:
    if component_id in PERIPHERAL_COMPONENT_IDS:
        return True
    return license_row(component_id).get("product_class") == "PERIPHERAL"


def is_model_access_gated(component_id: str) -> bool:
    row = license_row(component_id)
    return row.get("license_status") == "MODEL_ACCESS_GATED" or row.get("license_status_secondary") == "MODEL_ACCESS_GATED"


def essential_registry_rows() -> list[dict[str, Any]]:
    from .essentials_pack import ESSENTIAL_IDS

    return [license_row(component_id) for component_id in ESSENTIAL_IDS]
