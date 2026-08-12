"""Continuity and reference grounding for structured image prompts."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def _text(value: Any) -> str:
    return str(value or "").strip()


def compile_continuity_block(
    blueprint: Mapping[str, Any],
    identity_lock: Mapping[str, Any],
    references: Sequence[Mapping[str, Any]] | None = None,
) -> str:
    references = references or []
    locked = ", ".join(identity_lock.get("locked_traits") or [])
    continuity_notes = [_text(blueprint.get("hair_continuity"))]

    reference_roles = []
    for item in references:
        if not isinstance(item, Mapping):
            continue
        role = _text(item.get("reference_role"))
        if role:
            reference_roles.append(role)

    if reference_roles:
        continuity_notes.append(f"reference roles: {', '.join(reference_roles[:8])}")
    if identity_lock.get("forbidden_traits"):
        continuity_notes.append("apply the negative-constraints block as the drift-rejection source of truth")

    prefix = f"locked continuity traits: {locked}." if locked else "locked continuity traits present."
    suffix = " ".join(note for note in continuity_notes if note)
    return f"{prefix} {suffix}".strip()
