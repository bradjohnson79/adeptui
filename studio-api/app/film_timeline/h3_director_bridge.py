"""H3 Director Bridge — Adept Timeline → MiniMaxH3Director ComfyUI workflow.

Translates Adept V2 Film Timeline data (via existing orchestrator contracts) into
a ComfyUI workflow JSON that runs ``MiniMaxH3Director`` in headless external-group
mode. Adept owns creative intent, reference names, duration, resolution, Omni
continuity intelligence, and tail/last-frame context. Director owns H3 segmented
execution, AV decode, and export.

This bridge is the ONLY MiniMax H3 Local execution authority. No dual-stack.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("film_timeline.h3_director_bridge")

# ---------------------------------------------------------------------------
# ComfyUI node classes (verified against live Comfy :8188 object_info)
# ---------------------------------------------------------------------------
DIRECTOR_NODE = "MiniMaxH3Director"
GROUP_R2V_NODE = "MiniMaxH3DirectorGroupReferenceToVideo"
GROUPS_COMBINE_NODE = "MiniMaxH3DirectorGroupsCombine"
UNET_LOADER = "UNETLoader"
VAE_LOADER = "VAELoader"
CLIP_LOADER = "CLIPLoader"
LOAD_IMAGE = "LoadImage"
LOAD_VIDEO = "LoadVideo"
GET_VIDEO_COMPONENTS = "GetVideoComponents"
LOAD_AUDIO = "LoadAudio"
PREVIEW_IMAGE = "PreviewImage"
CREATE_VIDEO = "CreateVideo"
SAVE_VIDEO = "SaveVideo"

# Director defaults that Adept does not expose
DIRECTOR_DEFAULTS = {
    "steps": 25,
    "sampler_name": "res_multistep",
    "scheduler": "simple",
    "shift_video": 12.0,
    "shift_audio": 3.0,
    "cfg": 1.0,
}

# Canonical H3 model identifiers
H3_REF2VA_UNET = "minimax_h3_ref2va_pruned_int8_convrot.safetensors"
H3_VIDEO_VAE = "minimax_h3_video_vae_fp16.safetensors"
H3_AUDIO_VAE = "minimax_h3_audio_vae_fp32.safetensors"
H3_CLIP_NAME = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
H3_CLIP_TYPE = "minimax"

# task_type label for Director (must match live Comfy combo option)
TASK_TYPE_R2V = "r2v — 参考主体生视频(Reference to Video)"

# Node ID ranges
_NID_UNET = 1
_NID_VIDEO_VAE = 2
_NID_AUDIO_VAE = 3
_NID_CLIP = 4
_NID_DIRECTOR = 10
_NID_GROUPS_COMBINE = 11
_NID_PREVIEW = 99
_NID_CREATE_VIDEO = 90
_NID_SAVE_VIDEO = 91
# Per-group: node id = _NID_GROUP_BASE + (group_index * 100)
_NID_GROUP_BASE = 100
# Reference loaders per group: offset from group base
_REF_IMAGE_OFFSET = 0
_REF_VIDEO_OFFSET = 20
_REF_AUDIO_OFFSET = 40


@dataclass
class DirectorGroup:
    """One segment-equivalent external group for Director r2v_groups."""
    prompt: str
    duration_sec: int  # whole seconds — Adept canonical
    ref_images: dict[int, str] = field(default_factory=dict)  # index → Comfy filename
    ref_videos: dict[int, str] = field(default_factory=dict)  # index → Comfy filename
    ref_audios: dict[int, str] = field(default_factory=dict)  # index → Comfy filename


@dataclass
class DirectorPlan:
    """Complete H3 Director execution plan from Adept Timeline data."""
    width: int = 1152
    height: int = 640
    fps: float = 24.0
    seed: int = 0
    groups: list[DirectorGroup] = field(default_factory=list)
    continuity_enabled: bool = False
    # Native Director continuity (timeline.output.*) — see segment_continuity.py
    continuity_overlap: int = 22
    continuity_mode: str = "continue"  # guide | continue (latent)
    continuity_keep_tail: bool = True
    continuity_redraw: float = 0.10
    # When set, Director runSelectEnabled samples only these group indices.
    run_selection: list[int] | None = None
    # segments = export only last run segment IMAGE (needed for Adept +N continue)
    export_mode: str = "all"


# ---------------------------------------------------------------------------
# Comfy graph helpers
# ---------------------------------------------------------------------------
def _node(id_: int, class_type: str, inputs: dict[str, Any], meta: dict[str, Any] | None = None) -> dict[str, Any]:
    m = meta or {}
    m["title"] = m.get("title", class_type)
    return {"id": id_, "type": class_type, "inputs": inputs, "_meta": m}


def _next_id(used: set[int], start: int) -> int:
    while start in used:
        start += 1
    return start


def _duration_to_director_frames(duration_sec: int, fps: float = 24.0) -> int:
    raw = int(float(duration_sec) * float(fps))
    return max(4, min(raw, int(20 * fps)))

# ---------------------------------------------------------------------------
# Primary bridge function
# ---------------------------------------------------------------------------

def _director_timeline_data(plan: DirectorPlan) -> dict[str, Any]:
    """Build timeline_data matching live MiniMaxH3Director schema.

    Live Director reads continuity from ``output.continuityEnabled`` (and related
    output.* keys), NOT from a top-level ``continuity`` object. Continuity only
    activates when segment_count >= 2 (see segment_continuity.resolve_continuity_settings).
    """
    output: dict[str, Any] = {
        "mode": "fixed",
        "width": int(plan.width),
        "height": int(plan.height),
        "exportMode": str(plan.export_mode or "all"),
    }
    if plan.continuity_enabled:
        output["continuityEnabled"] = True
        output["continuityOverlapFrames"] = int(plan.continuity_overlap or 22)
        output["continuityMode"] = str(plan.continuity_mode or "continue")
        output["continuityKeepTail"] = bool(plan.continuity_keep_tail)
        output["continuityRedraw"] = float(plan.continuity_redraw)
    timeline: dict[str, Any] = {
        "editMode": "segment",
        "width": int(plan.width),
        "height": int(plan.height),
        "frameRate": float(plan.fps),
        "refImageSize": "match",
        "output": output,
        # Diagnostic mirror for Adept evidence; Director ignores this key.
        "continuity": {
            "enabled": bool(plan.continuity_enabled),
            "overlap": int(plan.continuity_overlap or 22) if plan.continuity_enabled else 0,
            "mode": str(plan.continuity_mode or "continue"),
            "redraw": float(plan.continuity_redraw) if plan.continuity_enabled else 0,
            "keepTail": bool(plan.continuity_keep_tail) if plan.continuity_enabled else False,
        },
    }
    if plan.run_selection is not None:
        timeline["runSelectEnabled"] = True
        timeline["runSelection"] = [int(i) for i in plan.run_selection]
    return timeline


def seed_director_prev_segment_cache(
    *,
    prior_video: Path | str,
    node_id: str = "10",
    output_dir: Path | str | None = None,
    fps: float = 24.0,
) -> Path:
    """Seed MiniMaxH3Director seg_0000 frame cache from a prior Adept segment MP4.

    Native Continue across separate Adept jobs has no in-session prev segment.
    Director resolves prev via ``minimax_seg_cache/<node_id>/seg_0000.frames.mkv``
    with ``allow_stale=True``. Adept seeds that slot from the finished prior MP4
    so group-1 can pin the **tail** (``prev_output[-overlap:]``) — never the opening.
    """
    import shutil
    import subprocess

    src = Path(prior_video)
    if not src.is_file():
        raise FileNotFoundError(f"H3 Director continue seed: prior video missing: {src}")
    if output_dir is None:
        out = Path(r"C:/Users/bradj/AppData/Local/Comfy-Desktop/ComfyUI-Shared/output")
    else:
        out = Path(output_dir)
    cache_root = out / "minimax_seg_cache" / str(node_id)
    cache_root.mkdir(parents=True, exist_ok=True)
    dest = cache_root / "seg_0000.frames.mkv"
    ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if not ffmpeg:
        raise RuntimeError("H3 Director continue seed: ffmpeg not found on PATH.")
    cmd = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(src),
        "-an",
        "-c:v",
        "ffv1",
        "-level",
        "3",
        "-pix_fmt",
        "bgr0",
        "-r",
        f"{float(fps):.6f}",
        "-f",
        "matroska",
        str(dest),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not dest.is_file() or dest.stat().st_size <= 0:
        raise RuntimeError(
            f"H3 Director continue seed failed (code={proc.returncode}): "
            f"{(proc.stderr or proc.stdout or 'unknown')[:400]}"
        )
    meta = cache_root / "seg_0000.meta.json"
    meta.write_text(
        json.dumps(
            {
                "adept_seeded": True,
                "source": str(src),
                "fps": float(fps),
                "note": "Film Timeline Continue prior segment for native Director continuity",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    log.info(
        "h3-director-bridge seeded seg_0000 cache from %s -> %s (%d bytes)",
        src,
        dest,
        dest.stat().st_size,
    )
    return dest


def build_director_workflow(
    plan: DirectorPlan,
    *,
    seed: int | None = None,
) -> dict[str, Any]:
    """Build a ComfyUI workflow JSON that runs MiniMaxH3Director.

    Graph structure:
        LoadImage(s) ──┐
        LoadVideo(s) ──┤
        LoadAudio(s) ──┤
                       ├──> GroupR2V(0..N)
        UNETLoader  ──┤                           ─┐
        VAELoader(v)──┤                            ├──> GroupsCombine ──> Director ──> PreviewImage
        VAELoader(a)──┤                            │
        CLIPLoader  ──┘                            │
                       ────────────────────────────┘
    """
    use_seed = int(seed) if seed is not None else int(plan.seed)
    nodes: dict[int, dict[str, Any]] = {}  # id → node
    used_ids: set[int] = set()

    # --- Loader nodes ---
    for nid, ctype, inputs in [
        (_NID_UNET, UNET_LOADER, {"unet_name": H3_REF2VA_UNET, "weight_dtype": "default"}),
        (_NID_VIDEO_VAE, VAE_LOADER, {"vae_name": H3_VIDEO_VAE}),
        (_NID_AUDIO_VAE, VAE_LOADER, {"vae_name": H3_AUDIO_VAE}),
        (_NID_CLIP, CLIP_LOADER, {"clip_name": H3_CLIP_NAME, "type": H3_CLIP_TYPE}),
    ]:
        nodes[nid] = _node(nid, ctype, inputs)
        used_ids.add(nid)

    # --- Build each group with its reference loaders ---
    group_node_ids: list[int] = []
    for gi, group in enumerate(plan.groups):
        base = _NID_GROUP_BASE + (gi * 100)
        group_id = base
        used_ids.add(group_id)

        group_inputs: dict[str, Any] = {
            "prompt": group.prompt,
            "duration_sec": float(group.duration_sec),
            "ref_image_size": "match",
        }

        # Reference images: LoadImage → Group R2V via autogrow flat key
        for idx, filename in sorted(group.ref_images.items()):
            lid = _next_id(used_ids, base + _REF_IMAGE_OFFSET + idx)
            used_ids.add(lid)
            nodes[lid] = _node(lid, LOAD_IMAGE, {"image": filename})
            group_inputs[f"ref_images.ref_image_{idx}"] = [lid, 0]

        # Reference videos: LoadVideo → GetVideoComponents → Group R2V
        for idx, filename in sorted(group.ref_videos.items()):
            vid_id = _next_id(used_ids, base + _REF_VIDEO_OFFSET + idx * 2)
            split_id = _next_id(used_ids, vid_id + 1)
            used_ids.add(vid_id)
            used_ids.add(split_id)
            nodes[vid_id] = _node(vid_id, LOAD_VIDEO, {"file": filename})
            nodes[split_id] = _node(split_id, GET_VIDEO_COMPONENTS, {"video": [vid_id, 0]})
            group_inputs[f"ref_videos.ref_video_{idx}"] = [split_id, 0]
            group_inputs[f"ref_video_audios.ref_video_audio_{idx}"] = [split_id, 1]

        # Reference audios: LoadAudio → Group R2V
        for idx, filename in sorted(group.ref_audios.items()):
            aid = _next_id(used_ids, base + _REF_AUDIO_OFFSET + idx)
            used_ids.add(aid)
            nodes[aid] = _node(aid, LOAD_AUDIO, {"audio": filename})
            group_inputs[f"ref_audios.ref_audio_{idx}"] = [aid, 0]

        nodes[group_id] = _node(group_id, GROUP_R2V_NODE, group_inputs)
        group_node_ids.append(group_id)

    # --- Groups Combine ---
    used_ids.add(_NID_GROUPS_COMBINE)
    combine_inputs: dict[str, Any] = {}
    for i, gid in enumerate(group_node_ids):
        combine_inputs[f"groups.group_{i}"] = [gid, 0]
    nodes[_NID_GROUPS_COMBINE] = _node(_NID_GROUPS_COMBINE, GROUPS_COMBINE_NODE, combine_inputs)

    # --- Director node ---
    used_ids.add(_NID_DIRECTOR)
    total_frames = sum(_duration_to_director_frames(g.duration_sec, plan.fps) for g in plan.groups)

    director_inputs: dict[str, Any] = {
        "model": [_NID_UNET, 0],
        "video_vae": [_NID_VIDEO_VAE, 0],
        "audio_vae": [_NID_AUDIO_VAE, 0],
        "clip": [_NID_CLIP, 0],
        "task_type": TASK_TYPE_R2V,
        "global_prompt": "",
        "cfg": DIRECTOR_DEFAULTS["cfg"],
        "seed": use_seed,
        "frame_rate": float(plan.fps),
        "width": int(plan.width),
        "height": int(plan.height),
        "ref_max_size": 2048,
        "total_frames": total_frames,
        "timeline_data": json.dumps(_director_timeline_data(plan)),
        "steps": DIRECTOR_DEFAULTS["steps"],
        "sampler": DIRECTOR_DEFAULTS["sampler_name"],
        "scheduler": DIRECTOR_DEFAULTS["scheduler"],
        "shift_video": DIRECTOR_DEFAULTS["shift_video"],
        "shift_audio": DIRECTOR_DEFAULTS["shift_audio"],
        "clear_vram_between_segments": True,
        "export_source_images": False,
        "export_pre_face_refine": False,
        "r2v_groups": [_NID_GROUPS_COMBINE, 0],
        "bd_grp_sample": "采样设置",   # BDGROUP — UI-only label, not a link
    }
    # widgets_values: positional mapping for non-link required inputs
    #     task_type, global_prompt, cfg, seed, frame_rate, width, height,
    #     ref_max_size, total_frames, timeline_data
    nodes[_NID_DIRECTOR] = {
        "id": _NID_DIRECTOR,
        "type": DIRECTOR_NODE,
        "inputs": director_inputs,
        "widgets_values": [
            TASK_TYPE_R2V,     # task_type
            "",                 # global_prompt
            DIRECTOR_DEFAULTS["cfg"],  # cfg
            use_seed,           # seed
            float(plan.fps),    # frame_rate
            int(plan.width),    # width
            int(plan.height),   # height
            2048,               # ref_max_size
            total_frames,       # total_frames
            "",                 # timeline_data
        ],
        "_meta": {"title": "H3 Director (Adept Bridge)"},
    }

    # --- PreviewImage (live progress) + CreateVideo/SaveVideo (ingestable MP4) ---
    # Director outputs IMAGE+AUDIO (+fps); Adept find_output_files needs a SaveVideo
    # artifact. Mirror h3_ref2v_builder: CreateVideo(color_space=sRGB) -> SaveVideo(mp4).
    used_ids.add(_NID_PREVIEW)
    nodes[_NID_PREVIEW] = _node(_NID_PREVIEW, PREVIEW_IMAGE, {
        "images": [_NID_DIRECTOR, 0],
    })
    used_ids.add(_NID_CREATE_VIDEO)
    nodes[_NID_CREATE_VIDEO] = _node(_NID_CREATE_VIDEO, CREATE_VIDEO, {
        "images": [_NID_DIRECTOR, 0],
        "fps": [_NID_DIRECTOR, 2],
        "audio": [_NID_DIRECTOR, 1],
        "bit_depth": 8,
        "color_space": "sRGB",
    })
    used_ids.add(_NID_SAVE_VIDEO)
    nodes[_NID_SAVE_VIDEO] = _node(_NID_SAVE_VIDEO, SAVE_VIDEO, {
        "filename_prefix": "adept_h3_director",
        "format": "mp4",
        "format.codec": "auto",
        "codec": "auto",
        "video": [_NID_CREATE_VIDEO, 0],
    })

    # --- Assemble into ComfyUI API format ---
    # Comfy /prompt expects flat dict: {"1": {"class_type": ..., "inputs": ...}}
    api_graph: dict[str, dict[str, Any]] = {}
    for nid, node in sorted(nodes.items()):
        # Convert link IDs from int to str for Comfy API
        converted_inputs: dict[str, Any] = {}
        for k, v in node["inputs"].items():
            if isinstance(v, list) and len(v) == 2 and isinstance(v[0], int):
                converted_inputs[k] = [str(v[0]), v[1]]
            else:
                converted_inputs[k] = v
        entry: dict[str, Any] = {
            "class_type": node["type"],
            "inputs": converted_inputs,
        }
        if "widgets_values" in node:
            entry["widgets_values"] = node["widgets_values"]
        api_graph[str(nid)] = entry
    return api_graph


# ---------------------------------------------------------------------------
# Duration helpers
# ---------------------------------------------------------------------------
def resolve_output_to_whole_seconds(
    output_paths: list[str],
    duration_sec: int,
    fps: float = 24.0,
) -> list[str]:
    """Trim Director output to the exact creator-requested whole-second duration."""
    target_frames = int(float(duration_sec) * float(fps))
    log.info(
        "h3-director-bridge trim-to-duration: target=%ds (%d frames @ %.1f fps), outputs=%d",
        duration_sec, target_frames, fps, len(output_paths),
    )
    return output_paths