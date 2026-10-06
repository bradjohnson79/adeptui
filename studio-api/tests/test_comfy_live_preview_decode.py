"""Comfy WS preview packets must decode without a fake prompt_id header."""

from __future__ import annotations

import json
import struct

from app.video_runtime.live_preview import decode_comfy_ws_preview


JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def _legacy_pid_packet(prompt_id: str, image: bytes) -> bytes:
    pid = prompt_id.encode("utf-8")
    return struct.pack(">I", 1) + struct.pack(">I", len(pid)) + pid + image


def test_decode_comfy_type1_jpeg_without_prompt_id() -> None:
    raw = struct.pack(">I", 1) + struct.pack(">I", 1) + JPEG
    # Old decoder treated type_num=1 as pid_len and dropped the frame.
    assert decode_comfy_ws_preview(raw, "26c6d762-ad6b-4fea-bf4f-58630c47feb1") == JPEG


def test_decode_comfy_type4_metadata_jpeg() -> None:
    meta = json.dumps({"prompt_id": "pid-1", "node": "10"}).encode("utf-8")
    raw = struct.pack(">I", 4) + struct.pack(">I", len(meta)) + meta + JPEG
    assert decode_comfy_ws_preview(raw, "pid-1") == JPEG
    assert decode_comfy_ws_preview(raw, "other") is None


def test_decode_legacy_adept_pid_header_still_works() -> None:
    raw = _legacy_pid_packet("prompt-abc", PNG)
    assert decode_comfy_ws_preview(raw, "prompt-abc") == PNG
    assert decode_comfy_ws_preview(raw, "nope") is None


def test_decode_ignores_unknown_event() -> None:
    raw = struct.pack(">I", 99) + struct.pack(">I", 1) + JPEG
    assert decode_comfy_ws_preview(raw) is None
