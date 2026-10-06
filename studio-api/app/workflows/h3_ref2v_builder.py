"""MiniMax H3 Reference-to-Video graph — FM4 Comfy baseline emit.

Emits a queued API graph materially equivalent to
FM4_QUEUED_API_GRAPH.json (Quality identity cert, 2026-09-10):

- MiniMaxH3ReferenceToVideo + ref2va UNET + Qwen3VL + video/audio VAE
- PathchSageAttentionKJ on the model path (Quality: no EasyCache)
- Flat COMFY_AUTOGROW keys: ref_images.ref_image_N / ref_videos.ref_video_N / ref_video_audios.ref_video_audio_N / ref_audios.ref_audio_N
- PrimitiveStringMultiline → prompt (exact Timed Prompt bytes)
- CreateVideo color_space=sRGB + SaveVideo format=mp4
- LoadImage node ids grow along the 9-ref capacity template

Timeline supplies ONLY: prompt, ordered creator refs, duration→legal length,
Quality/Fast. No Adept prompt rewrite / Front / _h3id / crop in this builder.
"""

from __future__ import annotations

from typing import Any

from ..video_runtime.seed_resolve import comfy_noise_seed

H3_REF2VA_UNET = "minimax_h3_ref2va_pruned_int8_convrot.safetensors"
H3_CLIP = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
H3_VIDEO_VAE = "minimax_h3_video_vae_fp16.safetensors"
H3_AUDIO_VAE = "minimax_h3_audio_vae_fp32.safetensors"

# FM4 Quality identity baseline canvas (ResolutionSelector 0.7 @ 16:9).
H3_REF2V_WIDTH = 1152
H3_REF2V_HEIGHT = 640
H3_REF2V_CANVAS = f"{H3_REF2V_WIDTH}x{H3_REF2V_HEIGHT}"
H3_REF2V_STEPS = 20
H3_REF2V_SAMPLER = "res_multistep"
H3_REF2V_SCHEDULER = "simple"
H3_REF2V_DENOISE = 1.0
H3_REF2V_FPS = 24.0

# FM4 / UI baseline node ids (3-ref identity + 9-ref capacity template).
H3_NODE_UNET = "127"
H3_NODE_SAGE = "144"
H3_NODE_CLIP = "128"
H3_NODE_VIDEO_VAE = "119"
H3_NODE_AUDIO_VAE = "120"
H3_NODE_PROMPT = "138"
H3_NODE_CONDITIONER = "136"
H3_NODE_NOISE = "129"
H3_NODE_SAMPLER_SELECT = "123"
H3_NODE_SCHEDULER = "124"
H3_NODE_GUIDER = "126"
H3_NODE_SAMPLER = "125"
H3_NODE_DECODE = "122"
H3_NODE_DECODE_AUDIO = "121"
H3_NODE_CREATE_VIDEO = "130"
H3_NODE_SAVE_VIDEO = "92"
H3_FAST_CACHE_NODE = "EasyCache"
H3_FAST_CACHE_NODE_ID = "143"
# Baseline UI EasyCache widgets on the 3/9-ref workflows.
H3_FAST_REUSE = 0.1
H3_FAST_START = 0.15
H3_FAST_END = 0.9
H3_SAGE_ATTENTION = "auto"
H3_SAGE_ALLOW_COMPILE = False

# Capacity template LoadImage ids from MiniMax_Reference_to_Video_9_Image_Refs.json
H3_REF_LOADIMAGE_IDS = ("137", "139", "145", "146", "147", "148", "149", "150", "151")
H3_REF_LOADAUDIO_START = 200
H3_REF_LOADVIDEO_START = 300

# Back-compat alias used by older tests / callers that still import this name.
H3_REF_NODE_START = int(H3_REF_LOADIMAGE_IDS[0])


def _next_node_id(graph: dict[str, Any], start: int = H3_REF_LOADAUDIO_START) -> str:
    n = max(int(start), H3_REF_LOADAUDIO_START)
    while str(n) in graph:
        n += 1
    return str(n)


