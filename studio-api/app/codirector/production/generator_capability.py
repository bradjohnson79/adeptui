"""Generator-aware long-scene planning for Co-Director scene production.

Capability law: Co-Director asks the Timeline generator capability registry
"how long can this generator natively generate in ONE pass?" and decomposes
the scene into sequential batch windows from that answer. No model-name
checks, no universal 15-second assumption, no hardcoded thresholds.

Adept's CERTIFIED capability (adapter contract) governs — never a
vendor-advertised maximum the adapter has not certified:

    maxSingleGenerationSeconds = maxDurationSec if set else max(supportedDurations)

    scene duration <= maxSingleGenerationSeconds → 1 batch, one execution prompt
    scene duration >  maxSingleGenerationSeconds → ceil(duration / max) batches
                                                   each with its own full prompt
"""

from __future__ import annotations

import math
from typing import Any

from .contracts import SceneProductionSpec


class GeneratorCapabilityError(Exception):
    """The generator has no certified single-generation duration."""


def certified_single_generation_seconds(caps: Any) -> float:
    """Adept-certified max seconds for ONE generation pass of this generator.

    Explicit ``maxDurationSec`` wins; otherwise the largest listed
    ``supportedDurations`` entry. Both come from the capability contract the
    Timeline adapters enforce at request validation — the same floor the
    runtime itself rejects requests over.
    """
    explicit = getattr(caps, "maxDurationSec", None)
    if explicit is not None and float(explicit) > 0:
        return float(explicit)
    listed = [float(d) for d in (getattr(caps, "supportedDurations", None) or []) if float(d) > 0]
    if listed:
        return max(listed)
    raise GeneratorCapabilityError(
        f"{getattr(caps, 'label', 'generator')} declares no certified single-generation duration "
        "(maxDurationSec and supportedDurations are both empty) — refusing to guess a batch plan."
    )


def resolve_max_single_generation_seconds(generator_id: str) -> float:
    """Ask the Timeline capability registry for the certified single-pass window."""
    from ...director_timeline_w46.generation.registry import GeneratorNotFoundError, get_registry
    from .generator_validator import GeneratorValidationError, normalize_generator_id

    registry = get_registry()
    try:
        adapter = registry.get(normalize_generator_id(generator_id))
    except GeneratorNotFoundError as exc:
        raise GeneratorValidationError(
            f"{generator_id} is not a Timeline generator.",
            details={"generatorId": generator_id},
        ) from exc
    return certified_single_generation_seconds(adapter.capabilities)


def capability_batch_plan(
    *,
    duration_seconds: float,
    max_single_generation_seconds: float,
    requested_batch_count: int | None = None,
) -> list[tuple[float, float]]:
    # OWNER-PROTECTED (Timeline Batch Architecture Guard). Windows come from the
    # capability registry's maxSingleGenerationSeconds — never hardcoded model
    # names, never even-split padding of a full-scene prompt. Final window is
    # partial by design. Fences: tests/test_timeline_architecture_guard.py
    """Ordered [start, end) windows covering the scene.

    count = ceil(duration / maxWindow). The final batch is a partial window —
    the scene is never padded to fill the generator's maximum. Windows are
    contiguous and gap-free so beats allocate to exactly one batch.

    ``requested_batch_count`` (creator said "3 batches") may coarsen the plan
    only when every resulting window still fits the certified maximum.
    """
    duration = max(float(duration_seconds or 0.0), 0.0)
    window = float(max_single_generation_seconds)
    if window <= 0:
        raise GeneratorCapabilityError("Generator single-generation window must be positive.")
    if duration <= 0:
        return []
    count = int(math.ceil(duration / window))
    requested = int(requested_batch_count or 0)
    if requested > count:
        # Coarser only if still within capability: every window <= maxWindow.
        coarsened = min(requested, int(math.ceil(duration / (duration / requested))))
        if duration / coarsened <= window + 1e-6:
            count = coarsened
            # Even split is safe here (every window fits) and gives the
            # creator's stated structure balanced windows.
            per = duration / count
            return [
                (round(i * per, 4), round(duration, 4) if i == count - 1 else round((i + 1) * per, 4))
                for i in range(count)
            ]
    # Capability-decided plan: full-size windows, partial final window.
    # 52s @ 15s → (0,15) (15,30) (30,45) (45,52) — the final batch is not
    # padded to fill the generator's maximum window.
    windows: list[tuple[float, float]] = []
    for index in range(count):
        start = round(index * window, 4)
        end = round(min((index + 1) * window, duration), 4)
        windows.append((start, end))
    return windows


def plan_spec_batches(
    spec: SceneProductionSpec,
    *,
    requested_batch_count: int | None = None,
) -> tuple[int, list[tuple[float, float]]]:
    """Resolve (batch_count, windows) for a spec from generator capability.

    The creator's stated batch count is honored only when it does not violate
    capability — otherwise the capability floor decides. Returns the effective
    count and the temporal windows for prompt compilation.
    """
    max_window = resolve_max_single_generation_seconds(spec.generator_id)
    effective_requested = requested_batch_count if requested_batch_count is not None else None
    if effective_requested is None and int(spec.batch_count or 0) > 1:
        effective_requested = int(spec.batch_count)
    windows = capability_batch_plan(
        duration_seconds=spec.duration_seconds,
        max_single_generation_seconds=max_window,
        requested_batch_count=effective_requested,
    )
    return max(len(windows), 1), windows
