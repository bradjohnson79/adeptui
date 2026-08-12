"""M3.0h local-first routing: no silent fal; LOCAL-16 start-frame blocker."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.engine_recommend import recommend_engine, resolve_engine_id
from app.local_first import (
    LOCAL_START_FRAME_REQUIRED,
    PAID_FAL_APPROVAL_REQUIRED,
    assert_fal_allowed,
    local_start_frame_blocker,
    paid_fallback_approved,
)
from app.codirector.model_intelligence.registry import ENGINE_TO_MODEL


def test_auto_maps_to_ltx_not_fal_seedance():
    assert ENGINE_TO_MODEL["auto"] == "ltx_2_3"


def test_recommend_engine_stays_local_even_with_fal_key(monkeypatch):
    monkeypatch.setattr(
        "app.engine_recommend.secret_status",
        lambda _k: {"configured": True},
    )
    project = SimpleNamespace(vram_gb=24, global_prompt="", negative_prompt="")
    scene = SimpleNamespace(
        duration_sec=5,
        lipsync_enabled=0,
        prompt="cinematic slow push-in, no music, no background",
        start_asset_id=None,
        engine="auto",
    )
    rec = recommend_engine(project=project, scene=scene)
    assert rec["local"] is True
    assert not str(rec["engineId"]).startswith("fal_")
    assert rec["engineId"] in ("ltx", "wan")
    assert rec.get("requiresStartFrame") is True


def test_resolve_auto_never_returns_fal(monkeypatch):
    monkeypatch.setattr(
        "app.engine_recommend.secret_status",
        lambda _k: {"configured": True},
    )
    project = SimpleNamespace(vram_gb=12, global_prompt="")
    scene = SimpleNamespace(
        duration_sec=4,
        lipsync_enabled=0,
        prompt="camera pan chase sequence",
        start_asset_id=None,
        engine="auto",
    )
    assert resolve_engine_id("auto", project, scene) in ("ltx", "wan")


def test_local_start_frame_blocker_prefers_local_still():
    blocker = local_start_frame_blocker(preferred_engine="ltx")
    assert blocker["code"] == LOCAL_START_FRAME_REQUIRED
    assert blocker["preferredAction"] == "generate_local_start_frame"
    assert blocker["falSubmissionAllowedWithoutApproval"] is False


def test_assert_fal_requires_approval():
    with pytest.raises(RuntimeError) as exc:
        assert_fal_allowed({}, engine="fal_seedance")
    payload = json.loads(str(exc.value))
    assert payload["code"] == PAID_FAL_APPROVAL_REQUIRED

    assert_fal_allowed({"paidFallbackApproved": True}, engine="fal_seedance")
    assert paid_fallback_approved({"paidFallbackApproved": True}) is True
