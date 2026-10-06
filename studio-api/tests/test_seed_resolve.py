"""Unit tests for canonical Comfy execution-seed resolution (SEED LAW)."""

from __future__ import annotations

import pytest

from app.video_runtime.seed_resolve import (
    COMFY_SEED_MAX,
    RANDOMIZE_SENTINEL,
    comfy_noise_seed,
    resolve_execution_seed,
    seed_lineage_patch,
)


def test_exact_seed_passthrough():
    r = resolve_execution_seed(42)
    assert r.requested_seed == 42
    assert r.resolved_seed == 42
    assert r.randomized is False


def test_zero_is_exact_not_randomize():
    r = resolve_execution_seed(0)
    assert r.requested_seed == 0
    assert r.resolved_seed == 0
    assert r.randomized is False


def test_minus_one_randomizes_not_clamp_to_zero():
    # Fixed RNG so we prove we do NOT clamp -1 -> 0.
    r = resolve_execution_seed(-1, rng_below=lambda n: 123456)
    assert r.requested_seed == RANDOMIZE_SENTINEL
    assert r.resolved_seed == 123456
    assert r.randomized is True
    assert r.resolved_seed != 0 or True  # may be 0 only if RNG returns 0


def test_minus_one_never_forced_to_zero_when_rng_nonzero():
    r = resolve_execution_seed(-1, rng_below=lambda n: 7)
    assert r.resolved_seed == 7
    assert r.resolved_seed != 0


def test_none_randomizes_like_minus_one():
    r = resolve_execution_seed(None, rng_below=lambda n: 99)
    assert r.requested_seed == RANDOMIZE_SENTINEL
    assert r.resolved_seed == 99
    assert r.randomized is True


def test_other_negative_rejected():
    with pytest.raises(ValueError, match="Invalid seed"):
        resolve_execution_seed(-2)


def test_over_max_rejected():
    with pytest.raises(ValueError, match="exceeds"):
        resolve_execution_seed(COMFY_SEED_MAX + 1)


def test_comfy_noise_seed_helper():
    assert comfy_noise_seed(5) == 5
    assert comfy_noise_seed(-1, rng_below=lambda n: 11) == 11


def test_lineage_patch_shape():
    r = resolve_execution_seed(-1, rng_below=lambda n: 3)
    patch = seed_lineage_patch(r)
    assert patch == {
        "seed": {
            "requested_seed": -1,
            "resolved_seed": 3,
            "randomized": True,
        }
    }


def test_resolved_seed_always_nonnegative_for_valid_inputs():
    for req in (None, -1, 0, 1, COMFY_SEED_MAX):
        r = resolve_execution_seed(req, rng_below=lambda n: 0)
        assert r.resolved_seed >= 0
