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


# ── Dependency-type taxonomy ────────────────────────────────────────────
# Coarse semantic classification of a setup component, derived from its
# verifier. Exposed on the readiness contract so the frontend can render
# type badges (MODEL / VAE / TEXT_ENCODER / UPSCALE_MODEL / CUSTOM_NODE /
# RUNTIME / CREDENTIAL / WORKFLOW) instead of inferring from counts or
# human-readable strings.
DEPENDENCY_TYPE_MODEL = "MODEL"
DEPENDENCY_TYPE_VAE = "VAE"
DEPENDENCY_TYPE_TEXT_ENCODER = "TEXT_ENCODER"
DEPENDENCY_TYPE_UPSCALE_MODEL = "UPSCALE_MODEL"
DEPENDENCY_TYPE_CUSTOM_NODE = "CUSTOM_NODE"
DEPENDENCY_TYPE_RUNTIME = "RUNTIME"
DEPENDENCY_TYPE_CREDENTIAL = "CREDENTIAL"
DEPENDENCY_TYPE_WORKFLOW = "WORKFLOW"
DEPENDENCY_TYPE_UNKNOWN = "UNKNOWN"

_VERIFIER_TO_DEP_TYPE: dict[str, str] = {
    "ltx_2_5_file": DEPENDENCY_TYPE_MODEL,
    "text_encoder_file": DEPENDENCY_TYPE_TEXT_ENCODER,
    "vae_file": DEPENDENCY_TYPE_VAE,
    "latent_upscale_model_file": DEPENDENCY_TYPE_UPSCALE_MODEL,
    "zimage_files": DEPENDENCY_TYPE_MODEL,
    "qwen_image_2512_files": DEPENDENCY_TYPE_MODEL,
    "krea2_files": DEPENDENCY_TYPE_MODEL,
    "linked_files": DEPENDENCY_TYPE_MODEL,
    "staged_video_pack": DEPENDENCY_TYPE_MODEL,
    "comfy_extension_nodes": DEPENDENCY_TYPE_CUSTOM_NODE,
    "comfy_service": DEPENDENCY_TYPE_RUNTIME,
    "ollama_service": DEPENDENCY_TYPE_RUNTIME,
    "fal_key": DEPENDENCY_TYPE_CREDENTIAL,
    "kie_key": DEPENDENCY_TYPE_CREDENTIAL,
    "wavespeed_key": DEPENDENCY_TYPE_CREDENTIAL,
    "video_understanding_files": DEPENDENCY_TYPE_MODEL,
    "qwen_omni_files": DEPENDENCY_TYPE_MODEL,
    "stills_perception_files": DEPENDENCY_TYPE_MODEL,
    "world_intelligence_files": DEPENDENCY_TYPE_MODEL,
    "realesrgan_ncnn": DEPENDENCY_TYPE_RUNTIME,
}


