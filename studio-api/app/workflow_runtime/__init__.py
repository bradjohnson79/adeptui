"""Unified Workflow Resolver facade — video + image registry domains (M42 W1)."""

from __future__ import annotations

from typing import Any, Literal, Union

Modality = Literal["video", "image"]


def resolve_workflow(
    intent: str,
    *,
    modality: Modality = "video",
    engine: str = "ltx",
    present_inputs: dict[str, Any] | None = None,
    paid_fal_approved: bool = False,
    fal_engine: str | None = None,
    wants_ingredients: bool = False,
    force_workflow_key: str | None = None,
    allow_draft: bool = True,
) -> Any:
    """
    Single resolver entrypoint across modality registries.

    Video: existing M41 Certified path (allow_draft ignored; Certified required).
    Image: M42 path — production uses allow_draft=False (Certified required).
    """
    if modality == "image":
        from ..image_runtime.contract import resolve_image_workflow

        return resolve_image_workflow(
            intent,
            engine=engine if engine not in {"ltx", "wan"} else "zimage",
            present_inputs=present_inputs,
            force_workflow_key=force_workflow_key,
            allow_draft=allow_draft,
        )

    from ..video_runtime.workflow_resolver import resolve_workflow as resolve_video

    return resolve_video(
        intent,
        engine=engine,
        present_inputs=present_inputs,
        paid_fal_approved=paid_fal_approved,
        fal_engine=fal_engine,
        wants_ingredients=wants_ingredients,
        force_workflow_key=force_workflow_key,
    )


def list_registry_domains() -> list[str]:
    return ["video", "image"]  # audio / 3d future
