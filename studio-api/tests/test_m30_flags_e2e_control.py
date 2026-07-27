"""M3.0 Completion Phase 3: the E2E-only feature-flag control and flag serialization.

`unifiedExperienceEnabled` decides which Co-Director surface the browser renders, so the
control has to move the *live* flag object -- several modules bound it by value at import
time -- and the shipped defaults must stay off.
"""

from __future__ import annotations

import os
from dataclasses import fields as dataclass_fields

import pytest
from fastapi import HTTPException

from app import feature_flags as feature_flags_mod
from app.routers.e2e import e2e_feature_flags

UNIFIED = "codirector_unified_experience_v1"


@pytest.fixture()
def e2e_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STUDIO_E2E", "1")
    singleton = feature_flags_mod.feature_flags
    before = {f.name: getattr(singleton, f.name) for f in dataclass_fields(type(singleton))}
    yield
    for name, value in before.items():
        object.__setattr__(singleton, name, value)


def test_control_is_disabled_without_studio_e2e(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STUDIO_E2E", raising=False)
    with pytest.raises(HTTPException) as exc:
        e2e_feature_flags({"flags": {UNIFIED: True}})
    assert exc.value.status_code == 404


def test_unknown_flag_is_rejected(e2e_env) -> None:
    with pytest.raises(HTTPException) as exc:
        e2e_feature_flags({"flags": {"not_a_real_flag_v1": True}})
    assert exc.value.status_code == 400


def test_empty_body_is_rejected(e2e_env) -> None:
    with pytest.raises(HTTPException) as exc:
        e2e_feature_flags({})
    assert exc.value.status_code == 400


def test_toggle_mutates_the_live_flag_object(e2e_env) -> None:
    """Modules such as `codirector.service` bound this object at import; never replace it."""
    singleton = feature_flags_mod.feature_flags

    out = e2e_feature_flags({"flags": {UNIFIED: True}})
    assert out["flags"][UNIFIED] is True
    assert feature_flags_mod.feature_flags is singleton, "flag object was replaced, not updated"
    assert singleton.codirector_unified_experience_v1 is True

    e2e_feature_flags({"flags": {UNIFIED: False}})
    assert feature_flags_mod.feature_flags is singleton
    assert singleton.codirector_unified_experience_v1 is False


def test_null_clears_the_env_override(e2e_env) -> None:
    env_name = f"STUDIO_FEATURE_{UNIFIED.upper()}"
    e2e_feature_flags({"flags": {UNIFIED: True}})
    assert os.environ.get(env_name) == "1"

    e2e_feature_flags({"flags": {UNIFIED: None}})
    assert env_name not in os.environ
    assert feature_flags_mod.feature_flags.codirector_unified_experience_v1 is False


def test_shipped_defaults_stay_off() -> None:
    flags = feature_flags_mod.FeatureFlags.from_env({})
    assert flags.codirector_unified_experience_v1 is False
    assert flags.audio_production_v1 is False
    assert flags.director_timeline_v1 is False


def test_codirector_health_serializes_the_unified_flag() -> None:
    from app.codirector.providers.base import ProviderHealthResult

    health = ProviderHealthResult(
        provider_id="mock",
        display_name="Mock",
        status="Ready",
        reachable=True,
        endpoint="mock://codirector",
        selected_model="mock-model",
        model_available=True,
    )
    health.unified_experience_enabled = True
    payload = health.to_dict()
    assert payload["unifiedExperienceEnabled"] is True
    assert "audioProductionEnabled" in payload
    assert "directorTimelineEnabled" in payload
