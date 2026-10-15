"""Immutable Production Context for closed-loop / job-graph orchestration (M2.7.1 / M011).

Created once at closed-loop start. Sparse optional fields are omitted when unknown.
Later facts are recorded via append-only context extensions (+ audit events), never by
mutating the original context row/JSON.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from ...db import ProductionContextExtension, ProductionContextRow, ProductionJobEvent


@dataclass(frozen=True)
class ProductionContext:
    """Immutable production context snapshot."""

    id: str
    projectId: str
    sceneId: str
    createdAt: str
    shotId: Optional[str] = None
    storyboardId: Optional[str] = None
    timelineId: Optional[str] = None
    productionBibleVersion: Optional[str] = None
    referenceSetVersion: Optional[str] = None
    cinematicDNA: Optional[Any] = None
    workflowVersion: Optional[str] = None
    executionManifestId: Optional[str] = None
    initiatedBy: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        data = {
            "id": self.id,
            "projectId": self.projectId,
            "sceneId": self.sceneId,
            "createdAt": self.createdAt,
            "shotId": self.shotId,
            "storyboardId": self.storyboardId,
            "timelineId": self.timelineId,
            "productionBibleVersion": self.productionBibleVersion,
            "referenceSetVersion": self.referenceSetVersion,
            "cinematicDNA": self.cinematicDNA,
            "workflowVersion": self.workflowVersion,
            "executionManifestId": self.executionManifestId,
            "initiatedBy": self.initiatedBy,
        }
        return {k: v for k, v in data.items() if v is not None}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ProductionContext":
        if not raw.get("projectId") or not raw.get("sceneId") or not raw.get("createdAt"):
            raise ValueError("ProductionContext requires projectId, sceneId, createdAt")
        ctx_id = str(raw.get("id") or "")
        if not ctx_id:
            raise ValueError("ProductionContext requires id")
        return cls(
            id=ctx_id,
            projectId=str(raw["projectId"]),
            sceneId=str(raw["sceneId"]),
            createdAt=str(raw["createdAt"]),
            shotId=str(raw["shotId"]) if raw.get("shotId") is not None else None,
            storyboardId=str(raw["storyboardId"]) if raw.get("storyboardId") is not None else None,
            timelineId=str(raw["timelineId"]) if raw.get("timelineId") is not None else None,
            productionBibleVersion=(
                str(raw["productionBibleVersion"])
                if raw.get("productionBibleVersion") is not None
                else None
            ),
            referenceSetVersion=(
                str(raw["referenceSetVersion"])
                if raw.get("referenceSetVersion") is not None
                else None
            ),
            cinematicDNA=raw.get("cinematicDNA"),
            workflowVersion=(
                str(raw["workflowVersion"]) if raw.get("workflowVersion") is not None else None
            ),
            executionManifestId=(
                str(raw["executionManifestId"])
                if raw.get("executionManifestId") is not None
                else None
            ),
            initiatedBy=str(raw["initiatedBy"]) if raw.get("initiatedBy") is not None else None,
        )


def _iso(dt: datetime | None = None) -> str:
    return (dt or datetime.utcnow()).isoformat() + "Z"


def create_production_context(
    db: Session,
    *,
    project_id: str,
    scene_id: str,
    initiated_by: str | None = None,
    shot_id: str | None = None,
    storyboard_id: str | None = None,
    timeline_id: str | None = None,
    production_bible_version: str | None = None,
    reference_set_version: str | None = None,
    cinematic_dna: Any = None,
    workflow_version: str | None = None,
    execution_manifest_id: str | None = None,
    created_at: datetime | None = None,
) -> ProductionContext:
    """Insert an immutable ProductionContext row once and return the frozen snapshot."""
    now = created_at or datetime.utcnow()
    ctx_id = str(uuid.uuid4())
    ctx = ProductionContext(
        id=ctx_id,
        projectId=project_id,
        sceneId=scene_id,
        createdAt=_iso(now),
        shotId=shot_id,
        storyboardId=storyboard_id,
        timelineId=timeline_id,
        productionBibleVersion=production_bible_version,
        referenceSetVersion=reference_set_version,
        cinematicDNA=cinematic_dna,
        workflowVersion=workflow_version,
        executionManifestId=execution_manifest_id,
        initiatedBy=initiated_by,
    )
    snapshot = ctx.to_dict()
    row = ProductionContextRow(
        id=ctx_id,
        project_id=project_id,
        scene_id=scene_id,
        context_json=json.dumps(snapshot, default=str),
        initiated_by=initiated_by,
        created_at=now,
    )
    db.add(row)
    db.add(
        ProductionJobEvent(
            id=str(uuid.uuid4()),
            job_id=None,
            project_id=project_id,
            event_type="production_context.created",
            payload_json=json.dumps({"contextId": ctx_id, "sceneId": scene_id}, default=str),
            created_at=now,
        )
    )
    db.commit()
    db.refresh(row)
    return ctx


def load_production_context(db: Session, context_id: str) -> ProductionContext | None:
    row = db.get(ProductionContextRow, context_id)
    if not row:
        return None
    try:
        raw = json.loads(row.context_json or "{}")
    except json.JSONDecodeError:
        raw = {}
    if "id" not in raw:
        raw["id"] = row.id
    if "projectId" not in raw:
        raw["projectId"] = row.project_id
    if "sceneId" not in raw:
        raw["sceneId"] = row.scene_id
    if "createdAt" not in raw:
        raw["createdAt"] = _iso(row.created_at)
    if row.initiated_by and "initiatedBy" not in raw:
        raw["initiatedBy"] = row.initiated_by
    return ProductionContext.from_dict(raw)


def append_context_extension(
    db: Session,
    context_id: str,
    *,
    extension_type: str,
    payload: dict[str, Any],
    actor: str,
) -> dict[str, Any]:
    """Append-only context extension with an audit event. Does not mutate the context row."""
    row = db.get(ProductionContextRow, context_id)
    if not row:
        raise ValueError(f"production context not found: {context_id}")
    now = datetime.utcnow()
    ext_id = str(uuid.uuid4())
    ext = ProductionContextExtension(
        id=ext_id,
        context_id=context_id,
        extension_type=extension_type,
        payload_json=json.dumps(payload or {}, default=str),
        actor=actor,
        created_at=now,
    )
    db.add(ext)
    db.add(
        ProductionJobEvent(
            id=str(uuid.uuid4()),
            job_id=None,
            project_id=row.project_id,
            event_type="production_context.extension",
            payload_json=json.dumps(
                {
                    "contextId": context_id,
                    "extensionId": ext_id,
                    "extensionType": extension_type,
                    "actor": actor,
                    "payload": payload or {},
                },
                default=str,
            ),
            created_at=now,
        )
    )
    db.commit()
    return {
        "id": ext_id,
        "contextId": context_id,
        "extensionType": extension_type,
        "payload": payload or {},
        "actor": actor,
        "createdAt": _iso(now),
    }


def list_context_extensions(db: Session, context_id: str) -> list[dict[str, Any]]:
    rows = (
        db.query(ProductionContextExtension)
        .filter(ProductionContextExtension.context_id == context_id)
        .order_by(ProductionContextExtension.created_at.asc())
        .all()
    )
    out: list[dict[str, Any]] = []
    for r in rows:
        try:
            payload = json.loads(r.payload_json or "{}")
        except json.JSONDecodeError:
            payload = {}
        out.append(
            {
                "id": r.id,
                "contextId": r.context_id,
                "extensionType": r.extension_type,
                "payload": payload,
                "actor": r.actor,
                "createdAt": _iso(r.created_at),
            }
        )
    return out