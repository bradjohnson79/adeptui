"""Domain models for timeline reference bindings (non-ORM)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class ReferenceBinding:
    id: str
    reference_asset_id: str
    role: str
    influence: str = "moderate"
    source: str = "project_asset"
    bible_entity_stable_id: Optional[str] = None
    bible_version_id: Optional[str] = None
    source_timeline_item_id: Optional[str] = None
    label: str = ""
    notes: str = ""
    sort_order: int = 0

    def to_public(self) -> dict[str, Any]:
        return {
            "bindingId": self.id,
            "referenceAssetId": self.reference_asset_id,
            "role": self.role,
            "influence": self.influence,
            "source": self.source,
            "bibleEntityStableId": self.bible_entity_stable_id,
            "bibleVersionId": self.bible_version_id,
            "sourceTimelineItemId": self.source_timeline_item_id,
            "label": self.label,
            "notes": self.notes,
            "sortOrder": self.sort_order,
        }


@dataclass
class ReferenceSetVersion:
    set_id: str
    version: int
    status: str
    bindings: list[ReferenceBinding] = field(default_factory=list)
    created_at: str = ""
    created_by: str = "user"

    def to_public(self) -> dict[str, Any]:
        return {
            "setId": self.set_id,
            "version": self.version,
            "status": self.status,
            "bindings": [b.to_public() for b in self.bindings],
            "createdAt": self.created_at,
            "createdBy": self.created_by,
            "count": len(self.bindings),
        }


@dataclass
class ReferenceSet:
    id: str
    project_id: str
    scene_id: str
    timeline_item_id: str
    active_version: int
    version: Optional[ReferenceSetVersion] = None

    def to_public(self) -> dict[str, Any]:
        payload = {
            "id": self.id,
            "projectId": self.project_id,
            "sceneId": self.scene_id,
            "timelineItemId": self.timeline_item_id,
            "activeVersion": self.active_version,
            "count": len(self.version.bindings) if self.version else 0,
        }
        if self.version:
            payload["version"] = self.version.to_public()
            payload["bindings"] = [b.to_public() for b in self.version.bindings]
        else:
            payload["bindings"] = []
        return payload
