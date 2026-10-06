"""Project-scoped asset file/thumb serving — one helper for file + thumb.

Canonical browser routes:
  GET /api/projects/{project_id}/assets/{asset_id}/file
  GET /api/projects/{project_id}/assets/{asset_id}/thumb

Unscoped GET /api/assets/{id}/file and /thumb are retired (403).
"""

from __future__ import annotations

import io
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from ..config import settings
from ..db import Asset, Project
from .permissions import (
    file_path_is_ambiguous,
    path_has_dotdot,
    project_id_from_file_path,
    resolve_data_file_path,
)

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
# Legacy continuity / library rows use 32-hex ids without dashes.
_HEX32_RE = re.compile(r"^[0-9a-fA-F]{32}$")


def canonical_project_asset_file_url(project_id: str | None, asset_id: str | None) -> str:
    pid = str(project_id or "").strip()
    aid = str(asset_id or "").strip()
    if not pid or not aid:
        return ""
    return f"/api/projects/{pid}/assets/{aid}/file"


def canonical_project_asset_thumb_url(project_id: str | None, asset_id: str | None) -> str:
    pid = str(project_id or "").strip()
    aid = str(asset_id or "").strip()
    if not pid or not aid:
        return ""
    return f"/api/projects/{pid}/assets/{aid}/thumb"


def is_canonical_project_asset_file_url(url: str | None) -> bool:
    raw = str(url or "").strip().split("?")[0]
    parts = raw.split("/")
    # /api/projects/{pid}/assets/{aid}/file
    return (
        len(parts) == 7
        and parts[1] == "api"
        and parts[2] == "projects"
        and bool(parts[3])
        and parts[4] == "assets"
        and bool(parts[5])
        and parts[6] == "file"
        and "/" not in parts[3]
        and "/" not in parts[5]
    )


def _require_ids(project_id: str, asset_id: str) -> tuple[str, str]:
    pid = str(project_id or "").strip()
    aid = str(asset_id or "").strip()
    if not pid or not aid or path_has_dotdot(pid) or path_has_dotdot(aid):
        raise HTTPException(
            status_code=400,
            detail={"error": "MALFORMED_ASSET_REQUEST", "projectId": pid, "assetId": aid},
        )
    if not _is_safe_asset_id(pid) or not _is_safe_asset_id(aid):
        raise HTTPException(
            status_code=400,
            detail={"error": "MALFORMED_ASSET_REQUEST", "projectId": pid, "assetId": aid},
        )
    return pid, aid


def _is_safe_asset_id(value: str) -> bool:
    return bool(_UUID_RE.match(value) or _HEX32_RE.match(value))


def _sniff_media(path: Path) -> str:
    """Classify bytes, not the library kind/extension. magi_color rows are H.264 named .png."""
    try:
        head = path.read_bytes()[:16]
    except OSError:
        return "unknown"
    if head.startswith(b"\x89PNG") or head.startswith(b"\xff\xd8\xff"):
        return "image"
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return "image"
    if head.startswith(b"RIFF") and head[8:12] == b"WAVE":
        return "audio"
    if head.startswith(b"ID3") or head.startswith(b"\xff\xfb") or head.startswith(b"\xff\xf3"):
        return "audio"
    if head.startswith(b"\x00\x00\x00\x01") or head[4:8] == b"ftyp" or b"ftyp" in head:
        return "video"
    suffix = path.suffix.lower()
    if suffix in {".mp4", ".mov", ".webm", ".mkv", ".avi"}:
        return "video"
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}:
        return "image"
    if suffix in {".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac"}:
        return "audio"
    return "unknown"


