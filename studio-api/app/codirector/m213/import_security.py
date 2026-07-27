"""Secure 3D import validation (no path traversal / script payloads)."""
from __future__ import annotations

import os
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Soft limits for studio imports (honest, not Blender-class authoring)
MAX_BYTES = 250 * 1024 * 1024
MAX_TEXTURE_BYTES = 64 * 1024 * 1024
ALLOWED_EXT = {".glb", ".gltf", ".obj", ".fbx", ".ply", ".stl", ".zip"}
GLB_MAGIC = b"glTF"


@dataclass
class ImportValidation:
    ok: bool
    path: str
    ext: str
    size_bytes: int
    reasons: list[str]
    warnings: list[str]
    format_hint: str
    fixture: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "path": self.path,
            "ext": self.ext,
            "sizeBytes": self.size_bytes,
            "reasons": self.reasons,
            "warnings": self.warnings,
            "formatHint": self.format_hint,
            "fixture": self.fixture,
        }


def _safe_resolve(path: Path, root: Path | None = None) -> Path:
    resolved = path.resolve()
    if root is not None:
        root_r = root.resolve()
        try:
            resolved.relative_to(root_r)
        except ValueError as exc:
            raise ValueError("path traversal rejected") from exc
    text = str(resolved)
    if ".." in path.as_posix():
        # still reject raw .. segments even if resolved under root
        if ".." in Path(os.path.normpath(path)).parts:
            raise ValueError("path traversal rejected")
    if any(part.startswith(".") and part not in {".", ".."} for part in resolved.parts[-3:]):
        pass
    return resolved


def validate_import_file(path: str | Path, *, root: Path | None = None) -> ImportValidation:
    p = Path(path)
    reasons: list[str] = []
    warnings: list[str] = []
    try:
        resolved = _safe_resolve(p, root)
    except ValueError as exc:
        return ImportValidation(
            ok=False,
            path=str(p),
            ext="",
            size_bytes=0,
            reasons=[str(exc)],
            warnings=[],
            format_hint="unknown",
        )
    ext = resolved.suffix.lower()
    if ext not in ALLOWED_EXT:
        reasons.append(f"extension {ext or '(none)'} not allowed")
    if not resolved.is_file():
        reasons.append("file not found")
        return ImportValidation(False, str(resolved), ext, 0, reasons, warnings, "unknown")
    size = resolved.stat().st_size
    if size <= 0:
        reasons.append("empty file")
    if size > MAX_BYTES:
        reasons.append(f"file exceeds {MAX_BYTES} bytes")
    format_hint = ext.lstrip(".") or "unknown"
    head = resolved.read_bytes()[:64]
    if ext == ".glb":
        if not head.startswith(GLB_MAGIC):
            reasons.append("GLB magic missing")
        else:
            format_hint = "glb"
            if len(head) >= 12:
                version = struct.unpack_from("<I", head, 4)[0]
                if version not in (1, 2):
                    warnings.append(f"unusual glTF version {version}")
    if ext == ".gltf":
        text = resolved.read_text(encoding="utf-8", errors="replace")[:200_000]
        lowered = text.lower()
        if "<script" in lowered or "javascript:" in lowered:
            reasons.append("script payload rejected in gltf")
        format_hint = "gltf"
    if b"<script" in head.lower() or b"javascript:" in head.lower():
        reasons.append("script signature rejected")
    return ImportValidation(
        ok=not reasons,
        path=str(resolved),
        ext=ext,
        size_bytes=size,
        reasons=reasons,
        warnings=warnings,
        format_hint=format_hint,
    )
