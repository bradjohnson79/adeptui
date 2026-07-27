"""The closed tool registry: the single place a definition is bound to a handler.

Binding lives in one table with one entry per declared tool. There is no dynamic lookup, no
name-to-import resolution, and no way to register a tool at runtime — if a tool isn't in
`_READ_HANDLERS` or `_MUTATION_HANDLERS` below, it cannot execute, and the module refuses to
import if a declared tool has no binding.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

from ..errors import TOOL_KIND_MISMATCH, TOOL_NOT_FOUND, TOOL_SCHEMA_VERSION_MISMATCH, CoDirectorError
from .definitions import (
    TOOL_DEFINITIONS,
    ToolContext,
    ToolDefinition,
    ToolPreview,
)
from .handlers import bible_domain, bible_read, project, scenes, storyboard, system, timeline_references, vision

ReadHandler = Callable[[ToolContext, dict[str, Any]], Awaitable[dict[str, Any]]]
PreviewFn = Callable[[ToolContext, dict[str, Any]], ToolPreview]
ApplyFn = Callable[[ToolContext, dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class MutationHandler:
    preview: PreviewFn
    apply: ApplyFn


_READ_HANDLERS: dict[str, ReadHandler] = {
    "get_project_profile": project.get_project_profile,
    "get_project_status": project.get_project_status,
    "list_scenes": scenes.list_scenes,
    "get_scene": scenes.get_scene,
    "get_active_scene": scenes.get_active_scene,
    "get_current_bible_version": bible_read.get_current_bible_version,
    "get_bible_entity": bible_read.get_bible_entity,
    "list_bible_entities": bible_read.list_bible_entities,
    "get_relevant_bible_context": bible_read.get_relevant_bible_context,
    "get_production_bible_summary": bible_domain.get_production_bible_summary,
    "get_scene_bible_context": bible_domain.get_scene_bible_context,
    "get_character_bible_context": bible_domain.get_character_bible_context,
    "get_location_bible_context": bible_domain.get_location_bible_context,
    "list_canon_records": bible_domain.list_canon_records,
    "list_continuity_warnings": bible_domain.list_continuity_warnings,
    "get_generation_reference_package": bible_domain.get_generation_reference_package,
    "get_provider_health": system.get_provider_health,
    "get_selected_model": system.get_selected_model,
    "get_comfyui_health": system.get_comfyui_health,
    "get_source_manager_status": system.get_source_manager_status,
    "get_reference_capabilities": system.get_reference_capabilities,
    "get_engine_capabilities": system.get_engine_capabilities,
    "get_cloud_render_status": system.get_cloud_render_status,
    "vision_validation_status": vision.vision_validation_status,
    "vision_validation_report": vision.vision_validation_report,
    "get_timeline_image": timeline_references.get_timeline_image,
    "list_timeline_images": timeline_references.list_timeline_images,
    "get_reference_set": timeline_references.get_reference_set,
    "list_reference_bindings": timeline_references.list_reference_bindings,
    "build_generation_reference_package": timeline_references.build_generation_reference_package,
    "suggest_reference_bindings": timeline_references.suggest_reference_bindings,
}

_MUTATION_HANDLERS: dict[str, MutationHandler] = {
    "create_scene": MutationHandler(scenes.preview_create_scene, scenes.apply_create_scene),
    "update_scene_title": MutationHandler(scenes.preview_update_scene_title, scenes.apply_update_scene_title),
    "set_scene_prompt": MutationHandler(scenes.preview_set_scene_prompt, scenes.apply_set_scene_prompt),
    "record_director_decision": MutationHandler(
        bible_read.preview_record_director_decision, bible_read.apply_record_director_decision
    ),
    "propose_character_update": MutationHandler(
        bible_domain.preview_propose_character_update, bible_domain.apply_propose_character_update
    ),
    "propose_canon_record": MutationHandler(
        bible_domain.preview_propose_canon_record, bible_domain.apply_propose_canon_record
    ),
    "propose_canon_supersession": MutationHandler(
        bible_domain.preview_propose_canon_supersession, bible_domain.apply_propose_canon_supersession
    ),
    "propose_continuity_update": MutationHandler(
        bible_domain.preview_propose_continuity_update, bible_domain.apply_propose_continuity_update
    ),
    "propose_reference_link": MutationHandler(
        bible_domain.preview_propose_reference_link, bible_domain.apply_propose_reference_link
    ),
    "propose_production_decision": MutationHandler(
        bible_domain.preview_propose_production_decision, bible_domain.apply_propose_production_decision
    ),
    "propose_visual_language_update": MutationHandler(
        bible_domain.preview_propose_visual_language_update, bible_domain.apply_propose_visual_language_update
    ),
    "propose_storyboard_generation": MutationHandler(
        storyboard.preview_propose_storyboard_generation, storyboard.apply_propose_storyboard_generation
    ),
    "propose_vision_correction": MutationHandler(
        vision.preview_propose_vision_correction, vision.apply_propose_vision_correction
    ),
    "propose_asset_bible_link": MutationHandler(
        vision.preview_propose_asset_bible_link, vision.apply_propose_asset_bible_link
    ),
    "record_vision_review": MutationHandler(
        vision.preview_record_vision_review, vision.apply_record_vision_review
    ),
    "create_reference_set_proposal": MutationHandler(
        timeline_references.preview_create_reference_set_proposal,
        timeline_references.apply_create_reference_set_proposal,
    ),
    "propose_add_reference_binding": MutationHandler(
        timeline_references.preview_propose_add_reference_binding,
        timeline_references.apply_propose_add_reference_binding,
    ),
    "propose_remove_reference_binding": MutationHandler(
        timeline_references.preview_propose_remove_reference_binding,
        timeline_references.apply_propose_remove_reference_binding,
    ),
    "propose_update_reference_binding": MutationHandler(
        timeline_references.preview_propose_update_reference_binding,
        timeline_references.apply_propose_update_reference_binding,
    ),
    "propose_apply_reference_preset": MutationHandler(
        timeline_references.preview_propose_apply_reference_preset,
        timeline_references.apply_propose_apply_reference_preset,
    ),
}

_BY_ID: dict[str, ToolDefinition] = {t.tool_id: t for t in TOOL_DEFINITIONS}


def _validate_bindings() -> None:
    """Fail at import time rather than mid-turn if the registry is internally inconsistent."""

    for definition in TOOL_DEFINITIONS:
        bound = _READ_HANDLERS if definition.kind == "read" else _MUTATION_HANDLERS
        if definition.tool_id not in bound:
            raise RuntimeError(f"Tool '{definition.tool_id}' is declared but has no {definition.kind} handler.")
    unknown = (set(_READ_HANDLERS) | set(_MUTATION_HANDLERS)) - set(_BY_ID)
    if unknown:
        raise RuntimeError(f"Handlers bound for undeclared tools: {sorted(unknown)}")


_validate_bindings()


def all_definitions() -> tuple[ToolDefinition, ...]:
    return TOOL_DEFINITIONS


def catalog() -> list[dict[str, Any]]:
    return [t.to_dict() for t in TOOL_DEFINITIONS]


def get(tool_id: str) -> ToolDefinition:
    definition = _BY_ID.get(tool_id)
    if definition is None:
        raise CoDirectorError(
            TOOL_NOT_FOUND,
            f"'{tool_id}' isn't a Co-Director tool.",
            details={"toolId": tool_id},
            recoverable=False,
            recommended_action="none",
        )
    return definition


def find(tool_id: str) -> Optional[ToolDefinition]:
    return _BY_ID.get(tool_id)


def require_kind(tool_id: str, kind: str) -> ToolDefinition:
    definition = get(tool_id)
    if definition.kind != kind:
        raise CoDirectorError(
            TOOL_KIND_MISMATCH,
            (
                f"'{tool_id}' is a {definition.kind} tool and can't be used here."
                if definition.kind == "read"
                else f"'{tool_id}' changes project data, so it needs an approved proposal."
            ),
            details={"toolId": tool_id, "kind": definition.kind, "expectedKind": kind},
            recoverable=False,
            recommended_action="none",
        )
    return definition


def check_schema_version(definition: ToolDefinition, version: int) -> None:
    """Guard a stored proposal against a registry that has since changed shape."""

    if version != definition.schema_version:
        raise CoDirectorError(
            TOOL_SCHEMA_VERSION_MISMATCH,
            "This proposal was created for an older version of the tool and can't be applied.",
            details={
                "toolId": definition.tool_id,
                "proposalSchemaVersion": version,
                "currentSchemaVersion": definition.schema_version,
            },
            recoverable=False,
            recommended_action="none",
        )


def read_handler(tool_id: str) -> ReadHandler:
    require_kind(tool_id, "read")
    return _READ_HANDLERS[tool_id]


def mutation_handler(tool_id: str) -> MutationHandler:
    require_kind(tool_id, "mutating")
    return _MUTATION_HANDLERS[tool_id]
