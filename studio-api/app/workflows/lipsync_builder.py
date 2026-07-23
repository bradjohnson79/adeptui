from __future__ import annotations

from typing import Any


def build_latentsync_workflow(
    *,
    video_path: str,
    audio_path: str,
    filename_prefix: str = "studio/lipsync",
    seed: int = 42,
    custom_width: int = 512,
    custom_height: int = 512,
    inference_steps: int = 20,
) -> dict[str, Any]:
    """
    LatentSync post-pass template.
    Requires a LatentSync ComfyUI custom node pack to be installed.
    Common node names vary by pack; this uses LatentSyncNode if present,
    otherwise LoadVideo + placeholder that the worker validates.
    """
    return {
        "1": {
            "class_type": "VHS_LoadVideoPath",
            "inputs": {
                "video": video_path,
                "force_rate": 0,
                "force_size": "Disabled",
                "custom_width": custom_width,
                "custom_height": custom_height,
                "frame_load_cap": 0,
                "skip_first_frames": 0,
                "select_every_nth": 1,
            },
        },
        "2": {
            "class_type": "VHS_LoadAudio",
            "inputs": {"audio_file": audio_path, "seek_seconds": 0, "duration": 0},
        },
        "3": {
            "class_type": "LatentSyncNode",
            "inputs": {
                "images": ["1", 0],
                "audio": ["2", 0],
                "seed": seed,
                "lips_expression": 1.5,
                "inference_steps": inference_steps,
            },
        },
        "4": {
            "class_type": "VHS_VideoCombine",
            "inputs": {
                "images": ["3", 0],
                "audio": ["2", 0],
                "frame_rate": 25,
                "loop_count": 0,
                "filename_prefix": filename_prefix,
                "format": "video/h264-mp4",
                "pingpong": False,
                "save_output": True,
            },
        },
    }


def lipsync_available_hint() -> str:
    return (
        "LatentSync custom nodes are not installed in ComfyUI. "
        "Install a LatentSync ComfyUI pack and models, then retry lip sync."
    )
