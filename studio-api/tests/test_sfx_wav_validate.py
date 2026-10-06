from pathlib import Path

from app.audio_studio.sfx_wav_validate import validate_sfx_wav


def test_missing_file_fails(tmp_path: Path):
    out = validate_sfx_wav(tmp_path / "nope.wav")
    assert out["ok"] is False


def test_tiny_file_fails(tmp_path: Path):
    p = tmp_path / "tiny.wav"
    p.write_bytes(b"RIFF")
    out = validate_sfx_wav(p)
    assert out["ok"] is False


def test_real_size_undecodable_file_is_not_rejected(tmp_path: Path):
    p = tmp_path / "floatish.wav"
    p.write_bytes(b"RIFFxxxxWAVEfmt " + b"\x00" * 1200)
    out = validate_sfx_wav(p, expected_duration_sec=3)
    assert out["ok"] is True
    assert out["bytes"] >= 1000
