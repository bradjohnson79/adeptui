"""Register completed scene-render MP4s into the open project's Library.

1 Frame / 3 Frame / Timeline all write a file. Library hydration is not
optional — a done job without an Asset row is an incomplete generation.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..db import Asset


def register_render_output_asset(
    db: Session,
    *,
    project_id: str,
    dest: Path | str,
    tag: str,
    prompt_meta: dict[str, Any] | None = None,
) -> Asset:
    """Idempotent Library row for a render that already exists on disk."""
    path = Path(dest)
    if not path.is_file():
        raise FileNotFoundError(f"Render output is missing: {path}")
    stored = str(path)
    existing = (
        db.query(Asset)
        .filter(Asset.project_id == project_id, Asset.path == stored)
        .first()
    )
    if existing:
        if prompt_meta and (existing.prompt_meta_json or "").strip() in {"", "{}"}:
            existing.prompt_meta_json = json.dumps(prompt_meta)
            db.add(existing)
        return existing
    asset = Asset(
        id=str(uuid.uuid4()),
        project_id=project_id,
        kind="video",
        filename=path.name,
        path=stored,
        tag=(tag or "")[:64],
        prompt_meta_json=json.dumps(prompt_meta or {}),
    )
    db.add(asset)
    db.flush()
    return asset
