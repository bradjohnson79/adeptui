"""Shared Co-Director vision input: load pixels, detect visual turns, keep images[]."""

from __future__ import annotations

import base64
import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import VISION_UNAVAILABLE, CoDirectorError

DEFAULT_VISION_MAX_DIM = 1536
CRS_SHEET_MAX_DIM = 2048

_VISUAL_TURN_RE = re.compile(
    r"\b("
    r"describe|visible|hairstyle|hair(?:style)?|clothing|outfit|wearing|footwear|"
    r"markings?|pattern|pose|earrings?|jewelry|eyes?|ears?|from (?:her|his|the) current|"
    r"in this image|in the (?:attached |current )?image|look at|what color|"
    r"what do you see|what(?:'s| is) in (?:this|the) (?:image|picture|photo|attachment)|"
    r"more like (?:this|the attached|what you see)|match(?:es)? the (?:lighting|style|materials)|"
    r"use this as|visual reference|the attached|this (?:picture|photo|attachment)|"
    r"which (?:one|image) is|compare (?:these|the) (?:images|pictures)|"
    r"visual (?:details?|reference|context|style)"
    r")\b",
    re.IGNORECASE,
)


class VisionLoadError(Exception):
    def __init__(self, reason: str, asset_id: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.asset_id = asset_id


@dataclass
class LoadedVisionImage:
    asset_id: str
    jpeg_bytes: bytes
    width: int
    height: int
    mime: str = "image/jpeg"
    source: str = "attachment"


def is_visual_inspection_turn(text: str | None) -> bool:
    raw = text or ""
    try:
        from .conversation.foundation.speech_act import (
            classify_speech_act,
            is_crs_create_action,
            resolve_production_action,
        )

        if classify_speech_act(raw) == "COMMAND" and is_crs_create_action(
            resolve_production_action(raw)
        ):
            return False
    except Exception:
        pass
    return bool(_VISUAL_TURN_RE.search(raw))


def vision_unavailable(reason: str, *, details: dict[str, Any] | None = None) -> CoDirectorError:
    clean = (reason or "the picture could not be used").strip()
    if clean.lower().startswith("vision input failed"):
        message = clean
    else:
        message = f"Vision input failed: {clean}"
    return CoDirectorError(
        VISION_UNAVAILABLE,
        message,
        details=details or {},
        recoverable=True,
        recommended_action="retry_or_check_service",
    )


def load_vision_image(
    db: Any,
    asset_id: str,
    *,
    project_id: str | None = None,
    max_dim: int = DEFAULT_VISION_MAX_DIM,
    source: str = "attachment",
) -> LoadedVisionImage:
    """Load an in-project image, convert to RGB JPEG, preserve aspect ratio."""
    from ..db import Asset

    asset = db.get(Asset, asset_id)
    if not asset:
        raise VisionLoadError("the attached picture is missing.", asset_id)
    if project_id and asset.project_id != project_id:
        raise VisionLoadError("the attached picture is not part of this project.", asset_id)
    if not (asset.kind or "").startswith("image"):
        raise VisionLoadError("that attachment is not an image.", asset_id)
    if not asset.path:
        raise VisionLoadError("the picture file is missing.", asset_id)
    path = Path(asset.path)
    if not path.is_file():
        raise VisionLoadError("the picture file could not be found.", asset_id)
    try:
        from PIL import Image

        with Image.open(path) as img:
            img = img.convert("RGB")
            width, height = img.size
            limit = max(256, int(max_dim or DEFAULT_VISION_MAX_DIM))
            if width > limit or height > limit:
                ratio = min(limit / width, limit / height)
                img = img.resize(
                    (max(1, int(width * ratio)), max(1, int(height * ratio))),
                    Image.Resampling.LANCZOS,
                )
            out_w, out_h = img.size
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            data = buf.getvalue()
    except VisionLoadError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise VisionLoadError("the picture could not be read.", asset_id) from exc
    if not data:
        raise VisionLoadError("the picture was empty after processing.", asset_id)
    return LoadedVisionImage(
        asset_id=str(asset_id),
        jpeg_bytes=data,
        width=int(out_w),
        height=int(out_h),
        mime="image/jpeg",
        source=source,
    )


def encode_ollama_images(images: list[LoadedVisionImage]) -> list[str]:
    return [base64.b64encode(item.jpeg_bytes).decode("ascii") for item in images if item.jpeg_bytes]


def images_from_last_user(messages: list[dict[str, Any]] | None) -> list[Any] | None:
    for message in reversed(messages or []):
        if str(message.get("role") or "") != "user":
            continue
        images = message.get("images")
        if isinstance(images, list) and images:
            return images
    return None


def attach_images_to_last_user(
    messages: list[dict[str, Any]],
    images: list[Any],
) -> list[dict[str, Any]]:
    if not messages or not images:
        return messages
    out = list(messages)
    for i in range(len(out) - 1, -1, -1):
        if str(out[i].get("role") or "") == "user":
            out[i] = {**out[i], "images": images}
            return out
    return out


def copy_images_onto_last_user(
    dest_messages: list[dict[str, Any]],
    source_messages: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    images = images_from_last_user(source_messages) or images_from_last_user(dest_messages)
    if not images:
        return list(dest_messages)
    return attach_images_to_last_user(list(dest_messages), images)


def build_vision_trace(
    images: list[LoadedVisionImage],
    *,
    model_id: str | None = None,
    encoded: list[str] | None = None,
) -> dict[str, Any]:
    encoded = encoded if encoded is not None else encode_ollama_images(images)
    return {
        "assetIds": [item.asset_id for item in images],
        "sources": [item.source for item in images],
        "mimeType": "image/jpeg",
        "imageCount": len(encoded),
        "dimensions": [{"width": item.width, "height": item.height} for item in images],
        "firstImageLength": len(encoded[0]) if encoded else 0,
        "modelId": model_id,
        "hasImages": bool(encoded),
    }


def ollama_images_to_openai_content(content: str, images: list[Any]) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = [{"type": "text", "text": content or ""}]
    for raw in images:
        if not raw:
            continue
        value = str(raw)
        url = value if value.startswith("data:") else f"data:image/jpeg;base64,{value}"
        parts.append({"type": "image_url", "image_url": {"url": url}})
    return parts
