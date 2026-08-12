"""Regression: prefer Comfy history fullpath when Shared output dir differs."""

from pathlib import Path

from app.comfy_client import ComfyClient


def test_find_output_files_uses_fullpath(tmp_path: Path):
    mp4 = tmp_path / "clip.mp4"
    mp4.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64)
    history = {
        "outputs": {
            "15": {
                "gifs": [
                    {
                        "filename": "missing_under_settings_dir.mp4",
                        "subfolder": "studio",
                        "type": "output",
                        "fullpath": str(mp4),
                    }
                ]
            }
        }
    }
    found = ComfyClient().find_output_files(history)
    assert found == [mp4]