def resolve_h3_generation_frames(duration_sec: float) -> int:
    """Authoritative MiniMax H3 frame-count resolver.

    Snaps UP to the next legal 17k+5 frame count at or above the request.
    If the requested duration already resolves to a legal count, no extra
    frames are added.

    12.0s @ 24fps = 288 frames (illegal) → 294 frames (legal, 17*17+5)
    12.25s @ 24fps = 294 frames (legal) → 294 frames (no change)

    The caller is responsible for trimming the generated excess back to the
    requested Timeline duration.
    """
    from ..video_runtime.legal_canvas import H3_TIMELINE_FPS, snap_h3_timeline_duration

    snap = snap_h3_timeline_duration(float(duration_sec), fps=H3_TIMELINE_FPS)
    if not snap.get("ok"):
        from ..video_runtime.legal_canvas import SpecFidelityError

        raise SpecFidelityError(
            str(snap.get("message") or "MiniMax H3 duration is above 15s."),
            code="ILLEGAL_DURATION",
        )
    return int(snap["frames"])


def resolve_h3_ref_image_size(value: Any = None) -> str:
    """Node enum is match | max. Production default stays match until benchmarked."""
    token = str(value or "match").strip().lower()
    return token if token in {"match", "max"} else "match"


def snap_h3_length(frames: int) -> int:
    """Snap a frame count UP to the next legal 17k+5 count.

    Already-legal counts at or below H3_MAX_FRAMES (362) pass through.
    Do NOT convert legal max frames through seconds — 362/24 ≈ 15.083s is the
    disclosed ceiling for a clean 15s creator request, but it is above the
    15.0s *request* max and would false-reject if re-entered via duration snap.
    """
    from ..video_runtime.legal_canvas import H3_MAX_FRAMES, SpecFidelityError

    n = max(0, int(frames or 0))
    if n > H3_MAX_FRAMES:
        raise SpecFidelityError(
            f"This shot is {n / H3_REF2V_FPS:g}s ({n} frames). MiniMax H3 can run up to "
            f"15s ({H3_MAX_FRAMES} frames). Shorten it or split it into batches.",
            code="ILLEGAL_DURATION",
        )
    if n >= 5 and n % 17 == 5:
        return n
    return resolve_h3_generation_frames(n / H3_REF2V_FPS)


def frames_for_duration(duration_sec: float) -> int:
    """Resolve a requested duration to legal MiniMax H3 generation frames."""
    return resolve_h3_generation_frames(float(duration_sec))


