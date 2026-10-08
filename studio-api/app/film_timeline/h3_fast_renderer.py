"""Timeline V2 MiniMax H3 Local renderer.

Builds the attached Ref2Video graph as an API workflow. Timeline owns the
prompt, references, whole-second duration, and legal pixel size. This module
owns provider tags, the 17-frame internal length, and the saved acceleration
wiring. It does not call MiniMax H3 Director or the retired ref2v builder.
"""

from __future__ import annotations

from typing import Any

UNET_NAME = "minimax_h3_ref2va_pruned_int8_convrot.safetensors"
CLIP_NAME = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
VIDEO_VAE = "minimax_h3_video_vae_fp16.safetensors"
AUDIO_VAE = "minimax_h3_audio_vae_fp32.safetensors"

# Attached graph: EasyCache then Sage into the guider only.
EASYCACHE_REUSE = 0.1
EASYCACHE_START = 0.15
EASYCACHE_END = 0.9
SAGE_ATTENTION = "auto"
SAGE_ALLOW_COMPILE = False

SAMPLER_NAME = "res_multistep"
SCHEDULER_NAME = "simple"
STEPS = 20
DENOISE = 1.0
FPS = 24
REF_IMAGE_SIZE = "match"
MAX_IMAGES = 9
MAX_VIDEOS = 3
MAX_AUDIOS = 3

MECHANISM = "h3_fast_renderer"


def legal_frames(duration_sec: float, *, fps: float = FPS) -> int:
    """Attached math: max(5, round(seconds * 24)) snapped so n ≡ 5 (mod 17).

    The result is provider-only. Timeline keeps the whole-second request.
    """

    raw = max(5, int(round(float(duration_sec) * float(fps))))
    return raw + (5 - (raw % 17)) % 17


def legal_tail_frame_count(seconds: float, *, at_least: bool = False, fps: float = FPS) -> int:
    """Frame count the reference node will keep without cutting the ending.

    MiniMaxH3ReferenceToVideo keeps frames from the start of a reference and
    drops the end until the count is 5, 22, 39, 56, 73, ... If the reference
    is longer than the new shot, it also keeps only the beginning. A continuation
    tail must already land on that grid and end on the source's last frame.
    """

    target = max(5, int(round(float(seconds) * float(fps))))
    remainder = (target - 5) % 17
    if remainder == 0:
        return target
    if at_least:
        return target + (17 - remainder)
    snapped = target - remainder
    return snapped if snapped >= 5 else 5


def plan_references(slots: list[dict[str, Any]] | None, continuity: dict[str, Any] | None) -> dict[str, list[dict[str, str]]]:
    """Identity pictures stay first. The prior segment is a video. The last frame is extra."""

    packet = continuity if isinstance(continuity, dict) else {}
    enabled = bool(packet.get("enabled"))
    images: list[dict[str, str]] = []
    seen: set[str] = set()
    ranked = [
        item
        for item in (slots or [])
        if isinstance(item, dict)
        and str(item.get("role") or "") not in {"video", "audio"}
        and item.get("pictureIndex") is not None
        and str(item.get("assetId") or "").strip()
    ]
    ranked.sort(key=lambda item: int(item.get("pictureIndex") or 0))
    for item in ranked:
        asset_id = str(item.get("assetId") or "").strip()
        if asset_id in seen:
            continue
        seen.add(asset_id)
        images.append({"assetId": asset_id, "label": str(item.get("label") or "").strip()})
        if len(images) >= MAX_IMAGES:
            break

    videos: list[dict[str, str]] = []
    video_seen: set[str] = set()
    prior = str(packet.get("priorAssetId") or "").strip() if enabled else ""
    tail = str(packet.get("tailAssetId") or "").strip() if enabled else ""
    # The tail is the ending. The full prior clip stays the canonical asset and
    # is not the video reference once a tail exists.
    video_id = tail or prior
    if video_id:
        videos.append({"assetId": video_id, "label": "Ending" if tail else "Previous segment"})
        video_seen.add(video_id)
    for item in slots or []:
        if not isinstance(item, dict) or str(item.get("role") or "") != "video":
            continue
        asset_id = str(item.get("assetId") or "").strip()
        if not asset_id or asset_id in video_seen:
            continue
        videos.append({"assetId": asset_id, "label": str(item.get("label") or "Video").strip()})
        video_seen.add(asset_id)
        if len(videos) >= MAX_VIDEOS:
            break
    videos = videos[:MAX_VIDEOS]

    mode = packet.get("h3Continuity") if isinstance(packet.get("h3Continuity"), dict) else {}
    include_last = True if "includeLastFrame" not in mode else bool(mode.get("includeLastFrame"))
    last = str(packet.get("lastFrameAssetId") or "").strip() if enabled and include_last else ""
    if last and last not in seen and len(images) < MAX_IMAGES:
        images.append({"assetId": last, "label": "Last frame"})

    audios: list[dict[str, str]] = []
    audio_seen: set[str] = set()
    for item in slots or []:
        if not isinstance(item, dict) or str(item.get("role") or "") != "audio":
            continue
        asset_id = str(item.get("assetId") or "").strip()
        if not asset_id or asset_id in audio_seen:
            continue
        audios.append({"assetId": asset_id, "label": str(item.get("label") or "Audio").strip()})
        audio_seen.add(asset_id)
        if len(audios) >= MAX_AUDIOS:
            break
    return {"images": images, "videos": videos, "audios": audios}


