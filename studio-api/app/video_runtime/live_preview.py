"""Live low-res preview tap for Comfy-backed generation.

Connects to the Comfy WebSocket and listens for binary latent-preview messages
(the same side-channel ComfyUI's own UI uses for during-render previews).
Each frame is republished to the Adept preview bus. Preview failure never
fails the actual generation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import struct
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

# Comfy BinaryEventTypes (protocol.py):
#   1 PREVIEW_IMAGE
#   2 UNENCODED_PREVIEW_IMAGE
#   4 PREVIEW_IMAGE_WITH_METADATA
_PREVIEW_IMAGE = 1
_PREVIEW_IMAGE_WITH_METADATA = 4

OnFrame = Callable[[bytes], Any]
OnEvent = Callable[[str, dict[str, Any]], Any]


def _looks_like_image(data: bytes) -> bool:
    if len(data) < 8:
        return False
    if data[:2] == b"\xff\xd8":
        return True
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return True
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return True
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return True
    return False


def decode_comfy_ws_preview(raw: bytes, prompt_id: str = "") -> bytes | None:
    """Extract JPEG/PNG bytes from a Comfy WebSocket binary preview.

    Current Comfy (0.30 / 0.32) does **not** prefix a prompt_id on type 1.
    Type 1 payload is ``image_type_u32 + jpeg/png``.
    Type 4 payload is ``meta_len_u32 + json + jpeg/png``.

    An older Adept decoder treated the type-1 image-type word as a prompt_id
    length and dropped every frame. Do not restore that.
    """
    if not isinstance(raw, (bytes, bytearray)) or len(raw) < 8:
        return None
    try:
        event_type = struct.unpack(">I", raw[:4])[0]
    except struct.error:
        return None
    payload = bytes(raw[4:])
    wanted = (prompt_id or "").strip()

    if event_type == _PREVIEW_IMAGE_WITH_METADATA:
        if len(payload) < 4:
            return None
        meta_len = struct.unpack(">I", payload[:4])[0]
        if meta_len < 0 or 4 + meta_len > len(payload):
            return None
        meta_raw = payload[4 : 4 + meta_len]
        image = payload[4 + meta_len :]
        if wanted:
            try:
                meta = json.loads(meta_raw.decode("utf-8", "replace"))
            except Exception:
                meta = {}
            if isinstance(meta, dict):
                pid = str(meta.get("prompt_id") or meta.get("promptId") or "").strip()
                if pid and pid != wanted:
                    return None
        return bytes(image) if _looks_like_image(image) else None

    if event_type != _PREVIEW_IMAGE:
        return None

    # Canonical Comfy: 4-byte image type (1=JPEG, 2=PNG) + encoded image.
    image = payload[4:]
    if _looks_like_image(image):
        return bytes(image)

    # Legacy Adept header: prompt_id length + prompt_id + image.
    try:
        pid_len = struct.unpack(">I", payload[:4])[0]
    except struct.error:
        return None
    if pid_len <= 0 or pid_len > 256 or 4 + pid_len > len(payload):
        return None
    pid = payload[4 : 4 + pid_len].decode("utf-8", "replace").strip()
    image = payload[4 + pid_len :]
    if wanted and pid and pid != wanted:
        return None
    return bytes(image) if _looks_like_image(image) else None


def _emit_event(on_event: OnEvent | None, mtype: str, data: dict[str, Any]) -> None:
    if on_event is None:
        return
    try:
        result = on_event(mtype, data)
        if hasattr(result, "__await__"):
            return
    except Exception:
        logger.debug("Preview status callback failed", exc_info=True)


async def _emit_event_async(on_event: OnEvent | None, mtype: str, data: dict[str, Any]) -> None:
    if on_event is None:
        return
    try:
        result = on_event(mtype, data)
        if hasattr(result, "__await__"):
            await result
    except Exception:
        logger.debug("Preview status callback failed", exc_info=True)


def _json_status(raw: Any) -> tuple[str, dict[str, Any]] | None:
    try:
        msg = json.loads(raw) if isinstance(raw, (str, bytes, bytearray)) else raw
    except Exception:
        return None
    if not isinstance(msg, dict):
        return None
    mtype = str(msg.get("type") or "")
    data = msg.get("data") if isinstance(msg.get("data"), dict) else {}
    if not mtype:
        return None
    return mtype, data


async def tap_comfy_previews(
    base_url: str,
    client_id: str,
    prompt_id: str,
    on_frame: Callable[[bytes], Awaitable[None]],
    *,
    max_frames: int = 240,
    on_event: OnEvent | None = None,
) -> None:
    """Subscribe to Comfy WebSocket and forward latent preview frames.

    Runs until the prompt completes or the task is cancelled. Never raises —
    a preview failure must not fail the render.
    """
    try:
        import websockets
    except Exception:
        logger.debug("websockets not installed — live preview tap disabled")
        return

    ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{ws_url}/ws?clientId={client_id}"
    frames = 0
    wanted = (prompt_id or "").strip()
    try:
        async with websockets.connect(ws_url, max_size=32 * 1024 * 1024, open_timeout=10) as ws:
            try:
                await ws.send(json.dumps({
                    "type": "feature_flags",
                    "data": {"supports_preview_metadata": True},
                }))
            except Exception:
                logger.debug("Could not announce Comfy preview feature flags", exc_info=True)
            async for raw in ws:
                if frames >= max_frames:
                    return
                if isinstance(raw, (bytes, bytearray)):
                    image_bytes = decode_comfy_ws_preview(bytes(raw), wanted)
                    if not image_bytes:
                        continue
                    frames += 1
                    try:
                        await on_frame(image_bytes)
                    except Exception:
                        logger.debug("Preview frame callback failed", exc_info=True)
                    continue
                parsed = _json_status(raw)
                if not parsed:
                    continue
                mtype, data = parsed
                pid = str(data.get("prompt_id") or "").strip()
                if wanted and pid and pid != wanted:
                    continue
                await _emit_event_async(on_event, mtype, data)
                if mtype == "executing" and data.get("node") is None:
                    return
                if mtype == "execution_error":
                    return
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.debug("Live preview tap ended", exc_info=True)


def tap_comfy_previews_sync(
    base_url: str,
    client_id: str,
    prompt_id: str,
    on_frame: Callable[[bytes], None],
    stop: Any,
    *,
    max_frames: int = 240,
    on_event: OnEvent | None = None,
) -> None:
    """Sync variant for Route A (blocking poll thread). Never raises."""
    try:
        import websocket  # websocket-client
    except Exception:
        logger.debug("websocket-client not installed — live preview tap disabled")
        return

    ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{ws_url}/ws?clientId={client_id}"
    frames = 0
    wanted = (prompt_id or "").strip()
    try:
        ws = websocket.create_connection(ws_url, timeout=10, max_size=32 * 1024 * 1024)
        ws.settimeout(2)
        try:
            ws.send(json.dumps({
                "type": "feature_flags",
                "data": {"supports_preview_metadata": True},
            }))
        except Exception:
            logger.debug("Could not announce Comfy preview feature flags", exc_info=True)
        while not stop.is_set() and frames < max_frames:
            try:
                raw = ws.recv()
            except Exception:
                continue
            if isinstance(raw, (bytes, bytearray)):
                image_bytes = decode_comfy_ws_preview(bytes(raw), wanted)
                if not image_bytes:
                    continue
                frames += 1
                try:
                    on_frame(image_bytes)
                except Exception:
                    logger.debug("Preview frame callback failed", exc_info=True)
                continue
            parsed = _json_status(raw)
            if not parsed:
                continue
            mtype, data = parsed
            pid = str(data.get("prompt_id") or "").strip()
            if wanted and pid and pid != wanted:
                continue
            _emit_event(on_event, mtype, data)
            if mtype == "executing" and data.get("node") is None:
                break
            if mtype == "execution_error":
                break
        try:
            ws.close()
        except Exception:
            pass
    except Exception:
        logger.debug("Live preview tap ended", exc_info=True)
