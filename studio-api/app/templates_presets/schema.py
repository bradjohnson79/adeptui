"""Dataclass models for Templates & Presets + Project Profiles."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .kinds import SCHEMA_VERSION


def _dict(data: Any) -> dict[str, Any]:
    return data if isinstance(data, dict) else {}


def _list(data: Any) -> list[Any]:
    return data if isinstance(data, list) else []


@dataclass
class CreativeItem:
    id: str
    kind: str
    name: str
    slug: str
    scope: str = "project"
    category: str = ""
    subcategory: str = ""
    description: str = ""
    intent: dict[str, Any] = field(default_factory=dict)
    provider_mappings: dict[str, Any] = field(default_factory=dict)
    compatibility: dict[str, Any] = field(default_factory=dict)
    lifecycle: str = "draft"
    approval_state: str = "draft"
    active_version_id: Optional[str] = None
    version: int = 1
    owner_user_id: Optional[str] = None
    project_id: Optional[str] = None
    scene_id: Optional[str] = None
    shot_ref: Optional[str] = None
    parent_item_id: Optional[str] = None
    origin: str = "local"
    visibility: str = "private"
    share_slug: Optional[str] = None
    library_system_key: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "category": self.category,
            "subcategory": self.subcategory,
            "scope": self.scope,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "intent": self.intent,
            "providerMappings": self.provider_mappings,
            "compatibility": self.compatibility,
            "lifecycle": self.lifecycle,
            "approvalState": self.approval_state,
            "activeVersionId": self.active_version_id,
            "version": self.version,
            "ownerUserId": self.owner_user_id,
            "projectId": self.project_id,
            "sceneId": self.scene_id,
            "shotRef": self.shot_ref,
            "parentItemId": self.parent_item_id,
            "origin": self.origin,
            "visibility": self.visibility,
            "shareSlug": self.share_slug,
            "librarySystemKey": self.library_system_key,
            "tags": list(self.tags),
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "schemaVersion": SCHEMA_VERSION,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CreativeItem":
        return cls(
            id=str(data.get("id") or ""),
            kind=str(data.get("kind") or ""),
            category=str(data.get("category") or ""),
            subcategory=str(data.get("subcategory") or ""),
            scope=str(data.get("scope") or "project"),
            name=str(data.get("name") or ""),
            slug=str(data.get("slug") or ""),
            description=str(data.get("description") or ""),
            intent=_dict(data.get("intent")),
            provider_mappings=_dict(data.get("providerMappings") or data.get("provider_mappings")),
            compatibility=_dict(data.get("compatibility")),
            lifecycle=str(data.get("lifecycle") or "draft"),
            approval_state=str(data.get("approvalState") or data.get("approval_state") or "draft"),
            active_version_id=data.get("activeVersionId") or data.get("active_version_id"),
            version=int(data.get("version") or 1),
            owner_user_id=data.get("ownerUserId") or data.get("owner_user_id"),
            project_id=data.get("projectId") or data.get("project_id"),
            scene_id=data.get("sceneId") or data.get("scene_id"),
            shot_ref=data.get("shotRef") or data.get("shot_ref"),
            parent_item_id=data.get("parentItemId") or data.get("parent_item_id"),
            origin=str(data.get("origin") or "local"),
            visibility=str(data.get("visibility") or "private"),
            share_slug=data.get("shareSlug") or data.get("share_slug"),
            library_system_key=str(
                data.get("librarySystemKey") or data.get("library_system_key") or ""
            ),
            tags=[str(t) for t in _list(data.get("tags"))],
            created_at=data.get("createdAt") or data.get("created_at"),
            updated_at=data.get("updatedAt") or data.get("updated_at"),
        )


@dataclass
class CreativeBinding:
    id: str
    project_id: str
    scope_level: str
    slot: str
    item_id: str
    scene_id: Optional[str] = None
    shot_ref: Optional[str] = None
    version_pin: Optional[int] = None
    mode: str = "override"
    expected_version: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "projectId": self.project_id,
            "scopeLevel": self.scope_level,
            "sceneId": self.scene_id,
            "shotRef": self.shot_ref,
            "slot": self.slot,
            "itemId": self.item_id,
            "versionPin": self.version_pin,
            "mode": self.mode,
            "expectedVersion": self.expected_version,
        }


@dataclass
class ResolvedSlot:
    slot: str
    item: Optional[CreativeItem]
    source_scope: str
    inheritance_chain: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "slot": self.slot,
            "item": self.item.to_dict() if self.item else None,
            "sourceScope": self.source_scope,
            "inheritanceChain": list(self.inheritance_chain),
        }


@dataclass
class ResolvedCreativePlan:
    project_id: str
    scene_id: Optional[str]
    shot_ref: Optional[str]
    slots: dict[str, ResolvedSlot] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "projectId": self.project_id,
            "sceneId": self.scene_id,
            "shotRef": self.shot_ref,
            "slots": {k: v.to_dict() for k, v in self.slots.items()},
            "notes": list(self.notes),
            "schemaVersion": SCHEMA_VERSION,
        }


@dataclass
class ProjectStructure:
    season_enabled: bool = False
    episode_enabled: bool = False
    scene_enabled: bool = True
    shot_enabled: bool = True
    trailer_enabled: bool = False
    sequence_enabled: bool = False
    beat_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "seasonEnabled": self.season_enabled,
            "episodeEnabled": self.episode_enabled,
            "sceneEnabled": self.scene_enabled,
            "shotEnabled": self.shot_enabled,
            "trailerEnabled": self.trailer_enabled,
            "sequenceEnabled": self.sequence_enabled,
            "beatEnabled": self.beat_enabled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ProjectStructure":
        d = _dict(data)
        return cls(
            season_enabled=bool(d.get("seasonEnabled") or d.get("season_enabled")),
            episode_enabled=bool(d.get("episodeEnabled") or d.get("episode_enabled")),
            scene_enabled=bool(d.get("sceneEnabled", d.get("scene_enabled", True))),
            shot_enabled=bool(d.get("shotEnabled", d.get("shot_enabled", True))),
            trailer_enabled=bool(d.get("trailerEnabled") or d.get("trailer_enabled")),
            sequence_enabled=bool(d.get("sequenceEnabled") or d.get("sequence_enabled")),
            beat_enabled=bool(d.get("beatEnabled") or d.get("beat_enabled")),
        )


@dataclass
class ProjectProfile:
    project_type: str
    display_name: str
    structure: ProjectStructure = field(default_factory=ProjectStructure)
    defaults: dict[str, Any] = field(default_factory=dict)
    library_emphasis: list[str] = field(default_factory=list)
    recommended_templates: list[str] = field(default_factory=list)
    recommended_camera_presets: list[str] = field(default_factory=list)
    recommended_lighting_presets: list[str] = field(default_factory=list)
    recommended_color_presets: list[str] = field(default_factory=list)
    recommended_look_presets: list[str] = field(default_factory=list)
    bible_sections: list[str] = field(default_factory=list)
    co_director_context: dict[str, Any] = field(default_factory=dict)
    audio_track_defaults: list[str] = field(default_factory=list)
    delivery: list[str] = field(default_factory=list)
    traits: list[str] = field(default_factory=list)
    version: int = 1
    parent_selector: Optional[str] = None
    group: str = ""
    beat_skeleton: list[str] = field(default_factory=list)
    overrides: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "projectType": self.project_type,
            "displayName": self.display_name,
            "structure": self.structure.to_dict(),
            "defaults": dict(self.defaults),
            "libraryEmphasis": list(self.library_emphasis),
            "recommendedTemplates": list(self.recommended_templates),
            "recommendedCameraPresets": list(self.recommended_camera_presets),
            "recommendedLightingPresets": list(self.recommended_lighting_presets),
            "recommendedColorPresets": list(self.recommended_color_presets),
            "recommendedLookPresets": list(self.recommended_look_presets),
            "bibleSections": list(self.bible_sections),
            "coDirectorContext": dict(self.co_director_context),
            "audioTrackDefaults": list(self.audio_track_defaults),
            "delivery": list(self.delivery),
            "traits": list(self.traits),
            "version": self.version,
            "parentSelector": self.parent_selector,
            "group": self.group,
            "beatSkeleton": list(self.beat_skeleton),
            "overrides": dict(self.overrides),
            "schemaVersion": SCHEMA_VERSION,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ProjectProfile":
        d = _dict(data)
        return cls(
            project_type=str(d.get("projectType") or d.get("project_type") or "custom"),
            display_name=str(d.get("displayName") or d.get("display_name") or "Custom Project"),
            structure=ProjectStructure.from_dict(_dict(d.get("structure"))),
            defaults=_dict(d.get("defaults")),
            library_emphasis=[str(x) for x in _list(d.get("libraryEmphasis") or d.get("library_emphasis"))],
            recommended_templates=[
                str(x) for x in _list(d.get("recommendedTemplates") or d.get("recommended_templates"))
            ],
            recommended_camera_presets=[
                str(x)
                for x in _list(d.get("recommendedCameraPresets") or d.get("recommended_camera_presets"))
            ],
            recommended_lighting_presets=[
                str(x)
                for x in _list(
                    d.get("recommendedLightingPresets") or d.get("recommended_lighting_presets")
                )
            ],
            recommended_color_presets=[
                str(x)
                for x in _list(d.get("recommendedColorPresets") or d.get("recommended_color_presets"))
            ],
            recommended_look_presets=[
                str(x)
                for x in _list(d.get("recommendedLookPresets") or d.get("recommended_look_presets"))
            ],
            bible_sections=[str(x) for x in _list(d.get("bibleSections") or d.get("bible_sections"))],
            co_director_context=_dict(d.get("coDirectorContext") or d.get("co_director_context")),
            audio_track_defaults=[
                str(x) for x in _list(d.get("audioTrackDefaults") or d.get("audio_track_defaults"))
            ],
            delivery=[str(x) for x in _list(d.get("delivery"))],
            traits=[str(x) for x in _list(d.get("traits"))],
            version=int(d.get("version") or 1),
            parent_selector=d.get("parentSelector") or d.get("parent_selector"),
            group=str(d.get("group") or ""),
            beat_skeleton=[str(x) for x in _list(d.get("beatSkeleton") or d.get("beat_skeleton"))],
            overrides=_dict(d.get("overrides")),
        )


@dataclass
class ProjectTypeDefinition:
    id: str
    slug: str
    display_name: str
    group: str = ""
    is_builtin: bool = False
    parent_selector: Optional[str] = None
    profile: ProjectProfile = field(default_factory=lambda: ProjectProfile("custom", "Custom"))
    version: int = 1
    lifecycle: str = "approved"
    origin: str = "builtin"
    primary_selector: bool = False
    subtypes: list[str] = field(default_factory=list)
    trait_options: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "slug": self.slug,
            "displayName": self.display_name,
            "group": self.group,
            "isBuiltin": self.is_builtin,
            "parentSelector": self.parent_selector,
            "profile": self.profile.to_dict(),
            "version": self.version,
            "lifecycle": self.lifecycle,
            "origin": self.origin,
            "primarySelector": self.primary_selector,
            "subtypes": list(self.subtypes),
            "traitOptions": list(self.trait_options),
        }
