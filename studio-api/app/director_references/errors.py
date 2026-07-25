"""Typed errors for timeline reference bindings."""

from __future__ import annotations


class DirectorReferenceError(Exception):
    def __init__(self, code: str, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "details": self.details}


class FeatureDisabled(DirectorReferenceError):
    def __init__(self) -> None:
        super().__init__(
            "feature_disabled",
            "Timeline references are disabled (STUDIO_FEATURE_TIMELINE_REFERENCES_V1).",
        )


class TimelineItemNotFound(DirectorReferenceError):
    def __init__(self, item_id: str) -> None:
        super().__init__(
            "timeline_item_not_found",
            f"Timeline image item not found: {item_id}",
            details={"itemId": item_id},
        )


class ReferenceAssetNotFound(DirectorReferenceError):
    def __init__(self, asset_id: str) -> None:
        super().__init__(
            "reference_asset_not_found",
            f"Reference asset not found in project: {asset_id}",
            details={"assetId": asset_id},
        )


class ReferenceCycleDetected(DirectorReferenceError):
    def __init__(self, item_id: str, target_item_id: str) -> None:
        super().__init__(
            "reference_cycle_detected",
            "Timeline image references form a cycle.",
            details={"itemId": item_id, "targetItemId": target_item_id},
        )


class InvalidReferenceRole(DirectorReferenceError):
    def __init__(self, role: str) -> None:
        super().__init__(
            "invalid_reference_role",
            f"Invalid reference role: {role}",
            details={"role": role},
        )


class InvalidInfluence(DirectorReferenceError):
    def __init__(self, influence: str) -> None:
        super().__init__(
            "invalid_influence",
            f"Invalid influence level: {influence}",
            details={"influence": influence},
        )


class VersionConflict(DirectorReferenceError):
    def __init__(self, expected: int, actual: int) -> None:
        super().__init__(
            "version_conflict",
            f"Reference set version conflict (expected {expected}, active {actual}).",
            details={"expected": expected, "actual": actual},
        )


class BindingNotFound(DirectorReferenceError):
    def __init__(self, binding_id: str) -> None:
        super().__init__(
            "binding_not_found",
            f"Reference binding not found: {binding_id}",
            details={"bindingId": binding_id},
        )


class PresetNotFound(DirectorReferenceError):
    def __init__(self, preset_id: str) -> None:
        super().__init__(
            "preset_not_found",
            f"Reference preset not found: {preset_id}",
            details={"presetId": preset_id},
        )


class VersionNotFound(DirectorReferenceError):
    def __init__(self, version: int) -> None:
        super().__init__(
            "version_not_found",
            f"Reference set version not found: {version}",
            details={"version": version},
        )