def dependency_type_for(component_id: str) -> str:
    """Return the semantic dependency type (MODEL / VAE / TEXT_ENCODER / ...) for a catalogued component."""
    try:
        definition = get_component(component_id)
    except Exception:  # noqa: BLE001
        return DEPENDENCY_TYPE_UNKNOWN
    return _VERIFIER_TO_DEP_TYPE.get(definition.verifier, DEPENDENCY_TYPE_UNKNOWN)


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
        "ltx_2_5_checkpoint", "LTX 2.5 Video Checkpoint",
        "LTX 2.5 distilled transformer (ComfyUI int8) - required for LTX 2.5 generation", False,
        25000 * MB, 25000 * MB, ("comfyui",), "ltx_2_5_file", "path_link",
        category="Video Models",
    ),
    ComponentDefinition(
        "ltx_2_5_text_encoder", "LTX 2.5 Text Encoder (Gemma 4)",
        "Gemma 4 12B text encoder with LTX 2.5 projection - required for LTX 2.5 generation", False,
        12000 * MB, 12000 * MB, ("comfyui",), "text_encoder_file", "path_link",
        category="Video Models",
    ),
    ComponentDefinition(
        "ltx_2_5_video_vae", "LTX 2.5 Video VAE",
        "LTX 2.5 video VAE decoder - required for LTX 2.5 generation", False,
        2000 * MB, 2000 * MB, ("comfyui",), "vae_file", "path_link",
        category="Video Models",
    ),
    ComponentDefinition(
        "ltx_2_5_audio_vae", "LTX 2.5 Audio VAE",
        "LTX 2.5 audio VAE - required for synchronized audio generation", False,
        1000 * MB, 1000 * MB, ("comfyui", "ltx_2_5_checkpoint", "ltx_2_5_text_encoder", "ltx_2_5_video_vae"), "vae_file", "path_link",
        category="Video Models",
    ),
    ComponentDefinition(
        "ltx_2_5_spatial_upscaler", "LTX 2.5 Spatial Upscaler",
        "LTX 2.5 spatial latent upscaler for 4K output - optional", False,
        1000 * MB, 1000 * MB, ("comfyui", "ltx_2_5_checkpoint"), "latent_upscale_model_file", "path_link",
        category="Video Models",
    ),
    ComponentDefinition(
        "ollama", "Ollama", "Local LLM host for the Adept assistant.", False,
        0, 4000 * MB, (), "ollama_service", "manual",
    ),
    ComponentDefinition(
        "ltx_checkpoint", "LTX Video Checkpoint (retired)",
        "RETIRED — LTX 2.3 is not a production video generator. Current local video is MiniMax H3 + LTX 2.5. Leftover callers may still resolve this id.",
        False,
        12000 * MB, 12000 * MB, ("comfyui",), "ltx_file", "path_link",
    ),
    ComponentDefinition(
        "wan_models", "WAN 2.2 Models (retired)",
        "RETIRED — WAN is not a production video generator. InfiniteTalk avatar WAN 2.1 I2V weights are a separate avatar runtime. Leftover callers may still resolve this id.",
        False,
        20000 * MB, 20000 * MB, ("comfyui",), "wan_files", "path_link",
    ),
    ComponentDefinition(
        "hunyuan_video_15",
        "HunyuanVideo 1.5 (retired)",
        "RETIRED — Hunyuan Video is not a production video generator. Hunyuan Image remains a still-image catalog entry. Leftover callers may still resolve this id.",
        False,
        45000 * MB,
        45000 * MB,
        ("comfyui",),
        "hunyuan_files",
        "huggingface_snapshot",
        category="Video Models",
    ),
    ComponentDefinition(
        "hunyuan_video_13b",
        "HunyuanVideo 13B (retired)",
        "RETIRED — Hunyuan Video is not a production video generator. Leftover callers may still resolve this id.",
        False,
        80000 * MB,
        80000 * MB,
        ("comfyui",),
        "hunyuan_files",
        "huggingface_snapshot",
        category="Video Models",
    ),
    ComponentDefinition(
        "minimax_h3_base_optimized",
        "MiniMax H3 Base Optimized",
        "Installed. Existing files detected. Optional reference-to-video profile using the MiniMax H3 weights already on this computer. No download.",
        False,
        0,
        0,
        ("comfyui",),
        "staged_video_pack",
        "detect_only",
        category="Video Models",
    ),
    ComponentDefinition(
        "hunyuan_video_1_5_distilled",
        "HunyuanVideo 1.5 Distilled",
        "Optional · Fast Local Video. Fast distilled local video generation for Text-to-Video and Start-Frame workflows. Recommended for systems with lower VRAM.",
        False,
        0,
        0,
        ("comfyui",),
        "staged_video_pack",
        "detect_only",
        category="Video Models",
    ),
    ComponentDefinition(
        "zimage_models", "Z-Image Turbo Models",
        "Local still-image stack: Z-Image Turbo UNET, Qwen text encoder, and AE VAE.",
        False,
        20000 * MB, 20000 * MB, ("comfyui",), "zimage_files", "path_link",
        category="Still Image Models",
    ),
    ComponentDefinition(
        "qwen_image_2512_models", "Qwen-Image-2512 Models",
        "Local still-image stack: Qwen-Image-2512 UNET, Qwen 2.5 VL text encoder, and VAE.",
        False,
        28000 * MB, 28000 * MB, ("comfyui",), "qwen_image_2512_files", "path_link",
        category="Still Image Models",
    ),
    ComponentDefinition(
        "krea2_models", "Krea 2 Turbo (+RAW) Models",
        "Local still-image stack: Krea 2 Turbo and RAW checkpoints, Qwen3-VL text encoder, "
        "and Qwen Image VAE under the shared model root (krea2 subtree). HF repos are gated "
        "(Krea 2 Community License) — link an existing download; never auto-downloaded.",
        False,
        40000 * MB, 40000 * MB, ("comfyui",), "krea2_files", "path_link",
        category="Still Image Models",
    ),
    ComponentDefinition(
        "flux1_dev_local",
        "FLUX.1 Dev",
        "Local open-weight FLUX.1 Dev image model for high-quality cinematic stills.",
        False,
        23000 * MB,
        25000 * MB,
        ("comfyui",),
        "linked_files",
        "path_link",
        category="Still Image Models",
    ),
    ComponentDefinition(
        "flux1_schnell_local",
        "FLUX.1 Schnell",
        "Local open-weight FLUX.1 Schnell image model for fast previews and ideation.",
        False,
        23000 * MB,
        25000 * MB,
        ("comfyui",),
        "linked_files",
        "path_link",
        category="Still Image Models",
    ),
    ComponentDefinition(
        "flux1_kontext_dev_local",
        "FLUX.1 Kontext Dev",
        "Local open-weight FLUX.1 Kontext Dev model for photoreal character work and context-aware edits.",
        False,
        24000 * MB,
        26000 * MB,
        ("comfyui",),
        "linked_files",
        "path_link",
        category="Still Image Models",
    ),
    ComponentDefinition(
        "sana_15_local",
        "Sana 1.5",
        "Local open-weight Sana 1.5 image model for stylized and anime-leaning stills.",
        False,
        12000 * MB,
        14000 * MB,
        ("comfyui",),
        "linked_files",
        "path_link",
        category="Still Image Models",
    ),
    ComponentDefinition(
        "sdxl_local",
        "Stable Diffusion XL",
        "Local SDXL still-image stack for broad ecosystem compatibility and editing workflows.",
        False,
        13000 * MB,
        15000 * MB,
        ("comfyui",),
        "linked_files",
        "path_link",
        category="Still Image Models",
    ),
    ComponentDefinition(
        "illustrious_local",
        "Illustrious XL 1.0 (Anime)",
        "Local Illustrious XL v1.0 SDXL anime/animation/stylized/realistic-anime image engine.",
        False,
        9000 * MB,
        12000 * MB,
        ("comfyui",),
        "illustrious_files",
        "path_link",
        category="Still Image Models",
    ),
    ComponentDefinition(
        "sd35_large_local",
        "Stable Diffusion 3.5 Large",
        "Local SD 3.5 Large still-image stack for modern prompt adherence and composition work.",
        False,
        17000 * MB,
        18000 * MB,
        ("comfyui",),
        "linked_files",
        "path_link",
        category="Still Image Models",
    ),
    ComponentDefinition(
        "cogview4_local",
        "CogView 4",
        "Experimental local CogView 4 still-image stack catalog entry.",
        False,
        18000 * MB,
        20000 * MB,
        ("comfyui",),
        "linked_files",
        "path_link",
        category="Still Image Models",
    ),
    ComponentDefinition(
        "hidream_local",
        "HiDream",
        "Experimental local HiDream still-image stack catalog entry.",
        False,
        20000 * MB,
        22000 * MB,
        ("comfyui",),
        "linked_files",
        "path_link",
        category="Still Image Models",
    ),
    ComponentDefinition(
        "lumina_image_2_local",
        "Lumina Image 2",
        "Experimental local Lumina Image 2 still-image stack catalog entry.",
        False,
        18000 * MB,
        20000 * MB,
        ("comfyui",),
        "linked_files",
        "path_link",
        category="Still Image Models",
    ),
    ComponentDefinition(
        "pixart_sigma_local",
        "PixArt Sigma",
        "Experimental local PixArt Sigma still-image stack catalog entry.",
        False,
        12000 * MB,
        14000 * MB,
        ("comfyui",),
        "linked_files",
        "path_link",
        category="Still Image Models",
    ),
    ComponentDefinition(
        "kolors_local",
        "Kolors",
        "Experimental local Kolors still-image stack catalog entry.",
        False,
        13000 * MB,
        15000 * MB,
        ("comfyui",),
        "linked_files",
        "path_link",
        category="Still Image Models",
    ),
    ComponentDefinition(
        "omnigen_local",
        "OmniGen",
        "Experimental local OmniGen multimodal image stack catalog entry.",
        False,
        14000 * MB,
        16000 * MB,
        ("comfyui",),
        "linked_files",
        "path_link",
        category="Still Image Models",
    ),
    ComponentDefinition(
        "janus_pro_local",
        "Janus-Pro",
        "Experimental local Janus-Pro multimodal image generation and edit stack catalog entry.",
        False,
        14000 * MB,
        16000 * MB,
        ("comfyui",),
        "linked_files",
        "path_link",
        category="Still Image Models",
    ),
    ComponentDefinition(
        "hunyuan_image_local",
        "Hunyuan Image",
        "Experimental local Hunyuan Image stack catalog entry for future certified image workflows.",
        False,
        20000 * MB,
        22000 * MB,
        ("comfyui",),
        "linked_files",
        "path_link",
        category="Still Image Models",
    ),
    ComponentDefinition(
        "fal_key", "fal.ai API Key", "Cloud generation credentials stored encrypted locally.", False,
        0, 0, (), "fal_key", "credentials",
        category="API Providers",
    ),
    ComponentDefinition(
        "kie_key", "Kie.ai API Key", "Cloud generation credentials stored encrypted locally.", False,
        0, 0, (), "kie_key", "credentials",
        category="API Providers",
    ),
    ComponentDefinition(
        "wavespeed_key", "WaveSpeed.ai API Key", "Cloud generation credentials stored encrypted locally.", False,
        0, 0, (), "wavespeed_key", "credentials",
        category="API Providers",
    ),
    ComponentDefinition(
        "magi_gpu_upscale",
        "MAGI GPU Upscaling",
        "High-quality GPU video upscaling for final delivery and mastering. Real-ESRGAN.",
        False,
        45 * MB,
        60 * MB,
        ("ffmpeg",),
        "realesrgan_ncnn",
        "realesrgan_ncnn",
        category="MAGI Finishing",
    ),
    ComponentDefinition(
        "ace_step_local",
        "ACE-Step Music Runtime",
        "Local ACE-Step music generation sandbox tracked by Setup for creator-facing readiness and repair visibility.",
        False,
        0,
        16000 * MB,
        ("python", "ffmpeg"),
        "audio_sandbox",
        "manual",
        category="Music Runtimes",
    ),
    ComponentDefinition(
        "mmaudio_local",
        "MMAudio Runtime",
        "Local MMAudio ambience and sound-effect sandbox tracked by Setup for creator-facing readiness and repair visibility.",
        False,
        0,
        16000 * MB,
        ("python", "ffmpeg"),
        "audio_sandbox",
        "manual",
        category="Music Runtimes",
    ),
    ComponentDefinition(
        "pack_essential_photoreal", "Essential Photoreal Pack",
        "Creative Assets pack for photoreal faces and lighting.", False,
        400 * MB, 400 * MB, ("comfyui",), "asset_pack", "asset_pack",
        category="Creative Packs",
    ),
    ComponentDefinition(
        "pack_essential_anime", "Essential Anime Pack",
        "Creative Assets pack for anime expressions.", False,
        250 * MB, 250 * MB, ("comfyui",), "asset_pack", "asset_pack",
        category="Creative Packs",
    ),
    ComponentDefinition(
        "pack_essential_cinematic", "Essential Cinematic Pack",
        "Creative Assets pack for cinematic lighting.", False,
        200 * MB, 200 * MB, ("comfyui",), "asset_pack", "asset_pack",
        category="Creative Packs",
    ),
    ComponentDefinition(
        "index_tts2",
        "IndexTTS2",
        "Official IndexTTS2 local character voice runtime with pinned upstream repo, isolated venv, and reference-based expressive voice cloning. ~15GB full install.",
        False,
        15000 * MB,
        15000 * MB,
        ("python", "ffmpeg"),
        "index_tts2",
        "index_tts2",
        category="Character Voice Models",
    ),
    ComponentDefinition(
        "qwen_voice_design_17b",
        "Qwen3-TTS Voice Design 1.7B",
        "Official Qwen3-TTS VoiceDesign model for creating novel character voices from text direction. Enables Character Voice Design. ~3.5GB HF download + isolated venv.",
        False,
        3500 * MB,
        3500 * MB,
        ("python", "ffmpeg"),
        "m210b_sandbox",
        "m210b_qwen_voice",
        category="Character Voice Models",
    ),
    ComponentDefinition(
        "qwen_voice_clone_17b",
        "Qwen3-TTS Voice Clone 1.7B",
        "Official Qwen3-TTS Base model for reference-conditioned voice cloning. Enables Character Voice Clone + dialogue. ~3.5GB HF download + isolated venv.",
        False,
        3500 * MB,
        3500 * MB,
        ("python", "ffmpeg"),
        "m210b_sandbox",
        "m210b_qwen_voice",
        category="Character Voice Models",
    ),
    ComponentDefinition(
        "ltx23_ic_lora_ingredients", "LTX 2.3 Ingredients IC-LoRA (retired)",
        "RETIRED — LTX 2.3 Ingredients IC-LoRA is not a production video generator. Leftover callers may still resolve this id.",
        False,
        2000 * MB, 2000 * MB, ("comfyui", "ltx_checkpoint"), "ic_lora_file", "path_link",
        category="Reference & Identity Models",
    ),
    ComponentDefinition(
        "comfyui_hunyuan_nodes",
        "Hunyuan ComfyUI Extension (retired)",
        "RETIRED — Hunyuan Video Comfy nodes are not a production video dependency. Leftover callers may still resolve this id.",
        False,
        50 * MB,
        80 * MB,
        ("comfyui",),
        "comfy_extension_nodes",
        "comfy_extension",
        category="ComfyUI Extensions",
    ),
    ComponentDefinition(
        "longcat-video-avatar-1-5-local",
        "LongCat Avatar 1.5 (RETIRED)",
        "RETIRED — Avatar Studio shelved from current Adept UI. Not part of production readiness. Do not install/probe from current flows.",
        False,
        147000 * MB,
        150000 * MB,
        ("python", "ffmpeg"),
        "avatar_runtime",
        "avatar_runtime",
        category="Avatar Runtimes (RETIRED)",
    ),
    ComponentDefinition(
        "infinitetalk-local",
        "InfiniteTalk (RETIRED)",
        "RETIRED — Avatar Studio / InfiniteTalk / Wan shelved from current Adept UI. Not part of production readiness.",
        False,
        34000 * MB,
        38000 * MB,
        ("python", "ffmpeg"),
        "avatar_runtime",
        "avatar_runtime",
        category="Avatar Runtimes (RETIRED)",
    ),
    ComponentDefinition(
        "musetalk-1-5-local",
        "MuseTalk 1.5",
        "RETIRED — Avatar Studio shelved. MuseTalk not part of current production readiness.",
        False,
        10000 * MB,
        12000 * MB,
        ("python", "ffmpeg"),
        "avatar_runtime",
        "avatar_runtime",
        category="Avatar Runtimes (RETIRED)",
    ),
    ComponentDefinition(
        "echomimic-v2-local",
        "EchoMimicV2",
        "RETIRED — Avatar Studio shelved. EchoMimic not part of current production readiness.",
        False,
        17000 * MB,
        19000 * MB,
        ("python", "ffmpeg"),
        "avatar_runtime",
        "avatar_runtime",
        category="Avatar Runtimes (RETIRED)",
    ),
    ComponentDefinition(
        "videochat3_4b",
        "VideoChat3 4B",
        "Co-Director Timeline visual review. Required for temporal continuity.",
        True,
        8500 * MB,
        9000 * MB,
        ("python", "ffmpeg"),
        "video_understanding_files",
        "huggingface_snapshot",
        category="Video Understanding",
    ),
    ComponentDefinition(
        "internvideo3_8b",
        "InternVideo3 8B",
        "Optional deep sequence review for Co-Director. Hardware-gated.",
        False,
        17500 * MB,
        19000 * MB,
        ("python", "ffmpeg"),
        "video_understanding_files",
        "huggingface_snapshot",
        category="Video Understanding",
    ),
    ComponentDefinition(
        "qwen2_5_omni_7b",
        "Qwen2.5-Omni 7B",
        "Recommended for full Timeline continuity review and Co-Director media "
        "intelligence. Timeline Generate and Continue still run when this model is "
        "absent. It is not a generation blocker and not a boot blocker.",
        False,
        26000 * MB,
        28000 * MB,
        ("python", "ffmpeg"),
        "qwen_omni_files",
        "huggingface_snapshot",
        category="Media Intelligence",
    ),
    ComponentDefinition(
        "grounding_dino_tiny",
        "Grounding DINO Tiny",
        "Optional Co-Director scene boxes. Testing. Not required to generate.",
        False,
        1500 * MB,
        1600 * MB,
        ("python",),
        "stills_perception_files",
        "stills_perception_hf",
        category="Co-Director Scene Perception",
    ),
    ComponentDefinition(
        "sam21_hiera_tiny",
        "SAM 2.1 Tiny",
        "Optional Co-Director masks. Testing. Not required to generate.",
        False,
        400 * MB,
        450 * MB,
        ("python",),
        "stills_perception_files",
        "stills_perception_hf",
        category="Co-Director Scene Perception",
    ),
    ComponentDefinition(
        "depth_anything_v2_small",
        "Depth Anything V2 Small",
        "Optional Co-Director near/far help. Testing. Apache-2.0 Small only.",
        False,
        200 * MB,
        250 * MB,
        ("python",),
        "stills_perception_files",
        "stills_perception_hf",
        category="Co-Director Scene Perception",
    ),
    ComponentDefinition(
        "vjepa2_world_intelligence",
        "Co-Director World Intelligence",
        "Advanced Co-Director world-state comparison. Helps preserve visual world consistency across scenes.",
        False,
        2800 * MB,
        3000 * MB,
        ("python",),
        "world_intelligence_files",
        "huggingface_snapshot",
        category="Co-Director World Intelligence",
    ),
    ComponentDefinition(
        "character_multiview_engine",
        "Character Angles",
        "Detect-only readiness for Qwen Image Edit 2509 Character Angles.",
        False,
        0,
        0,
        (),
        "character_multiview_engine",
        "detect_only",
        category="Character Creator",
    ),
    ComponentDefinition(
        "wonder3d_multiview",
        "Wonder3D (not used)",
        "AGPL-3.0. Never installed. Character Angles use Qwen Image Edit 2509.",
        False,
        0,
        0,
        (),
        "wonder3d_multiview",
        "detect_only",
        category="Character Creator",
    ),
)

