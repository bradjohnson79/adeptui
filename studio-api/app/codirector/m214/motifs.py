"""Production motifs across visual / sonic / narrative."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from .contracts import ProductionMotif
from .db import ensure_m214_tables
from .store import _jid, _now


def create_motif(
    db: Session,
    *,
    project_id: str,
    name: str,
    kind: str = "visual",
    description: str = "",
    scene_id: str = "",
    linked_media_ids: Optional[list[str]] = None,
) -> dict[str, Any]:
    ensure_m214_tables()
    motif = ProductionMotif(
        project_id=project_id,
        scene_id=scene_id,
        name=name,
        kind=kind,
        description=description,
        linked_media_ids=linked_media_ids or [],
    )
    db.execute(
        text(
            "INSERT INTO m214_production_motifs "
            "(id, project_id, scene_id, name, kind, motif_json, created_at) "
            "VALUES (:id, :pid, :sid, :name, :kind, :j, :ts)"
        ),
        {
            "id": motif.id,
            "pid": project_id,
            "sid": scene_id,
            "name": name,
            "kind": kind,
            "j": _jid(motif.to_dict()),
            "ts": _now(),
        },
    )
    db.commit()
    return motif.to_dict()