def compile_provider_prompt(
    prompt: str,
    images: list[dict[str, str]],
    videos: list[dict[str, str]],
    audios: list[dict[str, str]],
    *,
    continuation: bool = False,
    pair_video_audio: bool = True,
    boundary: str = "",
    prepend: bool = False,
    spoken_language: str = "",
) -> str:
    """Refer to the tags the live node inserts before this text.

    MiniMaxH3ReferenceToVideo tokenizes references itself, in order: each picture
    as ``<Picture i>:``, then each video soundtrack as ``<Audio j>:`` immediately
    before ``<Video k>:``, then standalone audio. The Timed Prompt is appended
    after those blocks. Tags in this text point at that binding. They do not
    create a second one.
    """

    lines: list[str] = []
    last_picture = 0
    for index, item in enumerate(images, start=1):
        label = (item.get("label") or "this picture").strip()
        if label == "Last frame":
            last_picture = index
            continue
        if label == "Arrival":
            lines.append(f"<Picture {index}> is the opening frame this shot must reach at the end.")
            continue
        lines.append(f"<Picture {index}> is {label}.")
    audio_ordinal = 1
    if videos and prepend:
        lines.append(
            "<Video 1> is the opening that already follows this shot. "
            "Do not begin in that opening. End this shot there, with the same people, place, pose, facing, camera, and light."
        )
        if pair_video_audio:
            lines.append("<Audio 1> is the sound at that opening.")
            audio_ordinal = 2
    elif videos and pair_video_audio:
        if continuation:
            lines.append(
                "Continue directly from the ending shown in <Video 1>. "
                "Begin in that same framing, with the same positions and orientation. "
                "<Audio 1> is the sound at that ending."
            )
        else:
            label = (videos[0].get("label") or "the previous part").strip()
            lines.append(f"<Video 1> is {label}. <Audio 1> is the sound with that video.")
        audio_ordinal = 2
    elif videos:
        if continuation:
            lines.append(
                "Continue directly from the ending shown in <Video 1>. "
                "Begin in that same framing, with the same positions and orientation."
            )
        else:
            label = (videos[0].get("label") or "the previous part").strip()
            lines.append(f"<Video 1> is {label}.")
    spoken = " ".join(str(spoken_language or "").split()) or "English"
    from .dialogue_authority import prompt_asks_to_speak

    lock = (
        f"Spoken language is {spoken} only. Every spoken word is in {spoken}. "
        "Do not speak Chinese or any other language."
    )
    if not prompt_asks_to_speak(str(prompt or "")):
        lock = f"{lock} This shot has no written dialogue, so nobody speaks."
    lines.insert(0, lock)
    if last_picture:
        lines.append(
            f"<Picture {last_picture}> is the visual state this shot begins from. "
            "Motion starts there. Do not cut to a different pose or framing."
        )
    for item in audios:
        label = (item.get("label") or "this sound").strip()
        lines.append(f"<Audio {audio_ordinal}> is {label}.")
        audio_ordinal += 1
    note = str(boundary or "").strip()
    if note:
        lines.append(note)
    body = str(prompt or "").strip()
    if not lines:
        return body
    if not body:
        return "\n".join(lines)
    return "\n".join(lines) + "\n\n" + body