BY_ID = {component.id: component for component in COMPONENTS}

#: Retired local video generators. Kept in COMPONENTS so leftover get_component()
#: callers still resolve, but public Setup/health/install lists must filter these.
RETIRED_VIDEO_SETUP_COMPONENT_IDS: frozenset[str] = frozenset(
    {
        "wan_models",
        "hunyuan_video_15",
        "hunyuan_video_13b",
        "ltx_checkpoint",
        "ltx23_ic_lora_ingredients",
        "comfyui_hunyuan_nodes",
    }
)

#: Avatar Studio runtimes temporarily retired from current Adept UI production.
#: Excluded from public Setup catalog / readiness; source kept on disk.
RETIRED_AVATAR_SETUP_COMPONENT_IDS: frozenset[str] = frozenset(
    {
        "longcat-video-avatar-1-5-local",
        "infinitetalk-local",
        "musetalk-1-5-local",
        "echomimic-v2-local",
    }
)

#: Obsolete Character Creator leftovers. Kept in COMPONENTS so leftover
#: get_component() callers still resolve; public Setup must not list them.
RETIRED_OBSOLETE_SETUP_COMPONENT_IDS: frozenset[str] = frozenset(
    {
        "wonder3d_multiview",
    }
)


def is_retired_video_setup_component(component_id: str) -> bool:
    return str(component_id or "") in RETIRED_VIDEO_SETUP_COMPONENT_IDS


def is_retired_avatar_setup_component(component_id: str) -> bool:
    return str(component_id or "") in RETIRED_AVATAR_SETUP_COMPONENT_IDS


def is_retired_obsolete_setup_component(component_id: str) -> bool:
    return str(component_id or "") in RETIRED_OBSOLETE_SETUP_COMPONENT_IDS


def public_components() -> tuple[ComponentDefinition, ...]:
    """Current production Setup catalog (MiniMax H3 + LTX 2.5 video, image, voice).

    Avatar Studio runtimes remain on disk but are excluded from public Setup —
    they are not current Adept UI production destinations. Obsolete leftovers
    such as Wonder3D are also excluded so they cannot count as Not Installed.
    """
    return tuple(
        component
        for component in COMPONENTS
        if component.id not in RETIRED_VIDEO_SETUP_COMPONENT_IDS
        and component.id not in RETIRED_AVATAR_SETUP_COMPONENT_IDS
        and component.id not in RETIRED_OBSOLETE_SETUP_COMPONENT_IDS
    )


def get_component(component_id: str) -> ComponentDefinition:
    try:
        return BY_ID[component_id]
    except KeyError as exc:
        raise KeyError(f"Unknown component {component_id}") from exc
