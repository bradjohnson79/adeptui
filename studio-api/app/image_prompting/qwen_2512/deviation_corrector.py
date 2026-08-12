"""Correction prompt compiler for Qwen-Image-2512 identity drift."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .identity_lock import build_identity_lock
from .negative_constraints import build_negative_constraints

_CORRECTION_MAP: dict[str, str] = {
    "blonde": "restore black twin ponytails",
    "blue eyes": "restore purple eyes",
    "aqua eyes": "restore purple eyes",
    "human ears": "restore elongated Sun Sprite Elf ears",
    "rounded ears": "restore elongated Sun Sprite Elf ears",
    "anadriya": "remove Anadriya resemblance and keep Korri distinct",
    "tattoo": "replace tattoo language with light-circuitry markings (not tattoos)",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _package_value(package: Mapping[str, Any], key: str) -> str:
    value = package.get(key)
    if isinstance(value, str):
        return value
    return _text(value)


def suggest_corrections(observed_deviations: Sequence[str]) -> list[str]:
    suggestions: list[str] = []
    for deviation in observed_deviations:
        lowered = _text(deviation).lower()
        for needle, correction in _CORRECTION_MAP.items():
            if needle in lowered and correction not in suggestions:
                suggestions.append(correction)
    return suggestions or ["restore all locked identity traits exactly as specified"]


def compile_correction_prompt(
    base_package: Mapping[str, Any],
    *,
    observed_deviations: Sequence[str],
    priority_fixes: Sequence[str] | None = None,
) -> dict[str, Any]:
    identity_lock = build_identity_lock(base_package.get("blueprint") or {})
    preserved = [
        _package_value(base_package, "compositionSummary"),
        _package_value(base_package, "styleSummary"),
        _package_value(base_package, "environmentSummary"),
    ]
    corrections = list(priority_fixes or [])
    for suggestion in suggest_corrections(observed_deviations):
        if suggestion not in corrections:
            corrections.append(suggestion)

    instruction = (
        "Correct only the listed identity drift while preserving the approved composition, camera, "
        "lighting, pose, wardrobe materials, and style treatment. "
        f"Apply these fixes: {'; '.join(corrections)}."
    )
    if any(item for item in preserved):
        instruction += f" Preserve unchanged approved context: {'; '.join(item for item in preserved if item)}."

    return {
        "instruction": instruction,
        "observedDeviations": [_text(item) for item in observed_deviations if _text(item)],
        "priorityFixes": corrections,
        "negativePrompt": ", ".join(build_negative_constraints(identity_lock)),
        "lockedTraits": identity_lock.get("locked_traits") or [],
    }
