"""Stage Library assets into Comfy input from durable identity.

A production job must not treat a previous Comfy upload filename as the
source of truth. Adept owns the Library asset (assetId + filesystem path).
The runtime adapter copies that file into Comfy input and returns a
staging name for this execution only.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config import settings

SAFE_SUFFIXES = {
    ".wav",
    ".mp3",
    ".flac",
    ".ogg",
    ".m4a",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".mp4",
    ".webm",
    ".mov",
}


class ComfyAssetMissing(ValueError):
    """Library source file is missing or empty."""


class ComfyAssetStagingFailed(RuntimeError):
    """Could not place a verified copy into Comfy input."""


@dataclass(frozen=True)
class StagedComfyAsset:
    asset_id: str
    comfy_name: str
    source_path: str
    staged_path: str
    bytes: int
    reused: bool
    ledger: dict[str, Any] = field(default_factory=dict)


def _suffix(source: Path) -> str:
    ext = source.suffix.lower()
    return ext if ext in SAFE_SUFFIXES else ".bin"


def staged_comfy_name(asset_id: str, source: Path, *, subfolder: str = "studio") -> str:
    ident = str(asset_id or "").strip()
    if not ident:
        raise ComfyAssetMissing("Library asset is missing an id.")
    folder = str(subfolder or "studio").strip().strip("/\\") or "studio"
    return f"{folder}/{ident}{_suffix(source)}"


def resolve_library_source(asset: Any) -> Path:
    asset_id = str(getattr(asset, "id", "") or "").strip()
    raw = str(getattr(asset, "path", "") or "").strip()
    if not raw:
        raise ComfyAssetMissing(f"Library asset {asset_id or 'unknown'} has no file path.")
    path = Path(raw)
    if not path.is_file() or path.stat().st_size <= 0:
        raise ComfyAssetMissing(
            f"Library asset {asset_id or path.name} is missing from disk."
        )
    return path


def staged_abs_path(comfy_name: str, *, input_dir: Path | None = None) -> Path:
    root = Path(input_dir or settings.comfy_input_dir)
    return root / str(comfy_name).replace("/", os.sep)


def stage_library_asset(
    asset: Any,
    *,
    input_dir: Path | None = None,
    subfolder: str = "studio",
) -> StagedComfyAsset:
    """Copy the Library file into Comfy input. Verify it exists before return."""
    source = resolve_library_source(asset)
    asset_id = str(getattr(asset, "id", "") or "").strip()
    name = staged_comfy_name(asset_id, source, subfolder=subfolder)
    dest = staged_abs_path(name, input_dir=input_dir)
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Reuse staged bytes only when size+mtime match (invalidate on ref file change).
    reused = False
    if dest.is_file():
        ds, ss = dest.stat(), source.stat()
        reused = ds.st_size == ss.st_size and int(ds.st_mtime_ns) == int(ss.st_mtime_ns)
    if not reused:
        shutil.copy2(source, dest)
    if not dest.is_file() or dest.stat().st_size <= 0:
        raise ComfyAssetStagingFailed(
            f"Could not stage Library asset {asset_id} into the MiniMax input folder."
        )
    return StagedComfyAsset(
        asset_id=asset_id,
        comfy_name=name.replace("\\", "/"),
        source_path=str(source),
        staged_path=str(dest),
        bytes=dest.stat().st_size,
        reused=reused,
        ledger={"identityAuthority": "reference_image", "uploaded": "library_file"},
    )


def staged_h3_identity_name(asset_id: str, *, subfolder: str = "studio") -> str:
    ident = str(asset_id or "").strip()
    if not ident:
        raise ComfyAssetMissing("Library asset is missing an id.")
    folder = str(subfolder or "studio").strip().strip("/\\") or "studio"
    return f"{folder}/{ident}_h3id.png"


def stage_h3_visual_asset(
    asset: Any,
    *,
    role: str = "",
    input_dir: Path | None = None,
    subfolder: str = "studio",
    cache_dir: Path | None = None,
    derive_identity_still: bool = False,
) -> StagedComfyAsset:
    """Stage a Timeline visual slot for MiniMax H3 LoadImage.

    Creator Specification Fidelity (2026-09-09): character CRS sheets are
    plain-copied (same bytes as non-character refs). No silent crop / RGB /
    LANCZOS-to-1024h / PNG re-encode into *_h3id.png.

    Opt-in derive_identity_still=True restores the legacy resolve_h3_character_source
    crop path for experiments only — Timeline H3 default is plain copy.
    cache_dir is retained for API compatibility with the opt-in path.
    """
    role_n = str(role or "").strip().lower()
    if role_n != "character" or not derive_identity_still:
        staged = stage_library_asset(asset, input_dir=input_dir, subfolder=subfolder)
        if role_n == "character":
            ledger = dict(staged.ledger or {})
            ledger["identityAuthority"] = "reference_image"
            ledger["uploaded"] = "library_file"
            ledger["plainCopy"] = True
            ledger["h3IdentityStill"] = "bypassed"
            return StagedComfyAsset(
                asset_id=staged.asset_id,
                comfy_name=staged.comfy_name,
                source_path=staged.source_path,
                staged_path=staged.staged_path,
                bytes=staged.bytes,
                reused=staged.reused,
                ledger=ledger,
            )
        return staged

    from ..character_identity.h3_identity_still import resolve_h3_character_source

    source, ledger = resolve_h3_character_source(asset, cache_dir=cache_dir)
    asset_id = str(getattr(asset, "id", "") or "").strip()
    if ledger.get("uploaded") == "derived_identity_still":
        name = staged_h3_identity_name(asset_id, subfolder=subfolder)
    else:
        name = staged_comfy_name(asset_id, source, subfolder=subfolder)
    dest = staged_abs_path(name, input_dir=input_dir)
    dest.parent.mkdir(parents=True, exist_ok=True)
    reused = dest.is_file() and dest.stat().st_size == source.stat().st_size
    if not reused:
        shutil.copy2(source, dest)
    if not dest.is_file() or dest.stat().st_size <= 0:
        raise ComfyAssetStagingFailed(
            f"Could not stage Library asset {asset_id} into the MiniMax input folder."
        )
    return StagedComfyAsset(
        asset_id=asset_id,
        comfy_name=name.replace("\\", "/"),
        source_path=str(source),
        staged_path=str(dest),
        bytes=dest.stat().st_size,
        reused=reused,
        ledger=ledger,
    )
