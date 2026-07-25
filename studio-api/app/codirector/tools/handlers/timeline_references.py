"""Co-Director tools for timeline images and reference sets (M2.6)."""

from __future__ import annotations

import re
from typing import Any

from ....director_references.errors import DirectorReferenceError, FeatureDisabled
from ....director_references.package import ReferencePackageBuilder
from ....director_references.service import TimelineReferenceService
from ....director_references.tags import ensure_tags, find_clip_by_tag, parse_tag_number
from ....director_timeline import parse_director_timeline
from ....db import Scene
from ....feature_flags import feature_flags
from ..definitions import ToolContext, ToolPreview

_TAG_IN_TEXT = re.compile(r"@Image\d+", re.I)


def _require_enabled() -> None:
    if not feature_flags.timeline_references_v1:
        raise FeatureDisabled()


def _scene(ctx: ToolContext, scene_id: str) -> Scene:
    scene = ctx.db.get(Scene, scene_id)
    if not scene or scene.project_id != ctx.project_id:
        raise DirectorReferenceError("timeline_item_not_found", f"Scene not found: {scene_id}")
    return scene


def _timeline(scene: Scene):
    return ensure_tags(
        parse_director_timeline(
            scene.director_json,
            fallback_duration=scene.duration_sec or 5.0,
            fallback_prompt=scene.prompt or "",
        )
    )