def find_h3_conditioner(graph: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    for node_id, node in graph.items():
        if isinstance(node, dict) and node.get("class_type") == "MiniMaxH3ReferenceToVideo":
            return str(node_id), node
    raise ValueError("Submitted graph is missing MiniMaxH3ReferenceToVideo.")


def h3_prompt_text(graph: dict[str, Any]) -> str:
    """Resolve exact Input Text (PrimitiveStringMultiline link or inline string)."""
    _, cond = find_h3_conditioner(graph)
    prompt = (cond.get("inputs") or {}).get("prompt")
    if isinstance(prompt, (list, tuple)) and prompt:
        src = graph.get(str(prompt[0])) or {}
        if src.get("class_type") == "PrimitiveStringMultiline":
            return str(((src.get("inputs") or {}).get("value") or ""))
        return ""
    return str(prompt or "")


def h3_ref_image_links(graph: dict[str, Any]) -> dict[str, list[Any]]:
    """Normalize flat ref_images.ref_image_N and nested ref_images dict."""
    _, cond = find_h3_conditioner(graph)
    inputs = cond.get("inputs") or {}
    out: dict[str, list[Any]] = {}
    nested = inputs.get("ref_images")
    if isinstance(nested, dict):
        for key, link in nested.items():
            if str(key).startswith("ref_image_") and isinstance(link, (list, tuple)):
                out[str(key)] = list(link)
    for key, value in inputs.items():
        if str(key).startswith("ref_images.ref_image_") and isinstance(value, (list, tuple)):
            short = str(key).split(".", 1)[1]
            out[short] = list(value)
    return dict(sorted(out.items(), key=lambda kv: int(str(kv[0]).rsplit("_", 1)[-1])))


def h3_ref_audio_links(graph: dict[str, Any]) -> dict[str, list[Any]]:
    _, cond = find_h3_conditioner(graph)
    inputs = cond.get("inputs") or {}
    out: dict[str, list[Any]] = {}
    nested = inputs.get("ref_audios")
    if isinstance(nested, dict):
        for key, link in nested.items():
            if str(key).startswith("ref_audio_") and isinstance(link, (list, tuple)):
                out[str(key)] = list(link)
    for key, value in inputs.items():
        if str(key).startswith("ref_audios.ref_audio_") and isinstance(value, (list, tuple)):
            short = str(key).split(".", 1)[1]
            out[short] = list(value)
    return dict(sorted(out.items(), key=lambda kv: int(str(kv[0]).rsplit("_", 1)[-1])))



def h3_ref_video_links(graph: dict[str, Any]) -> dict[str, list[Any]]:
    _, cond = find_h3_conditioner(graph)
    inputs = cond.get("inputs") or {}
    out: dict[str, list[Any]] = {}
    nested = inputs.get("ref_videos")
    if isinstance(nested, dict):
        for key, link in nested.items():
            if str(key).startswith("ref_video_") and isinstance(link, (list, tuple)):
                out[str(key)] = list(link)
    for key, value in inputs.items():
        if str(key).startswith("ref_videos.ref_video_") and isinstance(value, (list, tuple)):
            short = str(key).split(".", 1)[1]
            out[short] = list(value)
    return dict(sorted(out.items(), key=lambda kv: int(str(kv[0]).rsplit("_", 1)[-1])))


def build_h3_ref2v(
    *,
    prompt: str,
    ref_comfy_names: list[str],
    filename_prefix: str,
    seed: int = 0,
    width: int = H3_REF2V_WIDTH,
    height: int = H3_REF2V_HEIGHT,
    length: int = 5,
    steps: int = H3_REF2V_STEPS,
    ref_image_size: str = "match",
    fast: bool = False,
    ref_audio_comfy_names: list[str] | None = None,
    ref_video_comfy_names: list[str] | None = None,
    generate_audio: bool = True,
) -> dict[str, Any]:
    names = [str(name).strip() for name in ref_comfy_names if str(name or "").strip()]
    audio_names = [str(name).strip() for name in (ref_audio_comfy_names or []) if str(name or "").strip()]
    video_names = [str(name).strip() for name in (ref_video_comfy_names or []) if str(name or "").strip()]
    if not names:
        raise ValueError("H3_REF2V_REQUIRED: MiniMax H3 Reference-to-Video needs at least one reference picture.")
    if len(names) > 9:
        raise ValueError("MiniMax H3 Reference-to-Video accepts at most 9 reference pictures.")
    if len(audio_names) > 3:
        raise ValueError("MiniMax H3 Reference-to-Video accepts at most 3 reference audios.")
    if len(video_names) > 3:
        raise ValueError("MiniMax H3 Reference-to-Video accepts at most 3 reference videos.")
    from ..minimax_h3.route_a_adapter import assert_h3_legal_canvas

    length = snap_h3_length(length)
    width, height = assert_h3_legal_canvas(int(width or H3_REF2V_WIDTH), int(height or H3_REF2V_HEIGHT))
    prompt_text = str(prompt)

    # Model path: Quality = UNET → Sage; Fast = UNET → EasyCache → Sage.
    model_src: list[Any] = [H3_NODE_UNET, 0]
    graph: dict[str, Any] = {
        H3_NODE_UNET: {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": H3_REF2VA_UNET, "weight_dtype": "default"},
        },
        H3_NODE_CLIP: {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": H3_CLIP, "type": "minimax", "device": "default"},
        },
        H3_NODE_VIDEO_VAE: {
            "class_type": "VAELoader",
            "inputs": {"vae_name": H3_VIDEO_VAE},
        },
        H3_NODE_AUDIO_VAE: {
            "class_type": "VAELoader",
            "inputs": {"vae_name": H3_AUDIO_VAE},
        },
        H3_NODE_PROMPT: {
            "class_type": "PrimitiveStringMultiline",
            "inputs": {"value": prompt_text},
        },
        H3_NODE_CONDITIONER: {
            "class_type": "MiniMaxH3ReferenceToVideo",
            "inputs": {
                "prompt": [H3_NODE_PROMPT, 0],
                "width": width,
                "height": height,
                "length": length,
                "ref_image_size": resolve_h3_ref_image_size(ref_image_size),
                "clip": [H3_NODE_CLIP, 0],
                "vae": [H3_NODE_VIDEO_VAE, 0],
                "audio_vae": [H3_NODE_AUDIO_VAE, 0],
            },
        },
        H3_NODE_NOISE: {
            "class_type": "RandomNoise",
            "inputs": {"noise_seed": comfy_noise_seed(seed)},
        },
        H3_NODE_SAMPLER_SELECT: {
            "class_type": "KSamplerSelect",
            "inputs": {"sampler_name": H3_REF2V_SAMPLER},
        },
        H3_NODE_SCHEDULER: {
            "class_type": "BasicScheduler",
            "inputs": {
                "scheduler": H3_REF2V_SCHEDULER,
                "steps": steps,
                "denoise": H3_REF2V_DENOISE,
                "model": [H3_NODE_SAGE, 0],
            },
        },
        H3_NODE_GUIDER: {
            "class_type": "BasicGuider",
            "inputs": {
                "model": [H3_NODE_SAGE, 0],
                "conditioning": [H3_NODE_CONDITIONER, 0],
            },
        },
        H3_NODE_SAMPLER: {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": [H3_NODE_NOISE, 0],
                "guider": [H3_NODE_GUIDER, 0],
                "sampler": [H3_NODE_SAMPLER_SELECT, 0],
                "sigmas": [H3_NODE_SCHEDULER, 0],
                "latent_image": [H3_NODE_CONDITIONER, 1],
            },
        },
        H3_NODE_DECODE: {
            "class_type": "VAEDecode",
            "inputs": {"samples": [H3_NODE_SAMPLER, 0], "vae": [H3_NODE_VIDEO_VAE, 0]},
        },
        H3_NODE_DECODE_AUDIO: {
            "class_type": "VAEDecodeAudio",
            "inputs": {"samples": [H3_NODE_SAMPLER, 0], "vae": [H3_NODE_AUDIO_VAE, 0]},
        },
        H3_NODE_CREATE_VIDEO: {
            "class_type": "CreateVideo",
            "inputs": {
                "fps": H3_REF2V_FPS,
                "bit_depth": 8,
                "color_space": "sRGB",
                "images": [H3_NODE_DECODE, 0],
                "audio": [H3_NODE_DECODE_AUDIO, 0],
            },
        },
        H3_NODE_SAVE_VIDEO: {
            "class_type": "SaveVideo",
            "inputs": {
                "filename_prefix": filename_prefix,
                "format": "mp4",
                "format.codec": "auto",
                "codec": "auto",
                "video": [H3_NODE_CREATE_VIDEO, 0],
            },
        },
    }


    if not generate_audio:
        # Silence-locked / generate_audio=false: keep Audio VAE on conditioner
        # (node contract) but do not decode or mux native audio — video only.
        # Disabling native audio also removes ambience (single AV stem).
        graph.pop(H3_NODE_DECODE_AUDIO, None)
        create_in = graph[H3_NODE_CREATE_VIDEO]["inputs"]
        create_in.pop("audio", None)
        # Do not bind voice refs when native audio is disabled.
        # (ref_audio_comfy_names already ignored for mux; skip LoadAudio below)

    if fast:
        graph[H3_FAST_CACHE_NODE_ID] = {
            "class_type": H3_FAST_CACHE_NODE,
            "inputs": {
                "model": [H3_NODE_UNET, 0],
                "reuse_threshold": H3_FAST_REUSE,
                "start_percent": H3_FAST_START,
                "end_percent": H3_FAST_END,
                "verbose": False,
            },
        }
        model_src = [H3_FAST_CACHE_NODE_ID, 0]

    graph[H3_NODE_SAGE] = {
        "class_type": "PathchSageAttentionKJ",
        "inputs": {
            "sage_attention": H3_SAGE_ATTENTION,
            "allow_compile": H3_SAGE_ALLOW_COMPILE,
            "model": model_src,
        },
    }

    cond_in = graph[H3_NODE_CONDITIONER]["inputs"]
    for index, name in enumerate(names):
        node_id = H3_REF_LOADIMAGE_IDS[index]
        graph[node_id] = {"class_type": "LoadImage", "inputs": {"image": name}}
        cond_in[f"ref_images.ref_image_{index}"] = [node_id, 0]

    if generate_audio:
        for index, name in enumerate(audio_names):
            node_id = _next_node_id(graph, start=H3_REF_LOADAUDIO_START + index)
            graph[node_id] = {"class_type": "LoadAudio", "inputs": {"audio": name}}
            cond_in[f"ref_audios.ref_audio_{index}"] = [node_id, 0]

    # Live MiniMaxH3ReferenceToVideo: ref_videos (IMAGE) + optional ref_video_audios (AUDIO), max 3.
    # LoadVideo -> GetVideoComponents demuxes frames/audio for the conditioner sockets.
    for index, name in enumerate(video_names):
        load_id = _next_node_id(graph, start=H3_REF_LOADVIDEO_START + index * 2)
        split_id = _next_node_id(graph, start=int(load_id) + 1)
        graph[load_id] = {"class_type": "LoadVideo", "inputs": {"file": name}}
        graph[split_id] = {"class_type": "GetVideoComponents", "inputs": {"video": [load_id, 0]}}
        cond_in[f"ref_videos.ref_video_{index}"] = [split_id, 0]
        cond_in[f"ref_video_audios.ref_video_audio_{index}"] = [split_id, 1]

    return graph


