"""Capability handler: image.edit — same Image Generator pipeline, edit path."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .image_generate import handle as generate_image


def handle(
    db: Session,
    project_id: str,
    execution_id: str,
    *,
    prompt: str = "",
    source_asset_id: str = "",
    attachment_asset_ids: list[str] | None = None,
    reference_asset_id: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    source = (
        str(source_asset_id or reference_asset_id or "").strip()
        or next((str(x).strip() for x in (attachment_asset_ids or []) if x), "")
    )
    if not source:
        return {
            "error": "I need the picture to edit. Attach it or point to the last image.",
            "child_jobs": [],
        }
    attachments = list(attachment_asset_ids or [])
    if source not in attachments:
        attachments.insert(0, source)
    kwargs.pop("source_asset_id", None)
    kwargs.pop("reference_asset_id", None)
    return generate_image(
        db,
        project_id,
        execution_id,
        prompt=prompt,
        attachment_asset_ids=attachments,
        **kwargs,
    )
