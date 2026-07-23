from __future__ import annotations

import re
from dataclasses import dataclass

TAG_RE = re.compile(r"@([A-Za-z0-9_\-]+)")


@dataclass
class ResolvedPrompt:
    prompt: str
    resolved_tags: dict[str, str]
    missing_tags: list[str]
    attached_asset_ids: list[str]


def extract_tags(text: str) -> list[str]:
    return list(dict.fromkeys(TAG_RE.findall(text or "")))


def resolve_prompt(text: str, tag_to_asset: dict[str, tuple[str, str]]) -> ResolvedPrompt:
    """
    tag_to_asset maps tag -> (asset_id, description_or_path)
    Leaves @tags in the prompt for readability but returns attached assets.
    """
    tags = extract_tags(text)
    resolved: dict[str, str] = {}
    missing: list[str] = []
    attached: list[str] = []
    for tag in tags:
        if tag in tag_to_asset:
            asset_id, label = tag_to_asset[tag]
            resolved[tag] = label
            attached.append(asset_id)
        else:
            missing.append(tag)
    return ResolvedPrompt(
        prompt=text or "",
        resolved_tags=resolved,
        missing_tags=missing,
        attached_asset_ids=list(dict.fromkeys(attached)),
    )


def inject_spatial_and_camera(prompt: str, camera_note: str = "", spatial_notes: str = "") -> str:
    parts = [prompt.strip()] if prompt and prompt.strip() else []
    if camera_note.strip():
        parts.append(f"Camera: {camera_note.strip()}")
    if spatial_notes.strip():
        parts.append(f"Set continuity: {spatial_notes.strip()}")
    return " ".join(parts)