def build_h3_fast_workflow(
    *,
    prompt: str,
    filename_prefix: str,
    seed: int,
    width: int,
    height: int,
    duration_sec: float,
    image_names: list[str],
    image_labels: list[str] | None = None,
    video_names: list[str] | None = None,
    video_labels: list[str] | None = None,
    audio_names: list[str] | None = None,
    audio_labels: list[str] | None = None,
    continuation: bool = False,
    pair_video_audio: bool = True,
    boundary: str = "",
    prepend: bool = False,
    spoken_language: str = "",
    steps: int | None = None,
    lora_name: str | None = None,
    sage_attention: str | None = None,
) -> dict[str, Any]:
    """API graph matching the attached Ref2Video workflow.

    Scheduler reads the raw UNET. EasyCache then PathchSageAttentionKJ feed
    BasicGuider only. Those settings are the saved acceleration contract.
    """

    pictures = [str(name).strip() for name in image_names if str(name or "").strip()]
    videos = [str(name).strip() for name in (video_names or []) if str(name or "").strip()]
    audios = [str(name).strip() for name in (audio_names or []) if str(name or "").strip()]
    if not pictures and not videos:
        raise ValueError(
            "MiniMax H3 — Local needs a character, place, or previous finished part before it can run."
        )
    if len(pictures) > MAX_IMAGES:
        raise ValueError("MiniMax H3 — Local can use up to 9 pictures.")
    if len(videos) > MAX_VIDEOS:
        raise ValueError("MiniMax H3 — Local can use up to 3 videos.")
    if len(audios) > MAX_AUDIOS:
        raise ValueError("MiniMax H3 — Local can use up to 3 audio clips.")

    def _labels(names: list[str], supplied: list[str] | None) -> list[dict[str, str]]:
        raw = list(supplied or [])
        return [{"label": raw[i] if i < len(raw) else ""} for i in range(len(names))]

    provider_prompt = compile_provider_prompt(
        prompt,
        _labels(pictures, image_labels),
        _labels(videos, video_labels),
        _labels(audios, audio_labels),
        continuation=continuation,
        pair_video_audio=pair_video_audio,
        boundary=boundary,
        prepend=prepend,
        spoken_language=spoken_language,
    )
    frames = legal_frames(duration_sec)
    step_count = int(steps) if steps is not None else STEPS
    lora = str(lora_name or "").strip()

    # Callers choose the kernel. The default is the fast path. Base Optimized
    # continuations pass the safe profile; Standard H3 does not.
    sage_mode = str(sage_attention or SAGE_ATTENTION).strip() or SAGE_ATTENTION

    unet, cache, sage = "1", "5", "6"
    video_vae, audio_vae, clip = "2", "3", "4"
    scheduler, sampler_select, noise = "7", "8", "9"
    prompt_node, conditioner = "10", "11"
    guider, sampler = "12", "13"
    decode, decode_audio = "14", "15"
    create, save = "16", "17"

    graph: dict[str, Any] = {
        unet: {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": UNET_NAME, "weight_dtype": "default"},
        },
        video_vae: {"class_type": "VAELoader", "inputs": {"vae_name": VIDEO_VAE}},
        audio_vae: {"class_type": "VAELoader", "inputs": {"vae_name": AUDIO_VAE}},
        clip: {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": CLIP_NAME, "type": "minimax", "device": "default"},
        },
        cache: {
            "class_type": "EasyCache",
            "inputs": {
                "model": ["18", 0] if lora else [unet, 0],
                "reuse_threshold": EASYCACHE_REUSE,
                "start_percent": EASYCACHE_START,
                "end_percent": EASYCACHE_END,
                "verbose": False,
            },
        },
        sage: {
            "class_type": "PathchSageAttentionKJ",
            "inputs": {
                "model": [cache, 0],
                "sage_attention": sage_mode,
                "allow_compile": SAGE_ALLOW_COMPILE,
            },
        },
        scheduler: {
            "class_type": "BasicScheduler",
            "inputs": {
                "model": ["18", 0] if lora else [unet, 0],
                "scheduler": SCHEDULER_NAME,
                "steps": step_count,
                "denoise": DENOISE,
            },
        },
        sampler_select: {
            "class_type": "KSamplerSelect",
            "inputs": {"sampler_name": SAMPLER_NAME},
        },
        noise: {
            "class_type": "RandomNoise",
            "inputs": {"noise_seed": int(seed)},
        },
        prompt_node: {
            "class_type": "PrimitiveStringMultiline",
            "inputs": {"value": provider_prompt},
        },
        conditioner: {
            "class_type": "MiniMaxH3ReferenceToVideo",
            "inputs": {
                "clip": [clip, 0],
                "vae": [video_vae, 0],
                "audio_vae": [audio_vae, 0],
                "prompt": [prompt_node, 0],
                "width": int(width),
                "height": int(height),
                "length": int(frames),
                "ref_image_size": REF_IMAGE_SIZE,
            },
        },
        guider: {
            "class_type": "BasicGuider",
            "inputs": {
                "model": [sage, 0],
                "conditioning": [conditioner, 0],
            },
        },
        sampler: {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": [noise, 0],
                "guider": [guider, 0],
                "sampler": [sampler_select, 0],
                "sigmas": [scheduler, 0],
                "latent_image": [conditioner, 1],
            },
        },
        decode: {
            "class_type": "VAEDecode",
            "inputs": {"samples": [sampler, 0], "vae": [video_vae, 0]},
        },
        decode_audio: {
            "class_type": "VAEDecodeAudio",
            "inputs": {"samples": [sampler, 0], "vae": [audio_vae, 0]},
        },
        create: {
            "class_type": "CreateVideo",
            "inputs": {
                "images": [decode, 0],
                "audio": [decode_audio, 0],
                "fps": FPS,
                "bit_depth": 8,
                "color_space": "sRGB",
            },
        },
        save: {
            "class_type": "SaveVideo",
            "inputs": {
                "video": [create, 0],
                "filename_prefix": filename_prefix,
                "format": "mp4",
                "format.codec": "auto",
                "codec": "auto",
            },
        },
    }
    if lora:
        graph["18"] = {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": [unet, 0],
                "lora_name": lora,
                "strength_model": 1.0,
            },
        }

    cond = graph[conditioner]["inputs"]
    for index, name in enumerate(pictures):
        node_id = str(20 + index)
        graph[node_id] = {"class_type": "LoadImage", "inputs": {"image": name}}
        cond[f"ref_images.ref_image_{index}"] = [node_id, 0]
    for index, name in enumerate(videos):
        load_id = str(40 + index * 2)
        split_id = str(41 + index * 2)
        graph[load_id] = {"class_type": "LoadVideo", "inputs": {"file": name}}
        graph[split_id] = {
            "class_type": "GetVideoComponents",
            "inputs": {"video": [load_id, 0]},
        }
        cond[f"ref_videos.ref_video_{index}"] = [split_id, 0]
        if pair_video_audio:
            cond[f"ref_video_audios.ref_video_audio_{index}"] = [split_id, 1]
    for index, name in enumerate(audios):
        node_id = str(60 + index)
        graph[node_id] = {"class_type": "LoadAudio", "inputs": {"audio": name}}
        cond[f"ref_audios.ref_audio_{index}"] = [node_id, 0]
    return graph
