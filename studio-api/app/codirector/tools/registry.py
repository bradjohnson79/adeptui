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
from .handlers import bible_read, project, scenes, system

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
    "get_provider_health": system.get_provider_health,
    "get_selected_model": system.get_selected_model,
    "get_comfyui_health": system.get_comfyui_health,
    "get_source_manager_status": system.get_source_manager_status,
    "get_reference_capabilities": system.get_reference_capabilities,
    "get_engine_capabilities": system.get_engine_capabilities,
}

_MUTATION_HANDLERS: dict[str, MutationHandler] = {
    "create_scene": MutationHandler(scenes.preview_create_scene, scenes.apply_create_scene),
    "update_scene_title": MutationHandler(scenes.preview_update_scene_title, scenes.apply_update_scene_title),
    "set_scene_prompt": MutationHandler(scenes.preview_set_scene_prompt, scenes.apply_set_scene_prompt),
    "record_director_decision": MutationHandler(
        bible_read.preview_record_director_decision, bible_read.apply_record_director_decision
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
