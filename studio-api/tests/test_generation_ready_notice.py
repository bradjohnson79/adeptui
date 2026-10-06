"""Tests for Co-Director generation ready notices."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.codirector.execution.generation_ready_notice import (
    EMITTED_KEY,
    LINK_KEY,
    build_cancel_copy,
    build_fail_copy,
    build_ready_copy,
    is_cd_linked,
    media_kind_for_plan,
    maybe_emit_generation_ready_notice,
    notice_message_id,
    stamp_generation_link,
)


def test_media_kind_mapping():
    assert media_kind_for_plan(SimpleNamespace(capability="image.generate", surface_type="", plan_data={})) == "image"
    assert media_kind_for_plan(SimpleNamespace(capability="video.generate", surface_type="", plan_data={})) == "video"
    assert media_kind_for_plan(SimpleNamespace(capability="audio.sfx", surface_type="", plan_data={})) == "sfx"
    assert media_kind_for_plan(SimpleNamespace(capability="audio.ambience", surface_type="", plan_data={})) == "ambience"
    assert media_kind_for_plan(SimpleNamespace(capability="audio.music", surface_type="", plan_data={})) == "music"
    assert media_kind_for_plan(SimpleNamespace(capability="voice.generate", surface_type="", plan_data={})) == "voice"


def test_ready_copy_variants():
    assert build_ready_copy("image") == ("Your image is ready.", "View image")
    assert build_ready_copy("video") == ("Your video is ready.", "View video")
    assert build_ready_copy("sfx") == ("Your sound effect is ready.", "Listen")
    assert build_ready_copy("ambience") == ("Your ambience is ready.", "Listen")
    assert build_ready_copy("music") == ("Your music cue is ready.", "Listen")
    assert build_ready_copy("voice", subject="Lar") == ("Lar's voice clip is ready.", "Listen")
    assert build_ready_copy("voice") == ("Your voice clip is ready.", "Listen")


def test_fail_and_cancel_copy_no_ids():
    sentence, action = build_fail_copy("music")
    assert "couldn't be completed" in sentence
    assert action == "Details"
    assert "job" not in sentence.lower()
    assert build_cancel_copy("video") == "The video generation was cancelled."


def test_notice_message_id_stable_and_bounded():
    eid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    mid = notice_message_id(eid)
    assert mid == f"genrdy:{eid}"
    assert len(mid) <= 64
    assert notice_message_id(eid) == mid


def test_stamp_and_link_detection():
    plan = SimpleNamespace(plan_data={}, user_turn_id="turn-1", classifier_source="")
    assert stamp_generation_link(plan, request_id="turn-1") is True
    assert plan.plan_data[LINK_KEY]["linked"] is True
    assert plan.plan_data[LINK_KEY]["requestId"] == "turn-1"
    assert is_cd_linked(plan) is True
    assert stamp_generation_link(plan, request_id="turn-1") is False  # idempotent


def test_running_does_not_emit(monkeypatch):
    plan = SimpleNamespace(
        execution_id="exec-1",
        capability="image.generate",
        status="running",
        plan_data={LINK_KEY: {"linked": True, "requestId": "t1"}},
        user_turn_id="t1",
        result_asset_ids=[],
        child_jobs=[],
        error=None,
    )
    assert maybe_emit_generation_ready_notice(MagicMock(), "proj", plan, previous_status="queued") is None


def test_ready_emits_once_with_verified_asset(tmp_path, monkeypatch):
    asset_path = tmp_path / "out.png"
    asset_path.write_bytes(b"png")

    class FakeAsset:
        def __init__(self):
            self.path = str(asset_path)

    db = MagicMock()
    db.get.return_value = FakeAsset()

    appended = []

    class Batch:
        duplicate_count = 0

    def fake_append(db, project_id, events, **kwargs):
        appended.extend(list(events))
        return Batch()

    monkeypatch.setattr(
        "app.codirector.conversation_events.append_events",
        fake_append,
        raising=False,
    )
    # Import path used inside maybe_emit
    import app.codirector.execution.generation_ready_notice as mod

    monkeypatch.setattr(
        mod,
        "maybe_emit_generation_ready_notice",
        mod.maybe_emit_generation_ready_notice,
    )

    # Patch the import inside the function by injecting module
    import sys
    from types import ModuleType

    conv = ModuleType("app.codirector.conversation_events")
    conv.EventInput = lambda **kw: SimpleNamespace(**kw)
    conv.append_events = fake_append
    monkeypatch.setitem(sys.modules, "app.codirector.conversation_events", conv)

    # Also need db.get for Asset — patch _asset_accessible via Asset import
    asset_mod = ModuleType("app.db")
    asset_mod.Asset = object
    # The function does `from ...db import Asset` then db.get(Asset, id)
    # Our db.get already returns FakeAsset.

    plan = SimpleNamespace(
        execution_id="exec-ready-1",
        capability="image.generate",
        status="completed",
        plan_data={LINK_KEY: {"linked": True, "requestId": "t1"}},
        user_turn_id="t1",
        result_asset_ids=["asset-1"],
        child_jobs=[],
        error=None,
        surface_type="image_generation",
        classifier_source="deterministic",
    )

    # Monkeypatch _asset_accessible directly
    monkeypatch.setattr(mod, "_asset_accessible", lambda db, aid: aid == "asset-1")

    first = mod.maybe_emit_generation_ready_notice(db, "proj", plan, previous_status="running")
    assert first is not None
    assert first["outcome"] == "ready"
    assert first["assetId"] == "asset-1"
    assert "Your image is ready." in first["content"]
    assert "asset-1" not in first["content"]
    assert len(appended) == 1
    assert appended[0].message_id == notice_message_id("exec-ready-1")
    assert appended[0].message_type == "answer"
    assert plan.plan_data[EMITTED_KEY]["messageId"] == notice_message_id("exec-ready-1")

    # Second call — exactly-once via emitted stamp
    second = mod.maybe_emit_generation_ready_notice(db, "proj", plan, previous_status="completed")
    assert second is not None
    assert second["messageId"] == first["messageId"]
    assert len(appended) == 1


def test_fail_notice_keeps_tech_out_of_sentence(monkeypatch):
    import sys
    from types import ModuleType

    appended = []

    class Batch:
        duplicate_count = 0

    def fake_append(db, project_id, events, **kwargs):
        appended.extend(list(events))
        return Batch()

    conv = ModuleType("app.codirector.conversation_events")
    conv.EventInput = lambda **kw: SimpleNamespace(**kw)
    conv.append_events = fake_append
    monkeypatch.setitem(sys.modules, "app.codirector.conversation_events", conv)

    import app.codirector.execution.generation_ready_notice as mod

    plan = SimpleNamespace(
        execution_id="exec-fail-1",
        capability="audio.music",
        status="failed",
        plan_data={LINK_KEY: {"linked": True}},
        user_turn_id="t1",
        result_asset_ids=[],
        child_jobs=[SimpleNamespace(asset_id=None, error="ProviderTimeout: fal 504")],
        error="ProviderTimeout: fal 504",
        surface_type="",
        classifier_source="deterministic",
    )
    out = mod.maybe_emit_generation_ready_notice(MagicMock(), "proj", plan, previous_status="running")
    assert out is not None
    assert out["outcome"] == "failed"
    assert "couldn't be completed" in out["content"]
    assert "ProviderTimeout" not in out["content"]
    assert "fal 504" not in out["content"]
    assert out["technical"] and "ProviderTimeout" in out["technical"]
    assert appended[0].attachments[0]["actionLabel"] == "Details"


def test_cancel_never_ready(monkeypatch):
    import sys
    from types import ModuleType

    appended = []

    class Batch:
        duplicate_count = 0

    def fake_append(db, project_id, events, **kwargs):
        appended.extend(list(events))
        return Batch()

    conv = ModuleType("app.codirector.conversation_events")
    conv.EventInput = lambda **kw: SimpleNamespace(**kw)
    conv.append_events = fake_append
    monkeypatch.setitem(sys.modules, "app.codirector.conversation_events", conv)

    import app.codirector.execution.generation_ready_notice as mod

    plan = SimpleNamespace(
        execution_id="exec-cancel-1",
        capability="video.generate",
        status="cancelled",
        plan_data={LINK_KEY: {"linked": True}},
        user_turn_id="t1",
        result_asset_ids=["should-not-use"],
        child_jobs=[],
        error=None,
        surface_type="",
        classifier_source="deterministic",
    )
    out = mod.maybe_emit_generation_ready_notice(MagicMock(), "proj", plan, previous_status="running")
    assert out is not None
    assert out["outcome"] == "cancelled"
    assert "cancelled" in out["content"].lower()
    assert "ready" not in out["content"].lower()
    assert out.get("assetId") is None


def test_historical_same_terminal_skipped(monkeypatch):
    """Do not flood historical jobs when previous status already matches terminal."""
    import app.codirector.execution.generation_ready_notice as mod

    plan = SimpleNamespace(
        execution_id="exec-hist-1",
        capability="image.generate",
        status="completed",
        plan_data={LINK_KEY: {"linked": True}},
        user_turn_id="t1",
        result_asset_ids=["a1"],
        child_jobs=[],
        error=None,
        surface_type="",
        classifier_source="deterministic",
    )
    # No emitted stamp, but previous already completed — hydrate/flood guard
    assert (
        mod.maybe_emit_generation_ready_notice(
            MagicMock(), "proj", plan, previous_status="completed"
        )
        is None
    )


def test_legacy_invocation_untouched():
    """This feature must not record legacy_invocation entries."""
    from app.codirector.durable import journal

    before = journal.legacy_names()
    from app.codirector.execution import generation_ready_notice as mod

    assert hasattr(mod, "maybe_emit_generation_ready_notice")
    after = journal.legacy_names()
    assert after == before
