"""M3.2a tool catalog — filmmaking task labels, not model names."""

from __future__ import annotations

from typing import Any

TOOL_CATALOG: list[dict[str, Any]] = [
    {
        "id": "image.upscale",
        "label": "Upscale image",
        "category": "enhance",
        "description": "Increase resolution while preserving detail. Original stays untouched.",
        "providerHint": "RealESRGAN / SeedVR2 (local Comfy)",
        "cloudPaid": False,
        "libraryKey": None,
        "inputs": ["sourceAssetId"],
        "codirectorTool": "propose_image_upscale",
    },
    {
        "id": "video.upscale",
        "label": "Upscale video",
        "category": "enhance",
        "description": "Temporally consistent video upscale. Not frame-by-frame image upscaling.",
        "providerHint": "SeedVR2 (local Comfy)",
        "cloudPaid": False,
        "libraryKey": "video.generated",
        "inputs": ["sourceAssetId"],
        "codirectorTool": "propose_video_upscale",
        "capabilityState": "deferred",
        "executionAvailability": "deferred",
        "honesty": "M41 4.1A: deferred until SeedVR2 worker is certified. No fake COMPLETE.",
    },
    {
        "id": "image.background_remove",
        "label": "Remove background",
        "category": "remove_replace",
        "description": "AI matte / transparency. Exports RGBA or matte.",
        "providerHint": "BiRefNet (local Comfy)",
        "cloudPaid": False,
        "libraryKey": None,
        "inputs": ["sourceAssetId"],
        "codirectorTool": "propose_background_remove",
    },
    {
        "id": "image.chroma_key",
        "label": "Chroma key (green/blue screen)",
        "category": "remove_replace",
        "description": "Key green or blue with spill suppression and edge controls.",
        "providerHint": "OpenCV / FFmpeg (local)",
        "cloudPaid": False,
        "libraryKey": None,
        "inputs": ["sourceAssetId", "keyColor", "tolerance", "spill", "edgeFeather"],
        "codirectorTool": "propose_chroma_key",
    },
    {
        "id": "image.delighting",
        "label": "Remove lighting (de-lighting)",
        "category": "enhance",
        "description": "True albedo / lighting removal when a production model is available. Not ordinary color correction.",
        "providerHint": "Blocked pending production OSS",
        "cloudPaid": False,
        "libraryKey": None,
        "inputs": ["sourceAssetId"],
        "codirectorTool": None,
        "blocked": True,
        "blockedReason": "No production-ready open-source de-lighting stack certified. Color grade / white-balance must not be labeled as de-lighting.",
    },
    {
        "id": "image.portrait_skin",
        "label": "Enhance portrait skin",
        "category": "enhance",
        "description": "Natural skin refinement. Preserves identity unless you request intentional change.",
        "providerHint": "CodeFormer / GFPGAN (local Comfy)",
        "cloudPaid": False,
        "libraryKey": None,
        "inputs": ["sourceAssetId", "fidelity", "allowIdentityChange"],
        "codirectorTool": "propose_portrait_skin",
    },
    {
        "id": "video.extend",
        "label": "Extend video (generative continuation)",
        "category": "extend_reframe",
        "description": "True generative continuation from the last frames. Not loop/freeze/slow-mo padding.",
        "providerHint": "WAN / LTX I2V (local Comfy)",
        "cloudPaid": False,
        "libraryKey": "video.generated",
        "inputs": ["sourceAssetId", "durationSec", "prompt"],
        "codirectorTool": "propose_video_extend",
        "mode": "generative_continuation",
    },
    {
        "id": "audio.music.generate",
        "label": "Generate music",
        "category": "create",
        "description": "Create a project-linked music bed (ACE-Step local sandbox).",
        "providerHint": "ACE-Step (local)",
        "cloudPaid": False,
        "libraryKey": "audio.music",
        "inputs": ["prompt", "durationSec"],
        "codirectorTool": "audio.generate_music",
        "workspace": "audiostudio",
    },
    {
        "id": "audio.sfx.generate",
        "label": "Generate sound effect",
        "category": "create",
        "description": "Create a project-linked SFX clip (MMAudio local sandbox).",
        "providerHint": "MMAudio (local)",
        "cloudPaid": False,
        "libraryKey": "audio.sfx",
        "inputs": ["prompt", "durationSec"],
        "codirectorTool": "audio.generate_sfx",
        "workspace": "audiostudio",
    },
    {
        "id": "audio.ambience.generate",
        "label": "Generate ambience bed",
        "category": "create",
        "description": "Create a loopable ambience bed via Audio Studio (MMAudio local sandbox).",
        "providerHint": "MMAudio (local)",
        "cloudPaid": False,
        "libraryKey": "audio.ambience",
        "inputs": ["prompt", "durationSec"],
        "codirectorTool": "audio.generate_ambience",
        "workspace": "audiostudio",
    },
    {
        "id": "scriptwriter",
        "label": "Scriptwriter",
        "category": "create",
        "description": "Treatments, outlines, beats, scenes, screenplay, dialogue, storyboard/shot briefs, commercial/trailer/social scripts.",
        "providerHint": "Local LLM via Co-Director provider",
        "cloudPaid": False,
        "libraryKey": "scripts",
        "inputs": ["documentType", "brief"],
        "codirectorTool": "propose_script_document",
        "workspace": "scriptwriter",
    },
    {
        "id": "brand.studio",
        "label": "Brand Studio",
        "category": "create",
        "description": "Generate brand-safe campaign visuals with locked logos, packaging, color palette, wording, and format direction.",
        "providerHint": "Reference-locked ImageGen (local Comfy)",
        "cloudPaid": False,
        "libraryKey": "props.generated",
        "inputs": ["prompt", "logoAssetIds", "productAssetIds", "brandColors", "requiredWording", "format"],
        "codirectorTool": "propose_brand_generate",
    },
]

CATEGORIES = [
    {"id": "create", "label": "Create"},
    {"id": "enhance", "label": "Enhance"},
    {"id": "remove_replace", "label": "Remove and Replace"},
    {"id": "extend_reframe", "label": "Extend and Reframe"},
    {"id": "finish", "label": "Finish"},
]


def get_tool(tool_id: str) -> dict[str, Any] | None:
    for t in TOOL_CATALOG:
        if t["id"] == tool_id:
            return t
    return None


def tools_by_category() -> list[dict[str, Any]]:
    out = []
    for cat in CATEGORIES:
        tools = [t for t in TOOL_CATALOG if t["category"] == cat["id"]]
        out.append({**cat, "tools": tools})
    # Finish currently routes to Editor / Export — expose as navigation helpers
    out[-1]["tools"] = out[-1]["tools"] + [
        {
            "id": "finish.editor",
            "label": "Open Editor",
            "category": "finish",
            "description": "Assemble picture and sound.",
            "navTab": "editor",
        },
        {
            "id": "finish.export",
            "label": "Export masters",
            "category": "finish",
            "description": "Deliver project exports.",
            "navTab": "home",
        },
    ]
    return out
