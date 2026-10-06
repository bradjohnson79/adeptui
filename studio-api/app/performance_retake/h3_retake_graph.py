"""Performance Retake H3 graph — ref_videos wiring by composition.

`h3_ref2v_builder.py` is untracked foreign work (H3 Timeline mission), so
this module never edits it: it calls `build_h3_ref2v(...)` and injects the
source-video channel into the returned graph dict:

    LoadVideo(file=<staged window>) -> GetVideoComponents
        -> images (output 0) -> MiniMaxH3ReferenceToVideo.ref_videos.ref_video_0
        -> audio  (output 1) -> ref_video_audios.ref_video_audio_0  (opt-in ONLY)

`ref_video_audios` stays UNWIRED by default — feeding the source window's
original audio into the generator risks old-dialogue leak (governing doc §6).
"""

from __future__ import annotations

from typing import Any

from ..workflows.h3_ref2v_builder import (
    assert_h3_ref2v_graph,
    build_h3_ref2v,
    find_h3_conditioner,
)

# Node ids above the builder's LoadAudio range (200+) to avoid collisions.
RETAKE_LOADVIDEO_ID = "300"
RETAKE_VIDEO_COMPONENTS_ID = "301"


class RetakeGraphError(ValueError):
    """The composed retake graph violates the Performance Retake contract."""


def _free_node_id(graph: dict[str, Any], preferred: str) -> str:
    node_id = str(preferred)
    while node_id in graph:
        node_id = str(int(node_id) + 1)
    return node_id


def build_h3_retake_graph(
    *,
    prompt: str,
    ref_comfy_names: list[str],
    ref_video_comfy_name: str,
    filename_prefix: str,
    seed: int = 0,
    width: int = 1152,
    height: int = 640,
    length: int = 5,
    steps: int = 20,
    ref_image_size: str = "match",
    fast: bool = False,
    ref_audio_comfy_names: list[str] | None = None,
    include_source_audio: bool = False,
) -> dict[str, Any]:
    """Build the FM4 H3 R2V graph and inject the source-video reference."""
    video_name = str(ref_video_comfy_name or "").strip()
    if not video_name:
        raise RetakeGraphError(
            "Performance Retake requires the source window video reference "
            "(ref_video_comfy_name)."
        )

    graph = build_h3_ref2v(
        prompt=prompt,
        ref_comfy_names=ref_comfy_names,
        filename_prefix=filename_prefix,
        seed=seed,
        width=width,
        height=height,
        length=length,
        steps=steps,
        ref_image_size=ref_image_size,
        fast=fast,
        ref_audio_comfy_names=ref_audio_comfy_names,
    )

    load_id = _free_node_id(graph, RETAKE_LOADVIDEO_ID)
    graph[load_id] = {"class_type": "LoadVideo", "inputs": {"file": video_name}}
    components_id = _free_node_id(graph, RETAKE_VIDEO_COMPONENTS_ID)
    graph[components_id] = {
        "class_type": "GetVideoComponents",
        "inputs": {"video": [load_id, 0]},
    }

    _, cond = find_h3_conditioner(graph)
    cond_in = cond.setdefault("inputs", {})
    cond_in["ref_videos.ref_video_0"] = [components_id, 0]
    if include_source_audio:
        cond_in["ref_video_audios.ref_video_audio_0"] = [components_id, 1]
    return graph


def assert_h3_retake_graph(
    graph: dict[str, Any],
    *,
    expected_names: list[str],
    expected_video_name: str,
    expected_audio_names: list[str] | None = None,
    expect_source_audio: bool = False,
    expect_fast: bool | None = None,
    expected_prompt: str | None = None,
    expected_width: int | None = None,
    expected_height: int | None = None,
) -> None:
    """FM4 invariants (via assert_h3_ref2v_graph) + retake video channel."""
    assert_h3_ref2v_graph(
        graph,
        expected_names=expected_names,
        expected_audio_names=expected_audio_names,
        expect_fast=expect_fast,
        expected_prompt=expected_prompt,
        expected_width=expected_width,
        expected_height=expected_height,
    )

    load_nodes = [
        (nid, n)
        for nid, n in graph.items()
        if isinstance(n, dict) and n.get("class_type") == "LoadVideo"
    ]
    if len(load_nodes) != 1:
        raise RetakeGraphError(
            f"Retake graph must carry exactly one LoadVideo, found {len(load_nodes)}."
        )
    load_id, load_node = load_nodes[0]
    staged = str((load_node.get("inputs") or {}).get("file") or "")
    if staged != expected_video_name:
        raise RetakeGraphError(
            f"LoadVideo file {staged!r} != staged source window {expected_video_name!r}."
        )

    components = [
        (nid, n)
        for nid, n in graph.items()
        if isinstance(n, dict) and n.get("class_type") == "GetVideoComponents"
    ]
    if len(components) != 1:
        raise RetakeGraphError(
            f"Retake graph must carry exactly one GetVideoComponents, found {len(components)}."
        )
    components_id, components_node = components[0]
    if list((components_node.get("inputs") or {}).get("video") or []) != [load_id, 0]:
        raise RetakeGraphError("GetVideoComponents must read the LoadVideo output.")

    _, cond = find_h3_conditioner(graph)
    cond_in = cond.get("inputs") or {}
    if list(cond_in.get("ref_videos.ref_video_0") or []) != [components_id, 0]:
        raise RetakeGraphError(
            "ref_videos.ref_video_0 must read GetVideoComponents images (output 0)."
        )
    extra_video_keys = [
        key
        for key in cond_in
        if str(key).startswith("ref_videos.ref_video_") and key != "ref_videos.ref_video_0"
    ]
    if extra_video_keys:
        raise RetakeGraphError(f"Unexpected extra ref_videos sockets: {extra_video_keys}.")

    audio_keys = [
        key for key in cond_in if str(key).startswith("ref_video_audios.ref_video_audio_")
    ]
    if expect_source_audio:
        if list(cond_in.get("ref_video_audios.ref_video_audio_0") or []) != [components_id, 1]:
            raise RetakeGraphError(
                "include_source_audio=True requires ref_video_audios.ref_video_audio_0 "
                "on GetVideoComponents audio (output 1)."
            )
    elif audio_keys:
        raise RetakeGraphError(
            "ref_video_audios must stay unwired by default — old-dialogue leak guard."
        )
