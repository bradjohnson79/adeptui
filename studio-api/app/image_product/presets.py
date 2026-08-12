"""Image Session Presets — project-scoped reusable generation presets (M42 W3)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4

from .store import read_json, write_json

BUILTIN_PRESETS: list[dict[str, Any]] = [
    {
        "presetId": "builtin-concept-art",
        "name": "Concept Art",
        "builtin": True,
        "preferredModelFamily": "flux",
        "aspectRatio": "16:9",
        "qualityPreset": "high",
        "resolution": "1080p",
        "guidance": 3.5,
        "promptTemplate": "Cinematic concept art, production design, {subject}",
        "defaultReferenceAssetTypes": ["style", "environment"],
    },
    {
        "presetId": "builtin-storyboard",
        "name": "Storyboard",
        "builtin": True,
        "preferredModelFamily": "zimage",
        "aspectRatio": "16:9",
        "qualityPreset": "standard",
        "resolution": "1080p",
        "guidance": 2.0,
        "promptTemplate": "Storyboard frame, clear silhouette, {subject}",
        "defaultReferenceAssetTypes": ["character", "composition"],
    },
    {
        "presetId": "builtin-character-sheet",
        "name": "Character Sheet",
        "builtin": True,
        "preferredModelFamily": "zimage",
        "aspectRatio": "1:1",
        "qualityPreset": "high",
        "resolution": "1080p",
        "guidance": 2.5,
        "promptTemplate": "Character turnaround sheet, consistent identity, {subject}",
        "defaultReferenceAssetTypes": ["character", "wardrobe"],
    },
    {
        "presetId": "builtin-environment-sheet",
        "name": "Environment Sheet",
        "builtin": True,
        "preferredModelFamily": "flux",
        "aspectRatio": "16:9",
        "qualityPreset": "high",
        "resolution": "1080p",
        "guidance": 3.0,
        "promptTemplate": "Environment design sheet, location reference, {subject}",
        "defaultReferenceAssetTypes": ["environment", "lighting"],
    },
    {
        "presetId": "builtin-marketing",
        "name": "Marketing Artwork",
        "builtin": True,
        "preferredModelFamily": "flux",
        "aspectRatio": "16:9",
        "qualityPreset": "high",
        "resolution": "2K",
        "guidance": 4.0,
        "promptTemplate": "Marketing key art, polished, {subject}",
        "defaultReferenceAssetTypes": ["style", "character"],
    },
    {
        "presetId": "builtin-youtube-thumb",
        "name": "YouTube Thumbnail",
        "builtin": True,
        "preferredModelFamily": "zimage",
        "aspectRatio": "16:9",
        "qualityPreset": "standard",
        "resolution": "1080p",
        "guidance": 3.0,
        "promptTemplate": "Bold YouTube thumbnail, readable at small size, {subject}",
        "defaultReferenceAssetTypes": ["composition", "style"],
    },
    {
        "presetId": "builtin-poster",
        "name": "Poster",
        "builtin": True,
        "preferredModelFamily": "flux",
        "aspectRatio": "2:3",
        "qualityPreset": "high",
        "resolution": "2K",
        "guidance": 4.0,
        "promptTemplate": "Theatrical poster composition, {subject}",
        "defaultReferenceAssetTypes": ["style", "character", "composition"],
    },
    {
        "presetId": "builtin-matte",
        "name": "Matte Painting",
        "builtin": True,
        "preferredModelFamily": "flux",
        "aspectRatio": "21:9",
        "qualityPreset": "high",
        "resolution": "2K",
        "guidance": 3.5,
        "promptTemplate": "Matte painting, epic environment, {subject}",
        "defaultReferenceAssetTypes": ["environment", "lighting", "palette"],
    },
]


def list_presets(project_id: str) -> list[dict[str, Any]]:
    custom = read_json(project_id, "presets.json", {"presets": []})
    customs = list(custom.get("presets") or [])
    return deepcopy(BUILTIN_PRESETS) + customs


def get_preset(project_id: str, preset_id: str) -> dict[str, Any] | None:
    for p in list_presets(project_id):
        if p.get("presetId") == preset_id:
            return p
    return None


def create_preset(project_id: str, body: dict[str, Any]) -> dict[str, Any]:
    data = read_json(project_id, "presets.json", {"presets": []})
    preset = {
        "presetId": str(body.get("presetId") or f"preset-{uuid4().hex[:10]}"),
        "name": str(body.get("name") or "Custom Preset"),
        "builtin": False,
        "preferredModelFamily": body.get("preferredModelFamily") or "zimage",
        "aspectRatio": body.get("aspectRatio") or "1:1",
        "qualityPreset": body.get("qualityPreset") or "standard",
        "resolution": body.get("resolution") or "1080p",
        "guidance": body.get("guidance"),
        "promptTemplate": body.get("promptTemplate") or "{subject}",
        "defaultReferenceAssetTypes": list(body.get("defaultReferenceAssetTypes") or []),
    }
    data.setdefault("presets", []).append(preset)
    write_json(project_id, "presets.json", data)
    return preset


def update_preset(project_id: str, preset_id: str, body: dict[str, Any]) -> dict[str, Any] | None:
    if preset_id.startswith("builtin-"):
        raise RuntimeError("Cannot mutate built-in presets; save a copy instead")
    data = read_json(project_id, "presets.json", {"presets": []})
    for i, p in enumerate(data.get("presets") or []):
        if p.get("presetId") == preset_id:
            p.update({k: v for k, v in body.items() if k != "builtin" and k != "presetId"})
            data["presets"][i] = p
            write_json(project_id, "presets.json", data)
            return p
    return None


def delete_preset(project_id: str, preset_id: str) -> bool:
    if preset_id.startswith("builtin-"):
        raise RuntimeError("Cannot delete built-in presets")
    data = read_json(project_id, "presets.json", {"presets": []})
    before = len(data.get("presets") or [])
    data["presets"] = [p for p in (data.get("presets") or []) if p.get("presetId") != preset_id]
    write_json(project_id, "presets.json", data)
    return len(data["presets"]) < before


def apply_preset_to_request(preset: dict[str, Any], subject: str = "") -> dict[str, Any]:
    tmpl = str(preset.get("promptTemplate") or "{subject}")
    prompt = tmpl.replace("{subject}", subject or "subject")
    return {
        "modelFamilyPreference": preset.get("preferredModelFamily") or "zimage",
        "aspectRatio": preset.get("aspectRatio") or "1:1",
        "quality": preset.get("qualityPreset") or "standard",
        "resolution": preset.get("resolution") or "1080p",
        "guidance": preset.get("guidance"),
        "prompt": prompt,
        "defaultReferenceAssetTypes": list(preset.get("defaultReferenceAssetTypes") or []),
        "presetId": preset.get("presetId"),
        "presetName": preset.get("name"),
    }
