"""Timeline reference set service (item-specific, COW mutations)."""

from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..db import Asset, Scene
from ..director_timeline import ImageClip, parse_director_timeline
from ..director_references.tags import ensure_tags, find_clip_by_tag
from ..feature_flags import feature_flags
from .errors import (
    BindingNotFound,
    FeatureDisabled,
    InvalidInfluence,
    InvalidReferenceRole,
    PresetNotFound,
    ReferenceAssetNotFound,
    ReferenceCycleDetected,
    TimelineItemNotFound,
    VersionConflict,
    VersionNotFound,
)
from .influence import is_valid_influence
from .models import ReferenceBinding, ReferenceSet
from .roles import is_valid_role
from .store import ReferenceStore


def _nid() -> str:
    return str(uuid.uuid4())


class TimelineReferenceService:
    """Item-specific Reference Sets. No Project/Sequence/Scene auto-inheritance in M2.6.

    Extension points (documented, not implemented):
    - Project defaults: seed from project-level ingredient packs
    - Sequence inheritance: walk editor sequence parents
    - Scene ingredients: merge scene-scoped VisualReferences when hierarchy is reliable
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.store = ReferenceStore(db)

    def require_flag(self) -> None:
        if not feature_flags.timeline_references_v1:
            raise FeatureDisabled()

    def _scene(self, project_id: str, scene_id: str) -> Scene:
        scene = self.db.get(Scene, scene_id)
        if not scene or scene.project_id != project_id:
            raise TimelineItemNotFound(scene_id)
        return scene

    def _timeline(self, scene: Scene):
        tl = parse_director_timeline(
            scene.director_json,
            fallback_duration=scene.duration_sec or 5.0,
            fallback_prompt=scene.prompt or "",
        )
        return ensure_tags(tl)

    def _image_clip(self, scene: Scene, item_id: str) -> ImageClip:
        tl = self._timeline(scene)
        for clip in tl.image_clips:
            if clip.id == item_id:
                return clip
        raise TimelineItemNotFound(item_id)

    def _assert_asset(self, project_id: str, asset_id: str) -> Asset:
        asset = self.db.get(Asset, asset_id)
        if not asset or asset.project_id != project_id:
            raise ReferenceAssetNotFound(asset_id)
        return asset

    def _detect_cycle(
        self,
        project_id: str,
        scene_id: str,
        item_id: str,
        source_timeline_item_id: Optional[str],
    ) -> None:
        if not source_timeline_item_id:
            return
        if source_timeline_item_id == item_id:
            raise ReferenceCycleDetected(item_id, source_timeline_item_id)
        # Walk outbound timeline-image refs from the candidate source.
        visited: set[str] = {item_id}
        stack = [source_timeline_item_id]
        while stack:
            cur = stack.pop()
            if cur in visited:
                raise ReferenceCycleDetected(item_id, cur)
            visited.add(cur)
            active = self.store.load_active_set(project_id, scene_id, cur)
            if not active or not active.version:
                continue
            for b in active.version.bindings:
                if b.source_timeline_item_id:
                    stack.append(b.source_timeline_item_id)

    def get_references(
        self, project_id: str, scene_id: str, item_id: str
    ) -> dict[str, Any]:
        self.require_flag()
        scene = self._scene(project_id, scene_id)
        clip = self._image_clip(scene, item_id)
        ref_set = self.store.load_active_set(project_id, scene_id, item_id)
        if not ref_set:
            return {
                "timelineItemId": item_id,
                "displayTag": clip.display_tag,
                "primaryAssetId": clip.asset_id,
                "id": None,
                "activeVersion": 0,
                "count": 0,
                "bindings": [],
            }
        payload = ref_set.to_public()
        payload["displayTag"] = clip.display_tag
        payload["primaryAssetId"] = clip.asset_id
        return payload

    def add_binding(
        self,
        project_id: str,
        scene_id: str,
        item_id: str,
        *,
        reference_asset_id: str,
        role: str,
        influence: str = "moderate",
        source: str = "project_asset",
        bible_entity_stable_id: Optional[str] = None,
        bible_version_id: Optional[str] = None,
        source_timeline_item_id: Optional[str] = None,
        label: str = "",
        notes: str = "",
        created_by: str = "user",
    ) -> dict[str, Any]:
        self.require_flag()
        scene = self._scene(project_id, scene_id)
        self._image_clip(scene, item_id)
        if not is_valid_role(role):
            raise InvalidReferenceRole(role)
        if not is_valid_influence(influence):
            raise InvalidInfluence(influence)
        self._assert_asset(project_id, reference_asset_id)
        self._detect_cycle(project_id, scene_id, item_id, source_timeline_item_id)

        set_row = self.store.ensure_set(project_id, scene_id, item_id)
        current = self.store.load_version(set_row.id, set_row.active_version) if set_row.active_version else None
        bindings = list(current.bindings) if current else []
        bindings.append(
            ReferenceBinding(
                id=_nid(),
                reference_asset_id=reference_asset_id,
                role=role,
                influence=influence,
                source=source,
                bible_entity_stable_id=bible_entity_stable_id,
                bible_version_id=bible_version_id,
                source_timeline_item_id=source_timeline_item_id,
                label=label or "",
                notes=notes or "",
                sort_order=len(bindings),
            )
        )
        self.store.cow_new_version(set_row, bindings, created_by=created_by)
        self.db.commit()
        return self.get_references(project_id, scene_id, item_id)

    def patch_binding(
        self,
        project_id: str,
        scene_id: str,
        item_id: str,
        binding_id: str,
        *,
        role: Optional[str] = None,
        influence: Optional[str] = None,
        label: Optional[str] = None,
        notes: Optional[str] = None,
        sort_order: Optional[int] = None,
        expected_version: Optional[int] = None,
        created_by: str = "user",
    ) -> dict[str, Any]:
        self.require_flag()
        scene = self._scene(project_id, scene_id)
        self._image_clip(scene, item_id)
        set_row = self.store.get_set(project_id, scene_id, item_id)
        if not set_row or not set_row.active_version:
            raise BindingNotFound(binding_id)
        if expected_version is not None and expected_version != set_row.active_version:
            raise VersionConflict(expected_version, set_row.active_version)
        current = self.store.load_version(set_row.id, set_row.active_version)
        if not current:
            raise BindingNotFound(binding_id)
        found = False
        new_bindings: list[ReferenceBinding] = []
        for b in current.bindings:
            if b.id != binding_id:
                new_bindings.append(b)
                continue
            found = True
            if role is not None:
                if not is_valid_role(role):
                    raise InvalidReferenceRole(role)
                b.role = role
            if influence is not None:
                if not is_valid_influence(influence):
                    raise InvalidInfluence(influence)
                b.influence = influence
            if label is not None:
                b.label = label
            if notes is not None:
                b.notes = notes
            if sort_order is not None:
                b.sort_order = sort_order
            new_bindings.append(
                ReferenceBinding(
                    id=b.id,
                    reference_asset_id=b.reference_asset_id,
                    role=b.role,
                    influence=b.influence,
                    source=b.source,
                    bible_entity_stable_id=b.bible_entity_stable_id,
                    bible_version_id=b.bible_version_id,
                    source_timeline_item_id=b.source_timeline_item_id,
                    label=b.label,
                    notes=b.notes,
                    sort_order=b.sort_order,
                )
            )
        if not found:
            raise BindingNotFound(binding_id)
        self.store.cow_new_version(set_row, new_bindings, created_by=created_by)
        self.db.commit()
        return self.get_references(project_id, scene_id, item_id)

    def delete_binding(
        self,
        project_id: str,
        scene_id: str,
        item_id: str,
        binding_id: str,
        *,
        created_by: str = "user",
    ) -> dict[str, Any]:
        self.require_flag()
        scene = self._scene(project_id, scene_id)
        self._image_clip(scene, item_id)
        set_row = self.store.get_set(project_id, scene_id, item_id)
        if not set_row or not set_row.active_version:
            raise BindingNotFound(binding_id)
        current = self.store.load_version(set_row.id, set_row.active_version)
        if not current:
            raise BindingNotFound(binding_id)
        new_bindings = [b for b in current.bindings if b.id != binding_id]
        if len(new_bindings) == len(current.bindings):
            raise BindingNotFound(binding_id)
        self.store.cow_new_version(set_row, new_bindings, created_by=created_by)
        self.db.commit()
        return self.get_references(project_id, scene_id, item_id)

    def clear(
        self,
        project_id: str,
        scene_id: str,
        item_id: str,
        *,
        expected_version: Optional[int] = None,
        created_by: str = "user",
    ) -> dict[str, Any]:
        self.require_flag()
        scene = self._scene(project_id, scene_id)
        self._image_clip(scene, item_id)
        set_row = self.store.ensure_set(project_id, scene_id, item_id)
        if expected_version is not None and expected_version != set_row.active_version:
            raise VersionConflict(expected_version, set_row.active_version)
        self.store.cow_new_version(set_row, [], created_by=created_by)
        self.db.commit()
        return self.get_references(project_id, scene_id, item_id)

    def restore_version(
        self,
        project_id: str,
        scene_id: str,
        item_id: str,
        version: int,
        *,
        expected_version: Optional[int] = None,
        created_by: str = "user",
    ) -> dict[str, Any]:
        self.require_flag()
        scene = self._scene(project_id, scene_id)
        self._image_clip(scene, item_id)
        set_row = self.store.get_set(project_id, scene_id, item_id)
        if not set_row:
            raise VersionNotFound(version)
        if expected_version is not None and expected_version != set_row.active_version:
            raise VersionConflict(expected_version, set_row.active_version)
        prior = self.store.load_version(set_row.id, version)
        if not prior:
            raise VersionNotFound(version)
        # COW restore: copy prior bindings into a new version.
        restored = [
            ReferenceBinding(
                id=_nid(),
                reference_asset_id=b.reference_asset_id,
                role=b.role,
                influence=b.influence,
                source=b.source,
                bible_entity_stable_id=b.bible_entity_stable_id,
                bible_version_id=b.bible_version_id,
                source_timeline_item_id=b.source_timeline_item_id,
                label=b.label,
                notes=b.notes,
                sort_order=b.sort_order,
            )
            for b in prior.bindings
        ]
        self.store.cow_new_version(set_row, restored, created_by=created_by)
        self.db.commit()
        return self.get_references(project_id, scene_id, item_id)

    def continuity_previous(
        self, project_id: str, scene_id: str, item_id: str, *, created_by: str = "user"
    ) -> dict[str, Any]:
        """Attach nearest prior approved frame as continuity, or report unavailable."""
        self.require_flag()
        scene = self._scene(project_id, scene_id)
        clip = self._image_clip(scene, item_id)
        tl = self._timeline(scene)
        # Prefer production_approval == approved on project assets earlier on the timeline.
        candidates = sorted(
            [c for c in tl.image_clips if c.id != item_id and (c.start + c.length) <= clip.start + 1e-6],
            key=lambda c: c.start + c.length,
            reverse=True,
        )
        approved_asset_id = None
        source_item_id = None
        for c in candidates:
            if not c.asset_id:
                continue
            asset = self.db.get(Asset, c.asset_id)
            if not asset or asset.project_id != project_id:
                continue
            approval = getattr(asset, "production_approval", None) or "none"
            if approval == "approved":
                approved_asset_id = c.asset_id
                source_item_id = c.id
                break
        if not approved_asset_id:
            return {
                "ok": False,
                "available": False,
                "reason": "no_approved_prior_frame",
                "message": "No nearest approved prior timeline frame is available.",
            }
        result = self.add_binding(
            project_id,
            scene_id,
            item_id,
            reference_asset_id=approved_asset_id,
            role="continuity",
            influence="strong",
            source="approved_frame",
            source_timeline_item_id=source_item_id,
            label="Continuity (previous approved)",
            created_by=created_by,
        )
        return {"ok": True, "available": True, "references": result}

    def list_presets(self, project_id: str) -> list[dict[str, Any]]:
        self.require_flag()
        out = []
        for p in self.store.list_presets(project_id):
            bindings = self.store.list_preset_bindings(p.id)
            out.append(
                {
                    "presetId": p.id,
                    "projectId": p.project_id,
                    "name": p.name,
                    "description": p.description or "",
                    "count": len(bindings),
                    "bindings": [
                        {
                            "referenceAssetId": b.reference_asset_id,
                            "role": b.role,
                            "influence": b.influence,
                            "source": b.source,
                            "bibleEntityStableId": b.bible_entity_stable_id,
                            "bibleVersionId": b.bible_version_id,
                            "label": b.label or "",
                            "notes": b.notes or "",
                            "sortOrder": b.sort_order,
                        }
                        for b in bindings
                    ],
                }
            )
        return out

    def create_preset(
        self,
        project_id: str,
        name: str,
        description: str,
        binding_specs: list[dict[str, Any]],
        *,
        created_by: str = "user",
    ) -> dict[str, Any]:
        self.require_flag()
        bindings: list[ReferenceBinding] = []
        for i, spec in enumerate(binding_specs):
            role = spec.get("role", "other")
            influence = spec.get("influence", "moderate")
            asset_id = spec.get("referenceAssetId") or spec.get("reference_asset_id")
            if not asset_id:
                continue
            if not is_valid_role(role):
                raise InvalidReferenceRole(role)
            if not is_valid_influence(influence):
                raise InvalidInfluence(influence)
            self._assert_asset(project_id, asset_id)
            bindings.append(
                ReferenceBinding(
                    id=_nid(),
                    reference_asset_id=asset_id,
                    role=role,
                    influence=influence,
                    source=spec.get("source", "project_asset"),
                    bible_entity_stable_id=spec.get("bibleEntityStableId"),
                    bible_version_id=spec.get("bibleVersionId"),
                    label=spec.get("label") or "",
                    notes=spec.get("notes") or "",
                    sort_order=i,
                )
            )
        row = self.store.create_preset(
            project_id, name, description, bindings, created_by=created_by
        )
        self.db.commit()
        presets = self.list_presets(project_id)
        return next(p for p in presets if p["presetId"] == row.id)

    def apply_preset(
        self,
        project_id: str,
        scene_id: str,
        item_id: str,
        preset_id: str,
        *,
        mode: str = "replace",
        expected_version: Optional[int] = None,
        created_by: str = "user",
    ) -> dict[str, Any]:
        self.require_flag()
        scene = self._scene(project_id, scene_id)
        self._image_clip(scene, item_id)
        preset = self.store.get_preset(project_id, preset_id)
        if not preset:
            raise PresetNotFound(preset_id)
        set_row = self.store.ensure_set(project_id, scene_id, item_id)
        if expected_version is not None and expected_version != set_row.active_version:
            raise VersionConflict(expected_version, set_row.active_version)
        preset_bindings = self.store.list_preset_bindings(preset.id)
        incoming = [
            ReferenceBinding(
                id=_nid(),
                reference_asset_id=b.reference_asset_id,
                role=b.role,
                influence=b.influence,
                source=b.source,
                bible_entity_stable_id=b.bible_entity_stable_id,
                bible_version_id=b.bible_version_id,
                label=b.label or "",
                notes=b.notes or "",
                sort_order=b.sort_order,
            )
            for b in preset_bindings
        ]
        if mode == "merge" and set_row.active_version:
            current = self.store.load_version(set_row.id, set_row.active_version)
            existing = list(current.bindings) if current else []
            # Deduplicate by asset+role
            seen = {(b.reference_asset_id, b.role) for b in existing}
            for b in incoming:
                key = (b.reference_asset_id, b.role)
                if key not in seen:
                    existing.append(b)
                    seen.add(key)
            bindings = existing
        else:
            bindings = incoming
        self.store.cow_new_version(set_row, bindings, created_by=created_by)
        self.db.commit()
        return self.get_references(project_id, scene_id, item_id)

    def resolve_tag(self, project_id: str, scene_id: str, tag: str) -> dict[str, Any]:
        self.require_flag()
        scene = self._scene(project_id, scene_id)
        tl = self._timeline(scene)
        clip = find_clip_by_tag(tl.image_clips, tag)
        if not clip:
            raise TimelineItemNotFound(tag)
        refs = self.store.load_active_set(project_id, scene_id, clip.id)
        return {
            "timelineItemId": clip.id,
            "displayTag": clip.display_tag,
            "assetId": clip.asset_id,
            "start": clip.start,
            "length": clip.length,
            "referenceSet": refs.to_public() if refs else None,
        }
