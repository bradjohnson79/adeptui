"""Validate SceneSpec against the same Timeline generator registry the Inspector uses."""

from __future__ import annotations

from typing import Any

from .contracts import SceneProductionSpec
from .errors import GeneratorValidationError


_GENERATOR_ALIASES = {
    "minimax-h3": "minimax-h3",
    "minimax-h3-local": "minimax-h3",
    "minimax-h3-t2v-local": "minimax-h3",
    "ltx-2.5": "ltx-2.5",
    "seedance-2.0": "seedance-2.0",
}


def normalize_generator_id(generator_id: str) -> str:
    token = (generator_id or "").strip().lower()
    return _GENERATOR_ALIASES.get(token, token)


def _adapter_caps(generator_id: str) -> Any:
    from ...director_timeline_w46.generation.registry import GeneratorNotFoundError, get_registry

    registry = get_registry()
    try:
        adapter = registry.get(generator_id)
    except GeneratorNotFoundError as exc:
        raise GeneratorValidationError(
            f"{generator_id} is not a Timeline generator.",
            details={"generatorId": generator_id},
        ) from exc
    return adapter.capabilities


def per_batch_duration(spec: SceneProductionSpec) -> float:
    """Total scene duration is split evenly across batches."""
    count = max(int(spec.batch_count or 1), 1)
    return float(spec.duration_seconds or 0.0) / count


def validate_scene_spec_against_generator(spec: SceneProductionSpec) -> dict[str, Any]:
    generator_id = normalize_generator_id(spec.generator_id)
    caps = _adapter_caps(generator_id)
    errors: list[str] = []
    if spec.duration_seconds <= 0:
        errors.append("Duration must be greater than zero.")
    max_sec = float(getattr(caps, "maxDurationSec", 0) or 0)
    per_batch = per_batch_duration(spec)
    if max_sec and per_batch > max_sec + 1e-6:
            errors.append(
                f"{getattr(caps, 'label', generator_id)} does not support a {per_batch:g}s batch duration "
                f"({spec.duration_seconds:g}s across {max(int(spec.batch_count or 1), 1)} batch(es)). "
                f"Maximum duration per batch is {max_sec:g}s — increase the batch count or shorten the scene."
            )
    listed = [str(a) for a in (getattr(caps, "supportedAspectRatios", None) or [])]
    aspect = spec.aspect_ratio
    if listed and aspect and aspect not in listed and not any(aspect in a for a in listed):
        errors.append(
            f"{getattr(caps, 'label', generator_id)} does not support aspect {aspect}. "
            f"Supported: {', '.join(listed)}."
        )
    if spec.batch_count < 1:
        errors.append("Batch count must be at least 1.")
    if spec.megapixels is not None and generator_id.startswith("minimax-h3"):
        from ...video_runtime.legal_canvas import H3_MEGAPIXEL_LABELS, resolve_h3_megapixel_canvas

        try:
            resolve_h3_megapixel_canvas(spec.megapixels)
        except Exception as exc:
            errors.append(str(exc) or f"Unsupported MiniMax H3 megapixels {spec.megapixels}.")
            errors.append(f"Supported: {', '.join(H3_MEGAPIXEL_LABELS)}.")
    if errors:
        raise GeneratorValidationError(" ".join(errors), details={"generatorId": generator_id, "errors": errors})
    return {
        "generatorId": generator_id,
        "label": getattr(caps, "label", generator_id),
        "maxDurationSec": max_sec,
        "supportedAspectRatios": listed,
        "executable": bool(getattr(caps, "executable", True)),
    }


def normalize_generator_config(spec: SceneProductionSpec) -> dict[str, Any]:
    """Map creator-facing values onto Timeline runtime fields. Does not invent pixels for 16:9 MP."""
    from ...video_runtime.legal_canvas import resolve_h3_timeline_canvas, resolve_legal_canvas

    generator_id = normalize_generator_id(spec.generator_id)
    aspect = spec.aspect_ratio or "16:9"
    draft = False
    width = height = 0
    if generator_id.startswith("minimax-h3"):
        if aspect == "16:9":
            canvas = resolve_h3_timeline_canvas(
                {"mode": "manual", "megapixels": spec.megapixels} if spec.megapixels is not None else None,
                draft_mode=draft,
            )
            width, height = int(canvas["width"]), int(canvas["height"])
        else:
            tier = "1080p" if (spec.megapixels or 0) >= 1.5 else "720p"
            legal = resolve_legal_canvas(generator_id, tier=tier, aspect=aspect, surface="r2v")
            width, height = legal.width, legal.height
    return {
        "generatorId": generator_id,
        "durationSeconds": spec.duration_seconds,
        "aspectRatio": aspect,
        "quality": spec.quality,
        "megapixels": spec.megapixels,
        "batchCount": spec.batch_count,
        "width": width,
        "height": height,
        "h3Resolution": (
            {"mode": "manual", "megapixels": spec.megapixels}
            if spec.megapixels is not None and generator_id.startswith("minimax-h3")
            else None
        ),
    }
