from __future__ import annotations

"""LatentSync workflow builders for Adept Studio.

hay86/ComfyUI_LatentSync registers the node as ``D_LatentSyncNode`` with:
  - video_path: STRING (absolute path)
  - audio: AUDIO
  - seed: INT
  - returns: STRING video_path

Legacy packs may expose ``LatentSyncNode`` with image tensors; the worker probes
object_info and selects the matching builder.
"""

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
    node_class: str = "D_LatentSyncNode",
) -> dict[str, Any]:
    """Build a LatentSync ComfyUI graph for the installed pack."""
    _ = (filename_prefix, custom_width, custom_height, inference_steps)  # pack-specific

    if node_class == "D_LatentSyncNode":
        # hay86 pack: LoadAudio -> D_LatentSyncNode(video_path STRING, audio AUDIO)
        # D_LatentSyncNode is not an OUTPUT_NODE; PreviewAny terminates the graph for Comfy.
        return {
            "1": {
                "class_type": "LoadAudio",
                "inputs": {"audio": audio_path},
            },
            "2": {
                "class_type": "D_LatentSyncNode",
                "inputs": {
                    "video_path": video_path,
                    "audio": ["1", 0],
                    "seed": seed,
                },
            },
            "3": {
                "class_type": "PreviewAny",
                "inputs": {"source": ["2", 0]},
            },
        }

    # Legacy image-tensor LatentSyncNode (VHS loaders)
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
        "Install ComfyUI_LatentSync (D_LatentSyncNode) and checkpoints, then retry lip sync."
    )


def preferred_lipsync_node(available: set[str] | None) -> str | None:
    if not available:
        return None
    if "D_LatentSyncNode" in available:
        return "D_LatentSyncNode"
    if "LatentSyncNode" in available:
        return "LatentSyncNode"
    return None
