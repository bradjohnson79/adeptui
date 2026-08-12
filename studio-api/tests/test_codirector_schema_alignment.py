"""Static hygiene guard: every handler arg read must be declared in its ToolDefinition.

Parses each handler file with ``ast`` and collects string literals passed to
``args.get(...)`` / ``args[...]`` / ``args.pop(...)`` inside the preview/apply (or read)
function bound to a tool by the registry. Every collected key must be declared in the
corresponding ``ToolDefinition.parameters`` (resolved via the registry bindings) or
appear in ``ALLOWED_UNDECLARED`` below.

The allowlist is a snapshot of pre-existing exceptions at the time this guard was
introduced (c1-tool-registry repair). It is explicit and commented so a future
tightening is a visible diff. The test FAILS if a handler reads a new key that is
neither declared nor allowlisted.

Allowlist categories:

- snake_case defensive aliases: a few library/asset handlers read both
  ``args.get(\"assetId\")`` and ``args.get(\"asset_id\")``. The schema declares only the
  camelCase form (the model emits camelCase); the snake_case read is a legacy fallback
  the sanitizer never populates. Harmless dead reads, kept to avoid churning handlers
  outside this repair.
- asset.search/cursor: ``asset.search`` and ``asset.list`` share the ``asset_list``
  handler. ``asset.list`` declares ``cursor`` for pagination; ``asset.search`` does
  not, so the handler's ``cursor`` read is a no-op for search (documented in c1).
- out-of-scope pre-existing: handler reads an undeclared key not in the c1 P0/P1
  repair list. Snapshotted so the guard passes today; the primary agent may tighten.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

from app.codirector.tools import registry


def _collect_arg_keys(file_path: Path, func_name: str):
    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            keys: set[str] = set()
            for n in ast.walk(node):
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
                    if (
                        n.func.attr in ("get", "pop")
                        and isinstance(n.func.value, ast.Name)
                        and n.func.value.id == "args"
                        and n.args
                        and isinstance(n.args[0], ast.Constant)
                        and isinstance(n.args[0].value, str)
                    ):
                        keys.add(n.args[0].value)
                if isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name) and n.value.id == "args":
                    sl = n.slice
                    if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
                        keys.add(sl.value)
            return keys
    return None


# snake_case defensive aliases (camelCase declared; snake_case never populated).
_SNAKE_CASE_ALIASES = {
    "propose_asset_library_assignment": {
        "asset_id", "entity_id", "entity_name", "entity_type", "folder_id", "system_key",
    },
    "search_library_assets": {"entity_type", "folder_id", "q", "system_key"},
    "link_bible_entity_folder": {"entity_id", "entity_name", "entity_type", "system_key"},
    "plan_library_storage": {"entity_id", "entity_name", "entity_type", "expectedName", "system_key"},
    "resolve_library_location": {"system_key"},
    "character_creator.propose_visual_sheet": {"hero_asset_id"},
}

# asset.search shares asset_list; cursor is an asset.list-only contract.
_SHARED_HANDLER_EXCEPTIONS = {
    "asset.search": {"cursor"},
}

# Pre-existing out-of-scope mismatches (handler reads undeclared key; not in c1 P0/P1).
_OUT_OF_SCOPE = {
    ("build_generation_reference_package", "itemId"),
    ("character_creator.build_expression_plan", "characterKey"),
    ("character_creator.build_pose_plan", "characterKey"),
    ("character_creator.compare_voice_candidates", "candidateIdA"),
    ("character_creator.compare_voice_candidates", "candidateIdB"),
    ("character_creator.create_from_script", "excerpt"),
    ("character_creator.generate_voice_clone", "consent"),
    ("character_creator.generate_voice_clone", "path"),
    ("character_creator.get_voice_candidates", "voiceProfileId"),
    ("character_creator.refine_voice_candidate", "notes"),
    ("character_creator.validate_clone_source", "referencePath"),
    ("get_cloud_render_status", "model"),
    ("get_reference_set", "itemId"),
    ("get_timeline_image", "itemId"),
    ("get_timeline_image", "tag"),
    ("hosted_providers.recommend", "model"),
    ("posecraft.rename_object", "figureId"),
    ("posecraft.rename_object", "name"),
    ("posecraft.rename_object", "primitiveId"),
    ("production_bible.list_entries", "limit"),
    ("production_plan.create_draft", "steps"),
    ("prompt.recommend_strategy", "projectPrefs"),
    ("propose_add_reference_binding", "bibleEntityStableId"),
    ("propose_add_reference_binding", "bibleVersionId"),
    ("propose_image_edit", "targetAssetIds"),
    ("propose_image_edit", "engine"),
    ("propose_image_edit", "instruction"),
    ("propose_image_edit", "masks"),
    ("propose_image_edit", "referenceAssetIds"),
    ("propose_image_edit", "refs"),
    ("propose_image_edit", "sourceAssetIds"),
    ("propose_image_edit", "text"),
    ("propose_image_generate", "engine"),
    ("propose_image_generate", "family"),
    ("propose_image_generate", "refs"),
    ("propose_image_generate", "text"),
    ("propose_image_generate", "quality"),
    ("propose_image_generate", "style"),
    ("propose_update_reference_binding", "sortOrder"),
    ("propose_vision_correction", "findingValidatorIds"),
    ("script.convert_outline_to_scenes", "beats"),
    ("suggest_reference_bindings", "itemId"),
    ("timeline.propose_cancel", "batchBlockIds"),
    ("timeline.propose_create_inpaint_mask", "inPaintStrategy"),
    ("timeline.propose_generate_scene", "batchBlockIds"),
    ("timeline.set_playhead", "time"),
    ("timeline.update_settings", "settings"),
    ("voice_performance.parse_markup", "markup"),
}


def _allowed_undeclared() -> set[tuple[str, str]]:
    allowed: set[tuple[str, str]] = set()
    for tool_id, keys in _SNAKE_CASE_ALIASES.items():
        for key in keys:
            allowed.add((tool_id, key))
    for tool_id, keys in _SHARED_HANDLER_EXCEPTIONS.items():
        for key in keys:
            allowed.add((tool_id, key))
    allowed |= _OUT_OF_SCOPE
    return allowed


def _bound_functions(definition):
    if definition.kind == "read":
        fn = registry.read_handler(definition.tool_id)
        return [(fn.__name__, fn)]
    mh = registry.mutation_handler(definition.tool_id)
    return [(mh.preview.__name__, mh.preview), (mh.apply.__name__, mh.apply)]


def test_every_handler_arg_read_is_declared_or_allowlisted() -> None:
    allowed = _allowed_undeclared()
    mismatches: list[tuple[str, str, str]] = []
    for definition in registry.all_definitions():
        declared = {p.name for p in definition.parameters}
        for func_name, fn in _bound_functions(definition):
            module = importlib.import_module(fn.__module__)
            file_path = Path(module.__file__)
            keys = _collect_arg_keys(file_path, func_name)
            if not keys:
                continue
            for key in sorted(keys):
                if key in declared:
                    continue
                if (definition.tool_id, key) in allowed:
                    continue
                mismatches.append((definition.tool_id, func_name, key))
    assert not mismatches, (
        "Handler reads undeclared+unallowlisted argument keys (add the parameter to "
        "the ToolDefinition in definitions.py, or extend the allowlist with a "
        "comment if the read is intentional):\n"
        + "\n".join(f"  {tid} [{fn}] reads undeclared '{key}'" for tid, fn, key in mismatches)
    )
