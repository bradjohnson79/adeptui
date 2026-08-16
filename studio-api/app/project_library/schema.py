"""Dataclasses for Studio Project Library metadata."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


LIBRARY_SCHEMA_VERSION = 2  # M3.1a: Templates and Presets virtual folders


@dataclass
class Classification:
    category: str = ""
    subtype: str = ""
    target_folder: str = ""
    reason: str = ""
    confidence: float = 0.0
    classified_by: str = "auto"
    needs_clarification: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "Classification":
        if not data:
            return cls()
        return cls(
            category=str(data.get("category") or ""),
            subtype=str(data.get("subtype") or ""),
            target_folder=str(data.get("targetFolder") or data.get("target_folder") or ""),
            reason=str(data.get("reason") or ""),
            confidence=float(data.get("confidence") or 0.0),
            classified_by=str(data.get("classifiedBy") or data.get("classified_by") or "auto"),
            needs_clarification=bool(data.get("needsClarification") or data.get("needs_clarification")),
        )


@dataclass
class FolderNode:
    folder_id: str
    display_name: str
    system_key: Optional[str] = None
    parent_folder_id: Optional[str] = None
    display_path: str = ""
    is_system: bool = False
    is_renamable: bool = True
    is_deletable: bool = True
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    entity_name: Optional[str] = None
    children: list["FolderNode"] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "folderId": self.folder_id,
            "displayName": self.display_name,
            "displayPath": self.display_path,
            "isSystem": self.is_system,
            "isRenamable": self.is_renamable,
            "isDeletable": self.is_deletable,
        }
        if self.system_key:
            payload["systemKey"] = self.system_key
        if self.parent_folder_id:
            payload["parentFolderId"] = self.parent_folder_id
        if self.entity_type:
            payload["entityType"] = self.entity_type
        if self.entity_id:
            payload["entityId"] = self.entity_id
        if self.entity_name:
            payload["entityName"] = self.entity_name
        if self.children:
            payload["children"] = [c.to_dict() for c in self.children]
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FolderNode":
        return cls(
            folder_id=str(data.get("folderId") or data.get("folder_id") or ""),
            display_name=str(data.get("displayName") or data.get("display_name") or ""),
            system_key=data.get("systemKey") or data.get("system_key"),
            parent_folder_id=data.get("parentFolderId") or data.get("parent_folder_id"),
            display_path=str(data.get("displayPath") or data.get("display_path") or ""),
            is_system=bool(data.get("isSystem") or data.get("is_system")),
            is_renamable=bool(data.get("isRenamable", data.get("is_renamable", True))),
            is_deletable=bool(data.get("isDeletable", data.get("is_deletable", True))),
            entity_type=data.get("entityType") or data.get("entity_type"),
            entity_id=data.get("entityId") or data.get("entity_id"),
            entity_name=data.get("entityName") or data.get("entity_name"),
        )


@dataclass
class AssetLibraryMeta:
    canonical_folder_id: str = ""
    folder_system_key: str = ""
    library_path: str = ""
    classification: Classification = field(default_factory=Classification)
    character_id: Optional[str] = None
    prop_id: Optional[str] = None
    scene_id: Optional[str] = None
    content_hash: Optional[str] = None
    source_job_id: Optional[str] = None
    provider_output_id: Optional[str] = None
    version: int = 1
    approval_state: str = "draft"
    is_canonical: bool = False
    override: bool = False
    tags: list[str] = field(default_factory=list)
    aspect_ratio: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    quality: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "canonicalFolderId": self.canonical_folder_id,
            "folderSystemKey": self.folder_system_key,
            "libraryPath": self.library_path,
            "classification": self.classification.to_dict(),
            "version": self.version,
            "approvalState": self.approval_state,
            "isCanonical": self.is_canonical,
            "override": self.override,
            "tags": list(self.tags),
        }
        if self.character_id:
            payload["characterId"] = self.character_id
        if self.prop_id:
            payload["propId"] = self.prop_id
        if self.scene_id:
            payload["sceneId"] = self.scene_id
        if self.content_hash:
            payload["contentHash"] = self.content_hash
        if self.source_job_id:
            payload["sourceJobId"] = self.source_job_id
        if self.provider_output_id:
            payload["providerOutputId"] = self.provider_output_id
        if self.aspect_ratio:
            payload["aspectRatio"] = self.aspect_ratio
        if self.width:
            payload["width"] = self.width
        if self.height:
            payload["height"] = self.height
        if self.quality:
            payload["quality"] = self.quality
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "AssetLibraryMeta":
        if not data:
            return cls()
        return cls(
            canonical_folder_id=str(data.get("canonicalFolderId") or data.get("canonical_folder_id") or ""),
            folder_system_key=str(data.get("folderSystemKey") or data.get("folder_system_key") or ""),
            library_path=str(data.get("libraryPath") or data.get("library_path") or ""),
            classification=Classification.from_dict(data.get("classification")),
            character_id=data.get("characterId") or data.get("character_id"),
            prop_id=data.get("propId") or data.get("prop_id"),
            scene_id=data.get("sceneId") or data.get("scene_id"),
            content_hash=data.get("contentHash") or data.get("content_hash"),
            source_job_id=data.get("sourceJobId") or data.get("source_job_id"),
            provider_output_id=data.get("providerOutputId") or data.get("provider_output_id"),
            version=int(data.get("version") or 1),
            approval_state=str(data.get("approvalState") or data.get("approval_state") or "draft"),
            is_canonical=bool(data.get("isCanonical") or data.get("is_canonical")),
            override=bool(data.get("override")),
            tags=list(data.get("tags") or []),
            aspect_ratio=data.get("aspectRatio") or data.get("aspect_ratio"),
            width=int(data["width"]) if data.get("width") else None,
            height=int(data["height"]) if data.get("height") else None,
            quality=data.get("quality"),
        )


@dataclass
class LibraryState:
    schema_version: int = LIBRARY_SCHEMA_VERSION
    folders: dict[str, dict[str, Any]] = field(default_factory=dict)
    migration_log: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "folders": self.folders,
            "migrationLog": self.migration_log,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "LibraryState":
        if not data:
            return cls(schema_version=0)
        return cls(
            schema_version=int(data.get("schemaVersion") or data.get("schema_version") or 0),
            folders=dict(data.get("folders") or {}),
            migration_log=list(data.get("migrationLog") or data.get("migration_log") or []),
        )
