"""Library assets stage into Comfy input from durable ids, not display names."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.video_runtime.comfy_asset_stage import (
    ComfyAssetMissing,
    stage_library_asset,
    staged_comfy_name,
)


def test_staged_name_uses_asset_id_not_display_filename(tmp_path):
    src = tmp_path / "Anadriya Clone clone sample 4.wav"
    src.write_bytes(b"RIFF....WAVE")
    name = staged_comfy_name("e3a305b6-a9c3-4ab1-9508-4b0e030ae2d5", src)
    assert name == "studio/e3a305b6-a9c3-4ab1-9508-4b0e030ae2d5.wav"
    assert "Anadriya" not in name
    assert "clone sample" not in name


def test_stage_copies_from_library_path_and_ignores_stale_comfy_name(tmp_path):
    src = tmp_path / "clone_65d584da7d.wav"
    src.write_bytes(b"x" * 2048)
    input_dir = tmp_path / "input"
    asset = SimpleNamespace(
        id="asset-voice-1",
        path=str(src),
        filename="Someone Clone clone sample 4.wav",
        comfy_name="studio/Someone Clone clone sample 4.wav",
        kind="audio",
    )
    staged = stage_library_asset(asset, input_dir=input_dir)
    assert staged.comfy_name == "studio/asset-voice-1.wav"
    assert staged.reused is False
    dest = input_dir / "studio" / "asset-voice-1.wav"
    assert dest.is_file()
    assert dest.stat().st_size == 2048
    again = stage_library_asset(asset, input_dir=input_dir)
    assert again.reused is True


def test_h3_loadaudio_binds_staged_asset_id_not_label(tmp_path):
    from app.workflows.h3_ref2v_builder import assert_h3_ref2v_graph, build_h3_ref2v

    wav = tmp_path / "Anadriya Clone clone sample 4.wav"
    png = tmp_path / "Dialogue face.png"
    wav.write_bytes(b"x" * 2048)
    png.write_bytes(b"png")
    voice_id = "e3a305b6-a9c3-4ab1-9508-4b0e030ae2d5"
    picture_id = "a97963c4-09b3-402b-8341-8f0539b4bc0b"
    voice = SimpleNamespace(
        id=voice_id,
        path=str(wav),
        filename=wav.name,
        comfy_name="studio/Anadriya Clone clone sample 4.wav",
    )
    picture = SimpleNamespace(
        id=picture_id,
        path=str(png),
        filename=png.name,
        comfy_name="studio/Dialogue face.png",
    )
    input_dir = tmp_path / "input"
    staged_voice = stage_library_asset(voice, input_dir=input_dir)
    staged_picture = stage_library_asset(picture, input_dir=input_dir)
    assert staged_voice.comfy_name == f"studio/{voice_id}.wav"
    assert staged_picture.comfy_name == f"studio/{picture_id}.png"
    graph = build_h3_ref2v(
        prompt="<Picture 1> walk",
        ref_comfy_names=[staged_picture.comfy_name],
        filename_prefix="studio/h3",
        seed=1,
        length=5,
        ref_audio_comfy_names=[staged_voice.comfy_name],
    )
    assert_h3_ref2v_graph(
        graph,
        expected_names=[staged_picture.comfy_name],
        expected_audio_names=[staged_voice.comfy_name],
    )
    audio_bound = [
        str((node.get("inputs") or {}).get("audio") or "")
        for node in graph.values()
        if isinstance(node, dict) and node.get("class_type") == "LoadAudio"
    ]
    assert audio_bound == [f"studio/{voice_id}.wav"]
    assert all("clone sample" not in name and "Dialogue" not in name for name in audio_bound)


def test_stage_refuses_missing_library_file(tmp_path):
    asset = SimpleNamespace(
        id="missing-1",
        path=str(tmp_path / "gone.wav"),
        filename="gone.wav",
        comfy_name="studio/gone.wav",
        kind="audio",
    )
    with pytest.raises(ComfyAssetMissing):
        stage_library_asset(asset, input_dir=tmp_path / "input")