async def get_timeline_image(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _require_enabled()
    scene_id = str(args.get("sceneId") or "")
    tag = str(args.get("displayTag") or args.get("tag") or "")
    item_id = str(args.get("timelineItemId") or args.get("itemId") or "")
    scene = _scene(ctx, scene_id)
    svc = TimelineReferenceService(ctx.db)
    if tag:
        return svc.resolve_tag(ctx.project_id, scene_id, tag)
    tl = _timeline(scene)
    clip = next((c for c in tl.image_clips if c.id == item_id), None)
    if not clip:
        raise DirectorReferenceError("timeline_item_not_found", f"Item not found: {item_id}")
    return svc.resolve_tag(ctx.project_id, scene_id, clip.display_tag or "")


async def list_timeline_images(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _require_enabled()
    scene_id = str(args.get("sceneId") or "")
    scene = _scene(ctx, scene_id)
    tl = _timeline(scene)
    svc = TimelineReferenceService(ctx.db)
    items = []
    for clip in tl.image_clips:
        refs = svc.store.load_active_set(ctx.project_id, scene_id, clip.id)
        items.append(
            {
                "timelineItemId": clip.id,
                "displayTag": clip.display_tag,
                "assetId": clip.asset_id,
                "start": clip.start,
                "length": clip.length,
                "referenceCount": len(refs.version.bindings) if refs and refs.version else 0,
                "activeVersion": refs.active_version if refs else 0,
            }
        )
    return {"sceneId": scene_id, "images": items, "count": len(items)}


async def get_reference_set(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _require_enabled()
    scene_id = str(args["sceneId"])
    item_id = str(args.get("timelineItemId") or args.get("itemId") or "")
    return TimelineReferenceService(ctx.db).get_references(ctx.project_id, scene_id, item_id)


async def list_reference_bindings(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    data = await get_reference_set(ctx, args)
    return {
        "timelineItemId": data.get("timelineItemId") or args.get("timelineItemId"),
        "activeVersion": data.get("activeVersion", 0),
        "bindings": data.get("bindings", []),
        "count": data.get("count", 0),
    }


async def build_generation_reference_package(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _require_enabled()
    scene_id = str(args["sceneId"])
    item_id = str(args.get("timelineItemId") or args.get("itemId") or "")
    return ReferencePackageBuilder(ctx.db).build(ctx.project_id, scene_id, item_id)


async def suggest_reference_bindings(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Read-only suggestions — does not mutate. Operator/Co-Director may propose separately."""
    _require_enabled()
    scene_id = str(args["sceneId"])
    item_id = str(args.get("timelineItemId") or args.get("itemId") or "")
    scene = _scene(ctx, scene_id)
    tl = _timeline(scene)
    clip = next((c for c in tl.image_clips if c.id == item_id), None)
    if not clip:
        raise DirectorReferenceError("timeline_item_not_found", f"Item not found: {item_id}")
    suggestions: list[dict[str, Any]] = []
    # Suggest prior timeline image as continuity candidate
    priors = sorted(
        [c for c in tl.image_clips if c.id != item_id and c.asset_id and (c.start + c.length) <= clip.start + 1e-6],
        key=lambda c: c.start + c.length,
        reverse=True,
    )
    if priors:
        p = priors[0]
        suggestions.append(
            {
                "role": "continuity",
                "influence": "strong",
                "referenceAssetId": p.asset_id,
                "sourceTimelineItemId": p.id,
                "displayTag": p.display_tag,
                "rationale": "Nearest prior timeline image for continuity.",
            }
        )
    return {
        "timelineItemId": item_id,
        "displayTag": clip.display_tag,
        "suggestions": suggestions,
        "note": "Suggestions are advisory; apply via propose_* tools after approval.",
    }


def _item_args(args: dict[str, Any]) -> tuple[str, str]:
    return str(args["sceneId"]), str(args.get("timelineItemId") or args.get("itemId") or "")


def preview_propose_add_reference_binding(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    scene_id, item_id = _item_args(args)
    return ToolPreview(
        summary=f"Add reference binding on timeline item {item_id}.",
        lines=[
            f"Scene {scene_id}",
            f"Asset {args.get('referenceAssetId')} role={args.get('role')} influence={args.get('influence', 'moderate')}",
        ],
        resourceKind="timeline_reference_set",
        resourceId=item_id,
    )


def apply_propose_add_reference_binding(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    scene_id, item_id = _item_args(args)
    result = TimelineReferenceService(ctx.db).add_binding(
        ctx.project_id,
        scene_id,
        item_id,
        reference_asset_id=str(args["referenceAssetId"]),
        role=str(args.get("role") or "other"),
        influence=str(args.get("influence") or "moderate"),
        source=str(args.get("source") or "project_asset"),
        bible_entity_stable_id=args.get("bibleEntityStableId"),
        bible_version_id=args.get("bibleVersionId"),
        source_timeline_item_id=args.get("sourceTimelineItemId"),
        label=str(args.get("label") or ""),
        notes=str(args.get("notes") or ""),
        created_by="codirector",
    )
    return {"references": result}


def preview_propose_remove_reference_binding(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    scene_id, item_id = _item_args(args)
    return ToolPreview(
        summary=f"Remove reference binding {args.get('bindingId')} from {item_id}.",
        lines=[f"Scene {scene_id}", f"Binding {args.get('bindingId')}"],
        resourceKind="timeline_reference_set",
        resourceId=item_id,
    )


def apply_propose_remove_reference_binding(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    scene_id, item_id = _item_args(args)
    result = TimelineReferenceService(ctx.db).delete_binding(
        ctx.project_id,
        scene_id,
        item_id,
        str(args["bindingId"]),
        created_by="codirector",
    )
    return {"references": result}


def preview_propose_update_reference_binding(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    scene_id, item_id = _item_args(args)
    return ToolPreview(
        summary=f"Update reference binding {args.get('bindingId')} on {item_id}.",
        lines=[f"Scene {scene_id}", f"Patch role/influence/notes"],
        resourceKind="timeline_reference_set",
        resourceId=item_id,
    )


def apply_propose_update_reference_binding(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    scene_id, item_id = _item_args(args)
    result = TimelineReferenceService(ctx.db).patch_binding(
        ctx.project_id,
        scene_id,
        item_id,
        str(args["bindingId"]),
        role=args.get("role"),
        influence=args.get("influence"),
        label=args.get("label"),
        notes=args.get("notes"),
        sort_order=args.get("sortOrder"),
        expected_version=args.get("expectedVersion"),
        created_by="codirector",
    )
    return {"references": result}


def preview_propose_apply_reference_preset(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    scene_id, item_id = _item_args(args)
    return ToolPreview(
        summary=f"Apply reference preset {args.get('presetId')} to {item_id}.",
        lines=[f"Scene {scene_id}", f"Mode {args.get('mode', 'replace')}"],
        resourceKind="timeline_reference_set",
        resourceId=item_id,
    )


def apply_propose_apply_reference_preset(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    scene_id, item_id = _item_args(args)
    result = TimelineReferenceService(ctx.db).apply_preset(
        ctx.project_id,
        scene_id,
        item_id,
        str(args["presetId"]),
        mode=str(args.get("mode") or "replace"),
        expected_version=args.get("expectedVersion"),
        created_by="codirector",
    )
    return {"references": result}


def preview_create_reference_set_proposal(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    # Alias for add binding when set is empty — creates via COW add.
    return preview_propose_add_reference_binding(ctx, args)


def apply_create_reference_set_proposal(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return apply_propose_add_reference_binding(ctx, args)


def extract_timeline_image_mentions(user_message: str) -> list[str]:
    return sorted(set(_TAG_IN_TEXT.findall(user_message or "")))