def assert_h3_ref2v_graph(
    graph: dict[str, Any],
    *,
    expected_names: list[str],
    expected_audio_names: list[str] | None = None,
    expected_video_names: list[str] | None = None,
    expect_fast: bool | None = None,
    expected_prompt: str | None = None,
    expected_width: int | None = None,
    expected_height: int | None = None,
    expected_sampler: str = H3_REF2V_SAMPLER,
    expected_scheduler: str = H3_REF2V_SCHEDULER,
    expected_steps: int | None = None,
    expected_denoise: float = H3_REF2V_DENOISE,
    expected_ref_image_size: str = "match",
) -> None:
    cond_id, cond = find_h3_conditioner(graph)
    if any(
        isinstance(node, dict) and node.get("class_type") == "MiniMaxH3ImageToVideo"
        for node in graph.values()
    ):
        raise ValueError("H3 R2V refused MiniMaxH3ImageToVideo — that is ordinary I2V.")

    unet = ((graph.get(H3_NODE_UNET) or {}).get("inputs") or {}).get("unet_name")
    if unet != H3_REF2VA_UNET:
        raise ValueError(f"H3 R2V requires {H3_REF2VA_UNET}, not {unet}.")
    clip = ((graph.get(H3_NODE_CLIP) or {}).get("inputs") or {}).get("clip_name")
    if clip != H3_CLIP:
        raise ValueError(f"H3 R2V requires {H3_CLIP}, not {clip}.")
    video_vae = ((graph.get(H3_NODE_VIDEO_VAE) or {}).get("inputs") or {}).get("vae_name")
    if video_vae != H3_VIDEO_VAE:
        raise ValueError(f"H3 R2V requires {H3_VIDEO_VAE}, not {video_vae}.")
    audio_vae = ((graph.get(H3_NODE_AUDIO_VAE) or {}).get("inputs") or {}).get("vae_name")
    if audio_vae != H3_AUDIO_VAE:
        raise ValueError(f"H3 R2V requires {H3_AUDIO_VAE}, not {audio_vae}.")

    sage = graph.get(H3_NODE_SAGE) or {}
    if sage.get("class_type") != "PathchSageAttentionKJ":
        raise ValueError("H3 R2V FM4 baseline requires PathchSageAttentionKJ on the model path.")

    cond_in = cond.get("inputs") or {}
    width = int(cond_in.get("width") or 0)
    height = int(cond_in.get("height") or 0)
    if expected_width is not None and width != int(expected_width):
        raise ValueError(f"H3 R2V canvas width {width} != {expected_width}.")
    if expected_height is not None and height != int(expected_height):
        raise ValueError(f"H3 R2V canvas height {height} != {expected_height}.")
    prompt_text = h3_prompt_text(graph)
    if expected_prompt is not None and prompt_text != expected_prompt:
        raise ValueError("H3 R2V Input Text is not the verbatim Timed Prompt.")
    if str(cond_in.get("ref_image_size") or "") != expected_ref_image_size:
        raise ValueError(
            f"H3 R2V ref_image_size {cond_in.get('ref_image_size')!r} != {expected_ref_image_size!r}."
        )

    sampler = ((graph.get(H3_NODE_SAMPLER_SELECT) or {}).get("inputs") or {}).get("sampler_name")
    if sampler != expected_sampler:
        raise ValueError(f"H3 R2V sampler {sampler!r} != {expected_sampler!r}.")
    sched = (graph.get(H3_NODE_SCHEDULER) or {}).get("inputs") or {}
    if sched.get("scheduler") != expected_scheduler:
        raise ValueError(f"H3 R2V scheduler {sched.get('scheduler')!r} != {expected_scheduler!r}.")
    if expected_steps is not None and int(sched.get("steps") or 0) != int(expected_steps):
        raise ValueError(f"H3 R2V steps {sched.get('steps')} != {expected_steps}.")
    if float(sched.get("denoise") or 0) != float(expected_denoise):
        raise ValueError(f"H3 R2V denoise {sched.get('denoise')} != {expected_denoise}.")
    if list(sched.get("model") or []) != [H3_NODE_SAGE, 0]:
        raise ValueError("H3 R2V BasicScheduler must read PathchSageAttentionKJ (FM4).")
    guider = (graph.get(H3_NODE_GUIDER) or {}).get("inputs") or {}
    if list(guider.get("model") or []) != [H3_NODE_SAGE, 0]:
        raise ValueError("H3 R2V BasicGuider must read PathchSageAttentionKJ (FM4).")

    create = (graph.get(H3_NODE_CREATE_VIDEO) or {}).get("inputs") or {}
    if create.get("color_space") != "sRGB":
        raise ValueError("H3 R2V CreateVideo must set color_space=sRGB (FM4).")

    # generate_audio=false graphs omit VAEDecodeAudio and CreateVideo.audio
    has_audio_decode = H3_NODE_DECODE_AUDIO in graph
    if has_audio_decode:
        if "audio" not in create:
            raise ValueError("H3 R2V has VAEDecodeAudio but CreateVideo.audio is missing.")
    else:
        if "audio" in create:
            raise ValueError("H3 R2V generate_audio=false must not mux CreateVideo.audio.")
    save = (graph.get(H3_NODE_SAVE_VIDEO) or {}).get("inputs") or {}
    if save.get("format") != "mp4":
        raise ValueError("H3 R2V SaveVideo must use format=mp4 (FM4).")

    forbidden_accel = {"TeaCache", "MiniMaxH3TeaCache", "HyVideoTeaCache", "WanVideoTeaCache", "WanVideoTeaCacheKJ"}
    has_easy = False
    for node in graph.values():
        if not isinstance(node, dict):
            continue
        ct = str(node.get("class_type") or "")
        if ct in forbidden_accel:
            raise ValueError(f"H3 R2V refused {ct} — that cache is not MiniMax H3.")
        if ct == H3_FAST_CACHE_NODE:
            has_easy = True
    if expect_fast is False and has_easy:
        raise ValueError("H3 Quality (draftMode=false) must not inject EasyCache.")
    if expect_fast is True and not has_easy:
        raise ValueError("H3 Fast/draft requested EasyCache but the graph has none.")
    if expect_fast is True:
        sage_model = list(((graph.get(H3_NODE_SAGE) or {}).get("inputs") or {}).get("model") or [])
        if sage_model != [H3_FAST_CACHE_NODE_ID, 0]:
            raise ValueError("H3 Fast EasyCache is present but SageAttention still reads the raw UNET.")
    if expect_fast is False:
        sage_model = list(((graph.get(H3_NODE_SAGE) or {}).get("inputs") or {}).get("model") or [])
        if sage_model != [H3_NODE_UNET, 0]:
            raise ValueError("H3 Quality PathchSageAttentionKJ must read UNETLoader directly.")

    refs = h3_ref_image_links(graph)
    if not refs:
        raise ValueError("H3 R2V graph has no ref_images.")
    want_names = [str(name).strip() for name in expected_names if str(name or "").strip()]
    bound: list[str] = []
    for index, name in enumerate(want_names):
        key = f"ref_image_{index}"
        link = refs.get(key)
        if not isinstance(link, (list, tuple)) or not link:
            raise ValueError(f"H3 R2V missing {key} for creator order {want_names}.")
        node = graph.get(str(link[0])) or {}
        bound.append(str(((node.get("inputs") or {}).get("image") or "")))
    if bound != want_names:
        raise ValueError(f"H3 R2V LoadImage order {bound} != creator order {want_names}.")
    extra_keys = [
        key
        for key in refs
        if str(key).startswith("ref_image_")
        and key not in {f"ref_image_{i}" for i in range(len(want_names))}
    ]
    if extra_keys:
        raise ValueError(f"H3 R2V has extra LoadImage sockets {extra_keys}.")

    # Flat emit is the FM4 queued form.
    for index in range(len(want_names)):
        flat_key = f"ref_images.ref_image_{index}"
        if flat_key not in cond_in:
            raise ValueError(f"H3 R2V FM4 emit missing flat key {flat_key}.")

    want_audio = [str(name).strip() for name in (expected_audio_names or []) if str(name or "").strip()]
    if want_audio:
        audio_bound: list[str] = []
        for node in graph.values():
            if not isinstance(node, dict) or node.get("class_type") != "LoadAudio":
                continue
            audio_bound.append(str((node.get("inputs") or {}).get("audio") or ""))
        missing_audio = [name for name in want_audio if name not in audio_bound]
        if missing_audio:
            raise ValueError(f"H3 R2V LoadAudio missing uploaded voices: {missing_audio}")
        audio_refs = h3_ref_audio_links(graph)
        if not audio_refs:
            raise ValueError("H3 R2V graph has voice files but no ref_audios.")
    want_video = [str(name).strip() for name in (expected_video_names or []) if str(name or "").strip()]
    if want_video:
        video_bound: list[str] = []
        for node in graph.values():
            if not isinstance(node, dict) or node.get("class_type") != "LoadVideo":
                continue
            video_bound.append(str((node.get("inputs") or {}).get("file") or ""))
        missing_video = [name for name in want_video if name not in video_bound]
        if missing_video:
            raise ValueError(f"H3 R2V LoadVideo missing uploaded videos: {missing_video}")
        video_refs = h3_ref_video_links(graph)
        if not video_refs:
            raise ValueError("H3 R2V graph has video files but no ref_videos.")
        if len(video_refs) != len(want_video):
            raise ValueError(
                f"H3 R2V ref_videos count {len(video_refs)} != uploaded {len(want_video)}."
            )
    _ = cond_id  # reserved for callers / debugging

    _ = cond_id  # reserved for callers / debugging

    _ = cond_id  # reserved for callers / debugging