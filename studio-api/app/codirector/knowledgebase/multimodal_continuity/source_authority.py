"""Pixel vs Visual Canon lineage. Mismatch blocks prompt compilation."""

from __future__ import annotations

from typing import Any

from .schema import ContinuityCompileError, SourceAuthority


def resolve_source_authority(
    *,
    original_asset_id: str = "",
    atlas_asset_id: str = "",
    lineage_fingerprint: str = "",
) -> SourceAuthority:
    original = str(original_asset_id or "").strip()
    atlas = str(atlas_asset_id or "").strip()
    asset_id = original or atlas
    kind = "original_environment" if original else "atlas"
    return SourceAuthority(
        assetId=asset_id,
        type=kind,
        lineageFingerprint=str(lineage_fingerprint or "").strip(),
        isPixelAuthority=bool(asset_id),
    )


def pixel_authority_asset_id(*, original_asset_id: str = "", atlas_asset_id: str = "") -> str:
    return str(original_asset_id or "").strip() or str(atlas_asset_id or "").strip()


def assert_canon_matches_pixels(
    *,
    source: SourceAuthority,
    canon: Any | None,
) -> None:
    """Block when Visual Canon describes a different image than I2I will consume.

    Unavailable / missing canon is not a mismatch — compile proceeds from
    Scene Intent + Spatial Map without pretending vision ran.
    """
    if canon is None:
        return
    availability = str(getattr(canon, "availability", "") or "")
    if isinstance(canon, dict):
        availability = str(canon.get("availability") or "")
    if availability != "available":
        return
    canon_id = ""
    canon_fp = ""
    if isinstance(canon, dict):
        canon_id = str(canon.get("sourceAssetId") or "").strip()
        canon_fp = str(canon.get("groundingFingerprint") or "").strip()
    else:
        canon_id = str(getattr(canon, "sourceAssetId", "") or "").strip()
        canon_fp = str(getattr(canon, "groundingFingerprint", "") or "").strip()
    pixel_id = str(source.assetId or "").strip()
    if pixel_id and canon_id and canon_id != pixel_id:
        raise ContinuityCompileError(
            "The environment description does not match the source photo this "
            "sheet will use. Analyze the same image, or remove the mismatched "
            "description before generating.",
            field="sourceAuthority",
            conflicts=[f"pixel={pixel_id}", f"canon={canon_id}"],
        )
    src_fp = str(source.lineageFingerprint or "").strip()
    if src_fp and canon_fp and canon_fp != src_fp:
        raise ContinuityCompileError(
            "The environment description is out of date for this Spatial Map. "
            "Refresh the description from the current source photo before generating.",
            field="sourceAuthority.lineageFingerprint",
            conflicts=[f"map={src_fp}", f"canon={canon_fp}"],
        )
