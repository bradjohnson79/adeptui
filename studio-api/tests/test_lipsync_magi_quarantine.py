"""Timeline must not treat LatentSync / lipsync_output_path as Preview authority."""

from app.workflows.lipsync_magi_quarantine import (
    shelved_latentsync_builders,
    timeline_may_use_lipsync_playback,
)


def test_timeline_lipsync_playback_disabled_by_default(monkeypatch):
    monkeypatch.delenv("STUDIO_TIMELINE_LIPSYNC_PLAYBACK", raising=False)
    assert timeline_may_use_lipsync_playback() is False


def test_timeline_lipsync_playback_flag_opt_in(monkeypatch):
    monkeypatch.setenv("STUDIO_TIMELINE_LIPSYNC_PLAYBACK", "1")
    assert timeline_may_use_lipsync_playback() is True


def test_shelved_builders_expose_latentsync_without_timeline_coupling():
    shelf = shelved_latentsync_builders()
    assert callable(shelf["build_latentsync_workflow"])
    assert "MAGI" in shelf["note"]
    assert "video_clips" in shelf["note"]
