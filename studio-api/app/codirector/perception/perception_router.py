"""Task-aware perception routing. Does not use chat route_turn."""

from __future__ import annotations

from typing import Any, Literal

PerceptionTask = Literal[
    "select",
    "remove_background",
    "remove_object",
    "replace_object",
    "protect",
    "track",
    "spatial_place",
    "extract_subject",
]


def plan_perception(task: PerceptionTask, *, depth_available: bool = False) -> dict[str, Any]:
    """Return which models to invoke. Never run every model for every job."""
    need_sam = True
    need_dino = task in {
        "select",
        "remove_object",
        "replace_object",
        "protect",
        "extract_subject",
        "spatial_place",
    }
    if task in {"remove_background", "track"}:
        need_dino = False
    need_depth = task == "spatial_place" and depth_available
    need_track = task == "track"
    return {
        "task": task,
        "sam": need_sam,
        "dino": need_dino,
        "depth": need_depth,
        "track": need_track,
        "jepa": False,
        "videochat": False,
    }


def creator_unavailable_message(missing: str) -> str:
    if missing in {"sam", "dino", "select"}:
        return "Intelligent selection is not installed. Paint the region, or open Setup and install the Adept UI Essentials Pack."
    if missing == "depth":
        return "Near and far help is not installed. You can still select and edit in 2D."
    if missing == "jepa":
        return "World consistency notes are unavailable."
    if missing == "track":
        return "Tracking needs intelligent selection installed."
    return "That capability is not installed."
