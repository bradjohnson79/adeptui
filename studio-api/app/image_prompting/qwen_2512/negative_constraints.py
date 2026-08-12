"""Negative constraint generation for identity-safe prompts."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def _text(value: Any) -> str:
    return str(value or "").strip()


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def build_negative_constraints(
    identity_lock: Mapping[str, Any],
    extras: Sequence[str] | None = None,
) -> list[str]:
    items = list(identity_lock.get("forbidden_traits") or [])
    items.extend(
        [
            "identity drift",
            "wrong character",
            "missing wooden accessories",
            "missing light-circuitry markings",
        ]
    )
    if identity_lock.get("is_korri"):
        items.extend(
            [
                "blonde hair",
                "blue eyes",
                "aqua eyes",
                "human ears",
                "rounded ears",
                "Anadriya resemblance",
                "Anadriya formal Adept styling",
                "metallic sci-fi wardrobe",
                "generic armor",
                "tattoo ink replacing light-circuitry markings",
            ]
        )
    if extras:
        items.extend(_text(item) for item in extras if _text(item))
    return _unique([_text(item) for item in items if _text(item)])


def compile_negative_constraints_block(
    identity_lock: Mapping[str, Any],
    extras: Sequence[str] | None = None,
) -> str:
    return ", ".join(build_negative_constraints(identity_lock, extras))
