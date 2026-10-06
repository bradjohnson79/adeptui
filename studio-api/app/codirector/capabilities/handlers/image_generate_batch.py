"""Capability handler: image.generate_batch — same Image Generator, N stills."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .image_generate import handle as generate_image


def handle(
    db: Session,
    project_id: str,
    execution_id: str,
    *,
    count: int = 4,
    **kwargs: Any,
) -> dict[str, Any]:
    n = max(2, min(int(count or 4), 8))
    return generate_image(
        db,
        project_id,
        execution_id,
        count=n,
        **kwargs,
    )