@lru_cache(maxsize=16)
def _placeholder_webp(width: int, style: str) -> bytes:
    from PIL import Image, ImageDraw

    w = max(16, int(width))
    h = max(16, int(round(w * 9 / 16)))
    img = Image.new("RGB", (w, h), (28, 30, 38))
    draw = ImageDraw.Draw(img)
    if style == "audio":
        mid = h // 2
        bar_w = max(2, w // 24)
        for i in range(8):
            x = 20 + i * (bar_w + 6)
            bh = 8 + (i % 4) * 6
            draw.rectangle([x, mid - bh, x + bar_w, mid + bh], fill=(120, 140, 170))
    else:
        inset = max(8, w // 10)
        draw.rounded_rectangle(
            [inset, inset, w - inset, h - inset],
            radius=8,
            outline=(70, 76, 90),
            width=2,
        )
    buf = io.BytesIO()
    img.save(buf, "WEBP", quality=70)
    return buf.getvalue()


def _thumb_response(path: Path, *, fallback: bool, reason: str = "") -> FileResponse:
    headers = {
        "Content-Type": "image/webp",
        "Cache-Control": "private, max-age=120" if fallback else "public, max-age=31536000, immutable",
        "X-Adept-Thumb": "fallback" if fallback else "generated",
    }
    if reason:
        headers["X-Adept-Thumb-Reason"] = reason[:80]
    return FileResponse(path, headers=headers)


def _placeholder_response(width: int, style: str, reason: str) -> Response:
    return Response(
        content=_placeholder_webp(width, style),
        media_type="image/webp",
        headers={
            "Cache-Control": "private, max-age=120",
            "X-Adept-Thumb": "fallback",
            "X-Adept-Thumb-Reason": reason[:80],
        },
    )


def _ffmpeg_poster(src: Path, dest: Path, width: int) -> bool:
    import subprocess

    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-ss",
            "0.4",
            "-i",
            str(src),
            "-frames:v",
            "1",
            "-vf",
            f"scale={width}:{width}:force_original_aspect_ratio=decrease",
            str(dest),
        ],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    return proc.returncode == 0 and dest.is_file()


def _pil_thumb(src: Path, dest: Path, width: int) -> bool:
    from PIL import Image

    with Image.open(src) as im:
        im = im.convert("RGBA") if im.mode in ("RGBA", "P") else im.convert("RGB")
        im.thumbnail((width, width))
        im.save(dest, "WEBP", quality=82, method=6)
    return dest.is_file()


def resolve_project_asset_path(db: Session, project_id: str, asset_id: str) -> tuple[Asset, Path]:
    """Load asset, enforce project match, resolve path inside data_dir."""
    pid, aid = _require_ids(project_id, asset_id)
    if db.get(Project, pid) is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "PROJECT_NOT_FOUND", "projectId": pid},
        )
    asset = db.get(Asset, aid)
    if not asset:
        raise HTTPException(
            status_code=404,
            detail={"error": "ASSET_NOT_FOUND", "assetId": aid},
        )
    if str(asset.project_id or "") != pid:
        from ..creator_scope.service import resolve_readable_asset

        readable = resolve_readable_asset(db, pid, aid)
        if readable is None:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "ASSET_PROJECT_MISMATCH",
                    "projectId": pid,
                    "assetId": aid,
                },
            )
    if not asset.path:
        raise HTTPException(
            status_code=404,
            detail={"error": "ASSET_FILE_MISSING", "assetId": aid, "reason": "path not set"},
        )
    if path_has_dotdot(asset.path):
        raise HTTPException(
            status_code=403,
            detail={"error": "FILE_API_RESTRICTED", "reason": "path traversal or escape"},
        )
    resolved = resolve_data_file_path(asset.path, settings.data_dir)
    if resolved is None:
        raise HTTPException(
            status_code=403,
            detail={"error": "FILE_API_RESTRICTED", "reason": "path traversal or escape"},
        )
    raw = str(resolved)
    if file_path_is_ambiguous(raw):
        raise HTTPException(
            status_code=403,
            detail={"error": "FILE_API_RESTRICTED", "reason": "ambiguous project scope"},
        )
    path_project = project_id_from_file_path(raw)
    owner_pid = str(asset.project_id or "")
    if path_project and path_project != owner_pid:
        raise HTTPException(
            status_code=403,
            detail={"error": "ASSET_PROJECT_MISMATCH", "projectId": pid, "pathProjectId": path_project},
        )
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(
            status_code=404,
            detail={"error": "ASSET_FILE_MISSING", "assetId": aid, "path": str(resolved)},
        )
    return asset, resolved


def _sniff_image_mime(path: Path) -> str | None:
    try:
        head = path.read_bytes()[:16]
    except OSError:
        return None
    if head.startswith(b"\x89PNG"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return "image/webp"
    if head.startswith(b"GIF8"):
        return "image/gif"
    if head.startswith(b"BM"):
        return "image/bmp"
    return None


def serve_project_asset_file(db: Session, project_id: str, asset_id: str) -> FileResponse:
    _asset, resolved = resolve_project_asset_path(db, project_id, asset_id)
    mime = _sniff_image_mime(resolved)
    if mime:
        return FileResponse(resolved, media_type=mime)
    return FileResponse(resolved)


def serve_project_asset_thumb(db: Session, project_id: str, asset_id: str, w: int = 256) -> Any:
    asset, src = resolve_project_asset_path(db, project_id, asset_id)
    kind = str(asset.kind or "").strip().lower()
    width = int(w or 256)
    if width < 16 or width > 2048:
        raise HTTPException(
            status_code=400,
            detail={"error": "MALFORMED_ASSET_REQUEST", "reason": "invalid thumb width"},
        )
    sniffed = _sniff_media(src)
    if kind in {"audio", "music", "sfx"} or sniffed == "audio":
        return _placeholder_response(width, "audio", "audio_card")

    thumb_dir = src.parent / ".thumbs"
    try:
        thumb_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return _placeholder_response(width, "media", "thumb_dir_unavailable")
    thumb_path = thumb_dir / f"{src.stem}_{width}.webp"
    if thumb_path.is_file():
        return _thumb_response(thumb_path, fallback=False)

    treat_as_video = sniffed == "video" or kind == "video"
    try:
        if treat_as_video:
            if _ffmpeg_poster(src, thumb_path, width):
                return _thumb_response(thumb_path, fallback=False)
        else:
            if _pil_thumb(src, thumb_path, width):
                return _thumb_response(thumb_path, fallback=False)
            if sniffed == "unknown" and _ffmpeg_poster(src, thumb_path, width):
                return _thumb_response(thumb_path, fallback=False)
    except Exception:
        pass
    return _placeholder_response(width, "media", "thumbnail_unavailable")


def unscoped_asset_route_forbidden(kind: str = "file") -> None:
    raise HTTPException(
        status_code=403,
        detail={
            "error": "ASSET_SCOPE_REQUIRED",
            "reason": f"Use GET /api/projects/{{projectId}}/assets/{{assetId}}/{kind}",
        },
    )
