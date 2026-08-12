"""Import/export packages for creative items and project types."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from .compatibility import compatibility_report
from .kinds import CREATIVE_ITEM_PACKAGE, PROJECT_TYPE_PACKAGE, SCHEMA_VERSION
from .schema import CreativeItem, ProjectProfile, ProjectTypeDefinition


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _checksum(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def export_creative_item(item: CreativeItem) -> dict[str, Any]:
    body = {
        "format": CREATIVE_ITEM_PACKAGE,
        "schemaVersion": SCHEMA_VERSION,
        "exportedAt": _now(),
        "item": item.to_dict(),
    }
    body["checksum"] = _checksum({"item": body["item"], "format": body["format"]})
    body["compatibility"] = compatibility_report(item)
    return body


def import_creative_item(package: dict[str, Any]) -> tuple[CreativeItem, dict[str, Any]]:
    if not isinstance(package, dict):
        raise ValueError("package must be an object")
    fmt = package.get("format")
    if fmt and fmt != CREATIVE_ITEM_PACKAGE:
        raise ValueError(f"unsupported package format: {fmt}")
    item_data = package.get("item")
    if not isinstance(item_data, dict):
        raise ValueError("package.item is required")
    expected = package.get("checksum")
    if expected:
        actual = _checksum({"item": item_data, "format": CREATIVE_ITEM_PACKAGE})
        if actual != expected:
            raise ValueError("checksum_mismatch")
    item = CreativeItem.from_dict(item_data)
    report = compatibility_report(item)
    return item, report


def export_project_type(definition: ProjectTypeDefinition) -> dict[str, Any]:
    body = {
        "format": PROJECT_TYPE_PACKAGE,
        "schemaVersion": SCHEMA_VERSION,
        "exportedAt": _now(),
        "definition": definition.to_dict(),
    }
    body["checksum"] = _checksum({"definition": body["definition"], "format": body["format"]})
    return body


def import_project_type(package: dict[str, Any]) -> ProjectTypeDefinition:
    if not isinstance(package, dict):
        raise ValueError("package must be an object")
    fmt = package.get("format")
    if fmt and fmt != PROJECT_TYPE_PACKAGE:
        raise ValueError(f"unsupported package format: {fmt}")
    data = package.get("definition")
    if not isinstance(data, dict):
        raise ValueError("package.definition is required")
    expected = package.get("checksum")
    if expected:
        actual = _checksum({"definition": data, "format": PROJECT_TYPE_PACKAGE})
        if actual != expected:
            raise ValueError("checksum_mismatch")
    profile = ProjectProfile.from_dict(data.get("profile") or {})
    return ProjectTypeDefinition(
        id=str(data.get("id") or ""),
        slug=str(data.get("slug") or ""),
        display_name=str(data.get("displayName") or data.get("display_name") or ""),
        group=str(data.get("group") or ""),
        is_builtin=bool(data.get("isBuiltin") or data.get("is_builtin")),
        parent_selector=data.get("parentSelector") or data.get("parent_selector"),
        profile=profile,
        version=int(data.get("version") or 1),
        lifecycle=str(data.get("lifecycle") or "approved"),
        origin=str(data.get("origin") or "imported"),
        primary_selector=bool(data.get("primarySelector") or data.get("primary_selector")),
        subtypes=[str(x) for x in (data.get("subtypes") or [])],
        trait_options=[str(x) for x in (data.get("traitOptions") or data.get("trait_options") or [])],
    )
