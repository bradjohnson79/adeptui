"""Stitch must remux when concat-copy drops MiniMax AAC."""

from __future__ import annotations

from pathlib import Path

from app.media_ops import _audio_preserving_concat_args, stitch_needs_audio_remux


def test_stitch_needs_audio_remux_when_output_silent_and_input_has_audio(tmp_path, monkeypatch):
    a = tmp_path / "a.mp4"
    b = tmp_path / "b.mp4"
    out = tmp_path / "out.mp4"
    a.write_bytes(b"a")
    b.write_bytes(b"b")
    out.write_bytes(b"out")

    def fake_probe(path: Path) -> bool:
        return path.name in {"a.mp4", "b.mp4"}

    monkeypatch.setattr("app.media_ops._probe_has_audio", fake_probe)
    assert stitch_needs_audio_remux([a, b], out) is True


def test_stitch_needs_audio_remux_false_when_output_has_audio(tmp_path, monkeypatch):
    a = tmp_path / "a.mp4"
    out = tmp_path / "out.mp4"
    a.write_bytes(b"a")
    out.write_bytes(b"out")
    monkeypatch.setattr("app.media_ops._probe_has_audio", lambda path: True)
    assert stitch_needs_audio_remux([a], out) is False


def test_audio_preserving_concat_maps_video_and_audio(tmp_path, monkeypatch):
    a = tmp_path / "a.mp4"
    b = tmp_path / "b.mp4"
    out = tmp_path / "out.mp4"
    a.write_bytes(b"a")
    b.write_bytes(b"b")
    monkeypatch.setattr("app.media_ops._probe_has_audio", lambda path: path.name == "a.mp4")
    args = _audio_preserving_concat_args([a, b], out, 24)
    assert "-filter_complex" in args
    fc = args[args.index("-filter_complex") + 1]
    assert "concat=n=2:v=1:a=1[v][a]" in fc
    assert "-map" in args
    assert "[a]" in args
    assert "-c:a" in args
    assert "aac" in args
    assert any("anullsrc" in str(item) for item in args)
