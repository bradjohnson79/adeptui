"""Phase 5 prop advanced angle sequential session tests."""

from __future__ import annotations

from app.image_runtime.prop_angle_session import (
    MAX_INFLIGHT,
    begin_angle,
    clear_sessions,
    is_prop_advanced_angle_params,
    note_angle_cancelled,
    note_angle_completed,
    release_inflight,
    should_preserve_residency_on_cancel,
)
from app.image_runtime.ref_encode_cache import (
    build_ref_encode_key,
    classify_encode_cache,
    clear_ref_encode_session,
    last_shared_digest,
    NODE_LOAD_IMAGE,
    NODE_NEG_ENCODE,
)


def setup_function():
    clear_sessions()
    clear_ref_encode_session()


def test_max_inflight_is_one():
    assert MAX_INFLIGHT == 1


def test_begin_angle_rejects_second_inflight():
    begin_angle(prop_id="p1", primary_asset_id="a1", angle="front", job_id="j1")
    try:
        begin_angle(prop_id="p1", primary_asset_id="a1", angle="back", job_id="j2")
        assert False, "expected busy"
    except RuntimeError as exc:
        assert "busy" in str(exc).lower() or "maxInFlight" in str(exc)


def test_complete_releases_and_allows_next():
    begin_angle(prop_id="p1", primary_asset_id="a1", angle="front", job_id="j1")
    note_angle_completed("j1", angle="front")
    meta = begin_angle(prop_id="p1", primary_asset_id="a1", angle="back", job_id="j2")
    assert meta["sessionId"]
    assert meta["sessionSeq"] == 2
    assert meta["maxInFlight"] == 1


def test_cancel_preserves_ref_encode_session(tmp_path):
    img = tmp_path / "ref.png"
    img.write_bytes(b"png")
    key = build_ref_encode_key(
        ref_asset_id="a1",
        ref_path=img,
        prompt="front",
        negative="neg",
        workflow_key="qwen_edit_2509.edit",
        width=768,
        height=768,
    )
    classify_encode_cache(key=key, cached_nodes=[NODE_LOAD_IMAGE, NODE_NEG_ENCODE], stage_reused=True)
    shared_before = last_shared_digest()
    assert shared_before

    begin_angle(prop_id="p1", primary_asset_id="a1", angle="left", job_id="j-cancel")
    meta = note_angle_cancelled("j-cancel", angle="left")
    assert meta["cachePreserved"] is True
    assert meta["sharedDigestPresent"] is True
    assert last_shared_digest() == shared_before

    # Next angle can still classify against preserved shared digest.
    key2 = build_ref_encode_key(
        ref_asset_id="a1",
        ref_path=img,
        prompt="right view different",
        negative="neg",
        workflow_key="qwen_edit_2509.edit",
        width=768,
        height=768,
    )
    report = classify_encode_cache(
        key=key2,
        cached_nodes=[NODE_LOAD_IMAGE, NODE_NEG_ENCODE],
        stage_reused=True,
    )
    assert report["sharedKeyMatch"] is True
    assert report["hit"] is True


def test_release_inflight_unsticks():
    begin_angle(prop_id="p1", primary_asset_id="a1", angle="top", job_id="j-stuck")
    release_inflight("j-stuck")
    meta = begin_angle(prop_id="p1", primary_asset_id="a1", angle="bottom", job_id="j-next")
    assert meta["inflightJobId"] == "j-next"


def test_detect_prop_advanced_angle_params():
    assert is_prop_advanced_angle_params({"purpose": "project_prop_angle"})
    assert is_prop_advanced_angle_params(
        {"creativeContext": {"taskType": "PROP_ADVANCED_ANGLE"}}
    )
    assert should_preserve_residency_on_cancel({"purpose": "project_prop_angle"})
    assert not should_preserve_residency_on_cancel({"purpose": "other"})
