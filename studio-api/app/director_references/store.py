"""SQLAlchemy persistence for timeline reference sets (copy-on-write)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from ..db import (
    ReferencePreset,
    ReferencePresetBinding,
    TimelineReferenceBinding,
    TimelineReferenceSet,
    TimelineReferenceSetVersion,
)
from .models import ReferenceBinding, ReferenceSet, ReferenceSetVersion


def _nid() -> str:
    return str(uuid.uuid4())


def _iso(dt: datetime | None) -> str:
    return dt.isoformat() + "Z" if dt else ""


class ReferenceStore:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_set(
        self, project_id: str, scene_id: str, timeline_item_id: str
    ) -> Optional[TimelineReferenceSet]:
        return (
            self.db.query(TimelineReferenceSet)
            .filter(
                TimelineReferenceSet.project_id == project_id,
                TimelineReferenceSet.scene_id == scene_id,
                TimelineReferenceSet.timeline_item_id == timeline_item_id,
            )
            .one_or_none()
        )

    def get_set_by_id(self, set_id: str) -> Optional[TimelineReferenceSet]:
        return self.db.get(TimelineReferenceSet, set_id)

    def ensure_set(
        self, project_id: str, scene_id: str, timeline_item_id: str
    ) -> TimelineReferenceSet:
        existing = self.get_set(project_id, scene_id, timeline_item_id)
        if existing:
            return existing
        row = TimelineReferenceSet(
            id=_nid(),
            project_id=project_id,
            scene_id=scene_id,
            timeline_item_id=timeline_item_id,
            active_version=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(row)
        self.db.flush()
        return row

    def list_bindings(self, version_id: str) -> list[TimelineReferenceBinding]:
        return (
            self.db.query(TimelineReferenceBinding)
            .filter(TimelineReferenceBinding.version_id == version_id)
            .order_by(TimelineReferenceBinding.sort_order, TimelineReferenceBinding.id)
            .all()
        )

    def get_version_row(
        self, set_id: str, version: int
    ) -> Optional[TimelineReferenceSetVersion]:
        return (
            self.db.query(TimelineReferenceSetVersion)
            .filter(
                TimelineReferenceSetVersion.set_id == set_id,
                TimelineReferenceSetVersion.version == version,
            )
            .one_or_none()
        )

    def load_version(self, set_id: str, version: int) -> Optional[ReferenceSetVersion]:
        row = self.get_version_row(set_id, version)
        if not row:
            return None
        bindings = [
            ReferenceBinding(
                id=b.id,
                reference_asset_id=b.reference_asset_id,
                role=b.role,
                influence=b.influence,
                source=b.source,
                bible_entity_stable_id=b.bible_entity_stable_id,
                bible_version_id=b.bible_version_id,
                source_timeline_item_id=b.source_timeline_item_id,
                label=b.label or "",
                notes=b.notes or "",
                sort_order=int(b.sort_order or 0),
            )
            for b in self.list_bindings(row.id)
        ]
        return ReferenceSetVersion(
            set_id=set_id,
            version=row.version,
            status=row.status,
            bindings=bindings,
            created_at=_iso(row.created_at),
            created_by=row.created_by or "user",
        )

    def load_active_set(
        self, project_id: str, scene_id: str, timeline_item_id: str
    ) -> Optional[ReferenceSet]:
        row = self.get_set(project_id, scene_id, timeline_item_id)
        if not row:
            return None
        ver = self.load_version(row.id, row.active_version) if row.active_version else None
        return ReferenceSet(
            id=row.id,
            project_id=row.project_id,
            scene_id=row.scene_id,
            timeline_item_id=row.timeline_item_id,
            active_version=row.active_version,
            version=ver,
        )

    def cow_new_version(
        self,
        set_row: TimelineReferenceSet,
        bindings: list[ReferenceBinding],
        *,
        created_by: str = "user",
    ) -> ReferenceSetVersion:
        new_version = int(set_row.active_version or 0) + 1
        # Mark prior active as superseded
        if set_row.active_version:
            prior = self.get_version_row(set_row.id, set_row.active_version)
            if prior and prior.status == "active":
                prior.status = "superseded"
        ver_row = TimelineReferenceSetVersion(
            id=_nid(),
            set_id=set_row.id,
            version=new_version,
            status="active",
            created_at=datetime.utcnow(),
            created_by=created_by,
        )
        self.db.add(ver_row)
        self.db.flush()
        for i, b in enumerate(bindings):
            # Each COW version gets fresh binding row IDs (prior versions stay immutable).
            new_id = _nid()
            b.id = new_id
            self.db.add(
                TimelineReferenceBinding(
                    id=new_id,
                    version_id=ver_row.id,
                    reference_asset_id=b.reference_asset_id,
                    role=b.role,
                    influence=b.influence,
                    source=b.source,
                    bible_entity_stable_id=b.bible_entity_stable_id,
                    bible_version_id=b.bible_version_id,
                    source_timeline_item_id=b.source_timeline_item_id,
                    label=b.label or "",
                    notes=b.notes or "",
                    sort_order=b.sort_order if b.sort_order is not None else i,
                )
            )
        set_row.active_version = new_version
        set_row.updated_at = datetime.utcnow()
        self.db.flush()
        return ReferenceSetVersion(
            set_id=set_row.id,
            version=new_version,
            status="active",
            bindings=list(bindings),
            created_at=_iso(ver_row.created_at),
            created_by=created_by,
        )

    # --- presets ---
    def list_presets(self, project_id: str) -> list[ReferencePreset]:
        return (
            self.db.query(ReferencePreset)
            .filter(ReferencePreset.project_id == project_id)
            .order_by(ReferencePreset.name)
            .all()
        )

    def get_preset(self, project_id: str, preset_id: str) -> Optional[ReferencePreset]:
        row = self.db.get(ReferencePreset, preset_id)
        if not row or row.project_id != project_id:
            return None
        return row

    def list_preset_bindings(self, preset_id: str) -> list[ReferencePresetBinding]:
        return (
            self.db.query(ReferencePresetBinding)
            .filter(ReferencePresetBinding.preset_id == preset_id)
            .order_by(ReferencePresetBinding.sort_order, ReferencePresetBinding.id)
            .all()
        )

    def create_preset(
        self,
        project_id: str,
        name: str,
        description: str,
        bindings: list[ReferenceBinding],
        *,
        created_by: str = "user",
    ) -> ReferencePreset:
        row = ReferencePreset(
            id=_nid(),
            project_id=project_id,
            name=name,
            description=description or "",
            created_at=datetime.utcnow(),
            created_by=created_by,
        )
        self.db.add(row)
        self.db.flush()
        for i, b in enumerate(bindings):
            self.db.add(
                ReferencePresetBinding(
                    id=_nid(),
                    preset_id=row.id,
                    reference_asset_id=b.reference_asset_id,
                    role=b.role,
                    influence=b.influence,
                    source=b.source,
                    bible_entity_stable_id=b.bible_entity_stable_id,
                    bible_version_id=b.bible_version_id,
                    label=b.label or "",
                    notes=b.notes or "",
                    sort_order=i,
                )
            )
        self.db.flush()
        return row
