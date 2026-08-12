"""Scope inheritance resolution for scene references (projection only)."""

from __future__ import annotations

from typing import Any, Iterable

from .constants import SCOPE_PRECEDENCE


def scope_rank(scope_type: str) -> int:
    try:
        return SCOPE_PRECEDENCE.index(scope_type)
    except ValueError:
        return len(SCOPE_PRECEDENCE)


def ancestor_chain(
    scope_type: str,
    scope_id: str,
    *,
    project_id: str,
    sequence_id: str | None = None,
    scene_id: str | None = None,
    shot_id: str | None = None,
    clip_id: str | None = None,
) -> list[tuple[str, str]]:
    """Return scopes from most specific to project for inheritance walk."""
    chain: list[tuple[str, str]] = [(scope_type, scope_id)]
    if scope_type == "clip" and shot_id:
        chain.append(("shot", shot_id))
    if scope_type in {"clip", "shot"} and scene_id:
        chain.append(("scene", scene_id))
    if scope_type in {"clip", "shot", "scene"} and sequence_id:
        chain.append(("sequence", sequence_id))
    if scope_type in {"start_frame", "middle_frame", "end_frame"} and scene_id:
        chain.append(("scene", scene_id))
    chain.append(("project", project_id))
    # Deduplicate while preserving order
    seen: set[tuple[str, str]] = set()
    out: list[tuple[str, str]] = []
    for item in chain:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def merge_inherited(
    bindings_by_scope: dict[tuple[str, str], list[dict[str, Any]]],
    chain: list[tuple[str, str]],
) -> list[dict[str, Any]]:
    """
    Merge bindings along chain. More-specific scopes override same asset+type.
    Marks inherited_from and is_override.
    """
    selected: dict[tuple[str, str], dict[str, Any]] = {}
    origin: dict[tuple[str, str], str] = {}

    # Walk from least specific to most specific so overrides win
    for scope_type, scope_id in reversed(chain):
        for b in bindings_by_scope.get((scope_type, scope_id), []):
            key = (b["asset_id"], b["reference_type"])
            if not b.get("enabled", True):
                continue
            label = f"{scope_type}:{scope_id}"
            if key in selected and origin.get(key) != label:
                b = {**b, "is_override": True, "inherited_from": origin[key]}
            else:
                b = {
                    **b,
                    "is_override": False,
                    "inherited_from": None if (scope_type, scope_id) == chain[0] else label,
                }
            selected[key] = b
            origin[key] = label

    # Sort by order_index then id
    result = list(selected.values())
    result.sort(key=lambda x: (x.get("order_index", 0), x.get("id", "")))
    return result


def flatten_for_display(bindings: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(list(bindings), key=lambda x: (x.get("order_index", 0), x.get("id", "")))
