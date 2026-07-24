from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ComponentDefinition:
    id: str
    name: str
    description: str
    required: bool
    download_bytes: int
    installed_bytes: int
    dependencies: tuple[str, ...]
    verifier: str
    installer: str
    category: str = "Core"

    def public_dict(self) -> dict:
        value = asdict(self)
        value["dependencies"] = list(self.dependencies)
        return value


MB = 1024 * 1024

COMPONENTS: tuple[ComponentDefinition, ...] = (
    ComponentDefinition(
        "python", "Python", "Runtime for studio-api and tooling.", True,
        0, 200 * MB, (), "python", "detect_only",
    ),
    ComponentDefinition(
        "ffmpeg", "FFmpeg", "Media mux, trim, and encode toolkit.", True,
        80 * MB, 100 * MB, ("python",), "executable", "manual",
    ),
    ComponentDefinition(
        "comfyui", "ComfyUI", "Local node graph runtime for local video generation.", True,
        0, 500 * MB, ("python",), "comfy_service", "manual",
    ),
    ComponentDefinition(
        "ltx_checkpoint", "LTX Video Checkpoint",
        "Primary local image-to-video model weights.", True,
        12000 * MB, 12000 * MB, ("comfyui",), "ltx_file", "path_link",
    ),
    ComponentDefinition(
        "ollama", "Ollama", "Local LLM host for the Adept assistant.", False,
        0, 4000 * MB, (), "ollama_service", "manual",
    ),
    ComponentDefinition(
        "wan_models", "WAN 2.2 Models", "High/low noise WAN diffusion pair and VAE.", False,
        20000 * MB, 20000 * MB, ("comfyui",), "wan_files", "path_link",
    ),
    ComponentDefinition(
        "fal_key", "fal.ai API Key", "Cloud generation credentials stored encrypted locally.", False,
        0, 0, (), "fal_key", "credentials",
    ),
    ComponentDefinition(
        "pack_essential_photoreal", "Essential Photoreal Pack",
        "Creative Assets pack for photoreal faces and lighting.", False,
        400 * MB, 400 * MB, ("comfyui",), "asset_pack", "asset_pack",
    ),
    ComponentDefinition(
        "pack_essential_anime", "Essential Anime Pack",
        "Creative Assets pack for anime expressions.", False,
        250 * MB, 250 * MB, ("comfyui",), "asset_pack", "asset_pack",
    ),
    ComponentDefinition(
        "pack_essential_cinematic", "Essential Cinematic Pack",
        "Creative Assets pack for cinematic lighting.", False,
        200 * MB, 200 * MB, ("comfyui",), "asset_pack", "asset_pack",
    ),
    ComponentDefinition(
        "ltx23_ic_lora_ingredients", "LTX 2.3 Ingredients IC-LoRA",
        "Gated Ingredients IC-LoRA for Director reference-sheet conditioning (not a style LoRA).",
        False,
        2000 * MB, 2000 * MB, ("comfyui", "ltx_checkpoint"), "ic_lora_file", "path_link",
        category="Reference & Identity Models",
    ),
)

BY_ID = {component.id: component for component in COMPONENTS}


def get_component(component_id: str) -> ComponentDefinition:
    try:
        return BY_ID[component_id]
    except KeyError as exc:
        raise KeyError(f"Unknown component {component_id}") from exc
