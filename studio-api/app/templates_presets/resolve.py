"""Inheritance resolve engine + Project Profile resolution."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Optional

from ..aspect_fps import aspect_to_size
from .catalog.project_types import (
    BUILTIN_PROJECT_TYPES,
    get_builtin_project_type,
    resolve_type_slug,
)
from .catalog.seed_placeholders import system_items_by_slug
from .kinds import BINDING_SLOTS, RESOLUTION_BASE_LONG
from .schema import (
    CreativeBinding,
    CreativeItem,
    ProjectProfile,
    ResolvedCreativePlan,
    ResolvedSlot,
)


SCOPE_ORDER = ("system", "user", "project", "scene", "shot")


def merge_profile(
    primary_type: str,
    traits: list[str] | None = None,
    overrides: dict[str, Any] | None = None,
    custom_definition_profile: dict[str, Any] | None = None,
) -> ProjectProfile:
    traits = [str(t) for t in (traits or []) if str(t).strip()]
    slug = resolve_type_slug(primary_type, traits)

    # Trait may name a concrete subtype (e.g. web_series under series).
    for trait in traits:
        if trait in BUILTIN_PROJECT_TYPES and (
            BUILTIN_PROJECT_TYPES[trait].parent_selector == slug
            or BUILTIN_PROJECT_TYPES[trait].parent_selector == primary_type
            or slug == "series"
            and trait in (BUILTIN_PROJECT_TYPES.get("series").subtypes if BUILTIN_PROJECT_TYPES.get("series") else [])
        ):
            slug = trait
            break

    if custom_definition_profile:
        profile = ProjectProfile.from_dict(custom_definition_profile)
    else:
        definition = get_builtin_project_type(slug) or get_builtin_project_type("custom")
        assert definition is not None
        profile = deepcopy(definition.profile)
        profile.project_type = slug
        profile.display_name = definition.display_name
        profile.version = definition.version
        profile.parent_selector = definition.parent_selector
        profile.group = definition.group

    profile.traits = traits
    if overrides:
        profile.overrides = dict(overrides)
        defaults = dict(profile.defaults)
        for key in ("aspectRatio", "aspect", "frameRate", "fps", "resolution", "delivery"):
            if key in overrides and overrides[key] is not None:
                defaults[key] = overrides[key]
        # Normalize aspect/fps keys
        if "aspect" in defaults and "aspectRatio" not in defaults:
            defaults["aspectRatio"] = defaults["aspect"]
        if "fps" in defaults and "frameRate" not in defaults:
            defaults["frameRate"] = defaults["fps"]
        profile.defaults = defaults
    return profile


def profile_to_dimensions(profile: ProjectProfile) -> tuple[int, int, int]:
    defaults = profile.defaults or {}
    aspect = str(defaults.get("aspectRatio") or defaults.get("aspect") or "16:9")
    resolution = str(defaults.get("resolution") or "1080p")
    base = RESOLUTION_BASE_LONG.get(resolution, 1920)
    width, height = aspect_to_size(aspect, base)
    fps_raw = defaults.get("frameRate", defaults.get("fps", 24))
    try:
        fps = int(fps_raw)
    except (TypeError, ValueError):
        fps = 24
    if fps <= 0:
        fps = 24
    return width, height, fps


def resolve_creative_plan(
    *,
    project_id: str,
    scene_id: Optional[str] = None,
    shot_ref: Optional[str] = None,
    bindings: list[CreativeBinding] | None = None,
    project_items: dict[str, CreativeItem] | None = None,
    user_items: dict[str, CreativeItem] | None = None,
    selections: dict[str, str] | None = None,
) -> ResolvedCreativePlan:
    """Resolve slot → item with system < user < project < scene < shot authority.

    ``selections`` may pin slug/id per slot for the current resolve call without
    mutating bindings.
    """
    system = system_items_by_slug()
    project_items = project_items or {}
    user_items = user_items or {}
    bindings = bindings or []
    selections = selections or {}

    items_by_id: dict[str, CreativeItem] = {}
    for pool in (system.values(), user_items.values(), project_items.values()):
        for item in pool:
            items_by_id[item.id] = item
            items_by_id[item.slug] = item

    # Build per-slot best binding by scope
    best: dict[str, tuple[int, CreativeBinding]] = {}
    scope_rank = {"project": 2, "scene": 3, "shot": 4}
    for binding in bindings:
        if binding.mode == "disabled":
            continue
        if binding.scope_level == "scene" and scene_id and binding.scene_id != scene_id:
            continue
        if binding.scope_level == "shot" and shot_ref and binding.shot_ref != shot_ref:
            continue
        if binding.scope_level == "shot" and not shot_ref:
            continue
        if binding.scope_level == "scene" and not scene_id:
            continue
        rank = scope_rank.get(binding.scope_level, 0)
        prev = best.get(binding.slot)
        if prev is None or rank >= prev[0]:
            best[binding.slot] = (rank, binding)

    plan = ResolvedCreativePlan(project_id=project_id, scene_id=scene_id, shot_ref=shot_ref)
    for slot in BINDING_SLOTS:
        chain: list[str] = ["system"]
        item: CreativeItem | None = None
        source = "system"

        # Explicit selection wins for this resolve (does not mutate parent).
        selected = selections.get(slot)
        if selected and selected in items_by_id:
            item = items_by_id[selected]
            source = item.scope
            chain.append(f"selection:{selected}")
        elif slot in best:
            binding = best[slot][1]
            item = items_by_id.get(binding.item_id)
            source = binding.scope_level
            chain.append(f"{binding.scope_level}:{binding.item_id}")
            if binding.mode == "inherit":
                chain.append("inherit")

        plan.slots[slot] = ResolvedSlot(
            slot=slot,
            item=item,
            source_scope=source if item else "unbound",
            inheritance_chain=chain,
        )

    plan.notes.append("Shot overrides never mutate parent presets unless explicitly saved.")
    return plan


def adapter_citation_note(source_system: str, source_id: str) -> str:
    return f"Cited legacy {source_system}:{source_id} via read-only adapter (not a native creative_item)."
