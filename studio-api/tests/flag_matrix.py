"""Shared feature-flag matrix helpers for M2.6.1 closed-loop tests."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable

import pytest

from app.feature_flags import FeatureFlags


@dataclass(frozen=True)
class FlagCombo:
    name: str
    vision: bool
    references: bool
    intelligence: bool


# Combinations required by the M2.6.1 prompt §5.
FLAG_MATRIX: tuple[FlagCombo, ...] = (
    FlagCombo("all_off", False, False, False),
    FlagCombo("vision_only", True, False, True),
    FlagCombo("refs_only", False, True, True),
    FlagCombo("vision_refs_no_intel", True, True, False),
    FlagCombo("full_loop", True, True, True),
)


def apply_flag_combo(monkeypatch: pytest.MonkeyPatch, combo: FlagCombo) -> FeatureFlags:
    """Patch FeatureFlags singletons used by vision / references / intelligence modules."""

    def _set(name: str, enabled: bool) -> None:
        if enabled:
            monkeypatch.setenv(name, "1")
        else:
            monkeypatch.delenv(name, raising=False)

    _set("STUDIO_FEATURE_VISION_VALIDATION_V1", combo.vision)
    _set("STUDIO_FEATURE_TIMELINE_REFERENCES_V1", combo.references)
    _set("STUDIO_FEATURE_CODIRECTOR_INTELLIGENCE_V2", combo.intelligence)

    fresh = FeatureFlags.from_env(os.environ)

    import app.feature_flags as ff

    monkeypatch.setattr(ff, "feature_flags", fresh)

    try:
        import app.director_references.service as svc_mod
        import app.director_references.package as pkg_mod

        monkeypatch.setattr(svc_mod, "feature_flags", fresh)
        monkeypatch.setattr(pkg_mod, "feature_flags", fresh)
    except Exception:
        pass

    try:
        import app.codirector.vision.api as vision_api

        monkeypatch.setattr(vision_api, "feature_flags", fresh)
    except Exception:
        pass

    try:
        import app.codirector.service as cd_svc

        monkeypatch.setattr(cd_svc, "feature_flags", fresh)
    except Exception:
        pass

    try:
        import app.codirector.tools.handlers.timeline_references as tr_handlers

        monkeypatch.setattr(tr_handlers, "feature_flags", fresh)
    except Exception:
        pass

    return fresh


def iter_flag_matrix(combos: Iterable[FlagCombo] | None = None) -> Iterable[FlagCombo]:
    return combos if combos is not None else FLAG_MATRIX
