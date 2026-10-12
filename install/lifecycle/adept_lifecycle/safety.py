"""Path containment for uninstall and model removal."""

from __future__ import annotations

from pathlib import Path

SHARED_PARTS = {
    "comfyui",
    "comfy",
    "ffmpeg",
    "python",
    "python3",
    "system32",
    "syswow64",
    "windows",
    "drivers",
    "library",
}


def resolve_contained(path: Path, root: Path) -> Path | None:
    """Return the resolved path when it stays inside root.

    Symlinks and junctions are refused so deletion cannot escape the root.
    """
    if path.is_symlink():
        return None
    try:
        resolved = path.resolve(strict=False)
        root_resolved = root.resolve(strict=False)
        resolved.relative_to(root_resolved)
    except (OSError, ValueError):
        return None
    if resolved == root_resolved:
        return None
    return resolved


def is_shared_dependency(path: Path) -> bool:
    parts = {part.lower() for part in path.parts}
    return bool(parts & SHARED_PARTS)


def windows_model_on_system_drive(path: Path, system_drive: str) -> bool:
    """Refuse a Windows path whose drive is not the designated system drive.

    POSIX paths have no drive letter. They are judged by directory containment
    instead, so a simulated Windows profile on Linux does not skip them here.
    """
    if not path.drive:
        return True
    drive = system_drive.rstrip("\\/").upper()
    if len(drive) == 1:
        drive = drive + ":"
    return path.drive.upper() == drive.upper()
