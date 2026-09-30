"""Canonical execution-seed resolver for Comfy-bound video graphs.

SEED LAW (owner):
- requested_seed == -1 (or None) means randomize BEFORE execution
- requested_seed >= 0 means use exactly that seed
- Never clamp -1 to 0 (that violates creator "randomize" semantics)
- Never let a negative seed reach a Comfy node that forbids it (RandomNoise
  noise_seed min=0, max=2**64-1 per object_info)
- Persist both requested_seed and resolved_seed in lineage metadata
"""

from __future__ import annotations

import secrets
from dataclasses import asdict, dataclass
from typing import Any, Mapping

# JSON-safe upper bound well inside Comfy RandomNoise max (2**64-1).
# Matches common Adept practice (2**31 range) while allowing full uint32.
COMFY_SEED_MAX = 2**32 - 1
RANDOMIZE_SENTINEL = -1


@dataclass(frozen=True)
class ResolvedSeed:
    """Creator request + Comfy-safe resolved value."""

    requested_seed: int
    resolved_seed: int
    randomized: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def resolve_execution_seed(
    requested: int | None,
    *,
    rng_below: Any | None = None,
) -> ResolvedSeed:
    """Resolve a creator seed into a Comfy-valid non-negative integer.

    Args:
        requested: Creator/UI seed. ``-1`` or ``None`` => randomize.
            ``>= 0`` => use exactly. Other negatives are invalid.
        rng_below: Optional callable ``(upper: int) -> int`` returning
            ``0 .. upper-1``. Defaults to ``secrets.randbelow``. Injected
            for unit tests.
    """
    if requested is None or int(requested) == RANDOMIZE_SENTINEL:
        picker = rng_below if rng_below is not None else secrets.randbelow
        resolved = int(picker(COMFY_SEED_MAX + 1))
        return ResolvedSeed(
            requested_seed=RANDOMIZE_SENTINEL if requested is None else int(requested),
            resolved_seed=resolved,
            randomized=True,
        )

    value = int(requested)
    if value < 0:
        raise ValueError(
            f"Invalid seed {value}: only -1 (randomize) or >= 0 (exact) are allowed"
        )
    if value > COMFY_SEED_MAX:
        # Keep exact semantics for in-range seeds; refuse silent wrap/clamp.
        raise ValueError(
            f"Seed {value} exceeds Comfy-safe max {COMFY_SEED_MAX}"
        )
    return ResolvedSeed(requested_seed=value, resolved_seed=value, randomized=False)


def comfy_noise_seed(requested: int | None, *, rng_below: Any | None = None) -> int:
    """Convenience: return only the Comfy-bound resolved seed."""
    return resolve_execution_seed(requested, rng_below=rng_below).resolved_seed


def seed_lineage_patch(resolved: ResolvedSeed) -> dict[str, Any]:
    """Patch fragment for merge_video_runtime_history / result metadata."""
    return {
        "seed": {
            "requested_seed": resolved.requested_seed,
            "resolved_seed": resolved.resolved_seed,
            "randomized": resolved.randomized,
        }
    }


def extract_seed_lineage(history_or_params: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(history_or_params, Mapping):
        return None
    vr = history_or_params.get("videoRuntime")
    if isinstance(vr, Mapping) and isinstance(vr.get("seed"), Mapping):
        return dict(vr["seed"])
    if isinstance(history_or_params.get("seed"), Mapping):
        return dict(history_or_params["seed"])
    return None
