"""Derive a MiniMax H3 identity still from an approved Character Reference Sheet.

The Library sheet remains identity authority. MiniMax <Picture n> wants one
person, not a labeled multi-panel bible. This crop is not a substitute
hero_identity and is not new canon.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image

from .crs_single_figure import detect_collage_layout

_SHEET_MARKERS = (
    "character_sheet",
    "character_reference_sheet",
    "crs",
    "composed_sheet",
    "composed",
)


def _asset_blob(asset: Any | None) -> str:
    if asset is None:
        return ""
    parts = [
        str(getattr(asset, "labels_json", "") or ""),
        str(getattr(asset, "tag", "") or ""),
        str(getattr(asset, "filename", "") or ""),
        str(getattr(asset, "prompt_meta_json", "") or ""),
    ]
    return " ".join(parts).lower()


def _has_sheet_labels(asset: Any | None) -> bool:
    blob = _asset_blob(asset)
    return any(marker in blob for marker in _SHEET_MARKERS)


def _prompt_meta(asset: Any | None) -> dict[str, Any]:
    raw = getattr(asset, "prompt_meta_json", None) or ""
    if isinstance(raw, dict):
        return raw
    try:
        data = json.loads(str(raw))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def classify_sheet_layout(path: str | Path, asset: Any | None = None) -> str:
    """Which multi-panel bible this file is. unknown = treat as a single still."""
    meta = _prompt_meta(asset)
    layout = str(meta.get("layout") or "").strip().lower()
    if layout.startswith("v3_21x9") or layout.startswith("v2_21x9"):
        return "adept_v3"
    if str(meta.get("composer") or "").lower() == "adept" and "character_sheet" in str(
        meta.get("objective") or meta.get("compositionIntent") or ""
    ):
        return "adept_v3"
    if detect_collage_layout(path):
        return "four_panel_2x2"
    size = _image_size(path)
    if size is None:
        return "unknown"
    w, h = size
    ratio = w / max(1, h)
    if w >= 2000 and 2.2 <= ratio <= 2.5:
        return "adept_v3"
    labeled = _has_sheet_labels(asset)
    columns = turnaround_column_count(path)
    if labeled and _is_near_square(size) and columns >= 2:
        return "four_panel_2x2"
    if columns >= 3 or (labeled and _is_landscape_sheet(size)):
        return "type_a"
    return "unknown"


def _image_size(path: str | Path) -> tuple[int, int] | None:
    pth = Path(path)
    if not pth.is_file():
        return None
    try:
        with Image.open(pth) as im:
            return int(im.size[0]), int(im.size[1])
    except Exception:
        return None


def _is_landscape_sheet(size: tuple[int, int]) -> bool:
    w, h = size
    return w >= 1200 and h >= 700 and (w / max(1, h)) >= 1.35


def _is_near_square(size: tuple[int, int]) -> bool:
    w, h = size
    if w < 512 or h < 512:
        return False
    return abs(w - h) <= max(8, int(0.03 * max(w, h)))


def _column_std(gray: Image.Image, y0: int, y1: int) -> list[float]:
    pix = gray.load()
    w, _h = gray.size
    step = max(1, (y1 - y0) // 36)
    out: list[float] = []
    for x in range(w):
        vals = [float(pix[x, y]) for y in range(y0, y1, step)]
        if not vals:
            out.append(0.0)
            continue
        mean = sum(vals) / len(vals)
        var = sum((v - mean) ** 2 for v in vals) / len(vals)
        out.append(var**0.5)
    return out


def _high_runs(stds: list[float], *, min_width: int, thresh: float) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    i = 0
    n = len(stds)
    while i < n:
        if stds[i] >= thresh:
            j = i
            while j < n and stds[j] >= thresh:
                j += 1
            if j - i >= min_width:
                runs.append((i, j))
            i = j
        else:
            i += 1
    return runs


def turnaround_column_count(path: str | Path) -> int:
    """Count figure-like columns in the left half of the upper content band."""
    pth = Path(path)
    if not pth.is_file():
        return 0
    try:
        with Image.open(pth) as im:
            gray = im.convert("L")
            w, h = gray.size
            if w < 64 or h < 64:
                return 0
            y0, y1 = int(h * 0.12), int(h * 0.58)
            if y1 - y0 < 32:
                return 0
            stds = _column_std(gray, y0, y1)
            left = stds[: max(1, w // 2)]
            if not left:
                return 0
            ordered = sorted(left)
            thresh = ordered[int(len(ordered) * 0.45)]
            thresh = max(thresh, 8.0)
            runs = _high_runs(left, min_width=max(24, w // 40), thresh=thresh)
            return len(runs)
    except Exception:
        return 0


def looks_like_reference_sheet(path: str | Path, asset: Any | None = None) -> bool:
    """True when the bound picture is a multi-panel sheet, not one person."""
    return classify_sheet_layout(path, asset) != "unknown"


def identity_still_cache_path(asset_id: str, *, cache_dir: Path | None = None) -> Path:
    if cache_dir is not None:
        folder = Path(cache_dir)
    else:
        from ..config import settings

        root = Path(getattr(settings, "data_dir", None) or Path("data"))
        folder = root / "cache" / "h3_identity_stills"
    folder.mkdir(parents=True, exist_ok=True)
    ident = str(asset_id or "unknown").strip() or "unknown"
    return folder / f"{ident}_h3id.png"


def _crop_box(im: Image.Image, box: tuple[int, int, int, int]) -> Image.Image | None:
    x0, y0, x1, y1 = box
    w, h = im.size
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(w, x1), min(h, y1)
    if x1 - x0 < 32 or y1 - y0 < 32:
        return None
    crop = im.crop((x0, y0, x1, y1))
    extrema = crop.convert("L").getextrema()
    if extrema and extrema[1] - extrema[0] < 12:
        return None
    return crop


def _trim_flat_borders(im: Image.Image, *, thresh: int = 18) -> Image.Image:
    """Tight crop around the figure. Adept V3 tiles are wide gray cells."""
    gray = im.convert("L")
    w, h = gray.size
    if w < 48 or h < 48:
        return im
    pix = gray.load()
    bg = (pix[2, 2] + pix[w - 3, 2] + pix[2, h - 3] + pix[w - 3, h - 3]) / 4.0
    x_step = max(1, w // 48)
    y_step = max(1, h // 48)

    def _row_active(y: int) -> bool:
        return any(abs(pix[x, y] - bg) > thresh for x in range(0, w, x_step))

    def _col_active(x: int) -> bool:
        return any(abs(pix[x, y] - bg) > thresh for y in range(0, h, y_step))

    y0 = next((y for y in range(h) if _row_active(y)), 0)
    y1 = next((y for y in range(h - 1, -1, -1) if _row_active(y)), h - 1) + 1
    x0 = next((x for x in range(w) if _col_active(x)), 0)
    x1 = next((x for x in range(w - 1, -1, -1) if _col_active(x)), w - 1) + 1
    pad = max(6, int(min(w, h) * 0.02))
    box = (max(0, x0 - pad), max(0, y0 - pad), min(w, x1 + pad), min(h, y1 + pad))
    if box[2] - box[0] < 64 or box[3] - box[1] < 64:
        return im
    return im.crop(box)


def _drop_top_label(crop: Image.Image) -> Image.Image:
    """Remove a uniform FRONT/section bar. Do not cut a face that starts at the top."""
    cut = int(crop.height * 0.10)
    if crop.height - cut < 64:
        return crop
    top = crop.crop((0, 0, crop.width, max(8, cut)))
    extrema = top.convert("L").getextrema()
    if extrema and (extrema[1] - extrema[0]) < 36:
        return crop.crop((0, cut, crop.width, crop.height))
    return crop


def _merge_runs(runs: list[tuple[int, int]], *, gap: int) -> list[tuple[int, int]]:
    if not runs:
        return []
    merged = [[runs[0][0], runs[0][1]]]
    for start, end in runs[1:]:
        if start - merged[-1][1] <= gap:
            merged[-1][1] = end
        else:
            merged.append([start, end])
    return [(int(start), int(end)) for start, end in merged]


def _type_a_front_crop(im: Image.Image) -> Image.Image | None:
    """First turnaround figure on a GPT Image 2 / Type A landscape sheet.

    Four standing views occupy the left ~42%. The first column is Front.
    Edge-energy peaks alone are too skinny (hair, tattoo, panel rules),
    so the band fractions are the authority and gutters only widen them.
    """
    w, h = im.size
    y0, y1 = int(h * 0.165), int(h * 0.595)
    x0, x1 = int(w * 0.015), int(w * 0.128)
    x_limit = max(64, int(w * 0.22))
    gray = im.convert("L")
    stds = _column_std(gray, int(h * 0.14), y1)[:x_limit]
    if stds:
        ordered = sorted(stds)
        thresh = max(ordered[int(len(ordered) * 0.40)], 8.0)
        runs = _merge_runs(
            _high_runs(stds, min_width=max(20, w // 64), thresh=thresh),
            gap=max(12, w // 80),
        )
        wide = [(a, b) for a, b in runs if (b - a) >= max(90, int(w * 0.07))]
        if wide:
            a, b = wide[0]
            x0 = min(x0, max(0, a - 6))
            x1 = max(x1, min(x_limit, b + 6))
    crop = _crop_box(im, (x0, y0, x1, y1))
    if crop is None or crop.width < 90:
        return None
    return _drop_top_label(crop)


def _adept_v3_front_crop(im: Image.Image) -> Image.Image | None:
    """Front tile of the Adept Character Creator 21:9 sheet. Notes stay off-tensor."""
    from .character_sheet_compose import plan_v3_character_sheet

    w, h = im.size
    plan = plan_v3_character_sheet(w, h)
    front = next((cell for cell in plan["views"] if cell["role"] == "full_body_front"), None)
    box = list((front or {}).get("identityBbox") or (front or {}).get("bbox") or [])
    if len(box) != 4:
        return None
    inset = max(4, int(min(w, h) * 0.008))
    crop = _crop_box(
        im,
        (box[0] + inset, box[1] + inset, box[2] - inset, box[3] - inset),
    )
    return crop


def _four_panel_front_crop(source: Path) -> Image.Image | None:
    from .crs_identity_views import extract_crs_identity_views

    try:
        views = extract_crs_identity_views(source)
    except Exception:
        return None
    preferred = ("full_body_front", "hero_identity", "full_body_three_quarter_front")
    by_role = {str(view.role): view for view in views}
    for role in preferred:
        view = by_role.get(role)
        if view is not None and view.image is not None:
            return view.image.convert("RGB")
    if views and views[0].image is not None:
        return views[0].image.convert("RGB")
    return None


def write_identity_still(
    source: Path,
    dest: Path,
    *,
    asset: Any | None = None,
) -> bool:
    """Crop one standing figure from a sheet. False = keep the sheet."""
    try:
        with Image.open(source) as raw:
            im = raw.convert("RGB")
    except Exception:
        return False
    w, h = im.size
    if w < 64 or h < 64:
        return False
    still: Image.Image | None = None
    kind = classify_sheet_layout(source, asset)
    if kind == "adept_v3":
        still = _adept_v3_front_crop(im)
    elif kind == "four_panel_2x2":
        still = _four_panel_front_crop(source)
    elif kind == "type_a":
        still = _type_a_front_crop(im)
    if still is None and kind != "unknown":
        still = _type_a_front_crop(im) or _adept_v3_front_crop(im)
    if still is None or still.width < 90 or still.height < 90:
        return False
    still = _trim_flat_borders(still)
    if still.width < 90 or still.height < 90:
        return False
    still = _upscale_identity(still)
    dest.parent.mkdir(parents=True, exist_ok=True)
    still.save(dest, format="PNG")
    return dest.is_file() and dest.stat().st_size > 0


def _upscale_identity(still: Image.Image) -> Image.Image:
    """Give MiniMax a usable tensor. The crop region itself stays the authority."""
    target_h = 1024
    if still.height >= target_h:
        return still
    width = max(1, int(still.width * (target_h / still.height)))
    return still.resize((width, target_h), Image.Resampling.LANCZOS)


def resolve_h3_character_source(
    asset: Any,
    *,
    cache_dir: Path | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Library sheet stays authority. Return the file MiniMax should load."""
    from ..video_runtime.comfy_asset_stage import resolve_library_source

    source = resolve_library_source(asset)
    asset_id = str(getattr(asset, "id", "") or "").strip()
    ledger: dict[str, Any] = {
        "identityAuthority": "reference_image",
        "libraryAssetId": asset_id,
        "uploaded": "library_file",
    }
    if not looks_like_reference_sheet(source, asset):
        return source, ledger
    ledger["sheetLayout"] = classify_sheet_layout(source, asset)
    dest = identity_still_cache_path(asset_id or source.stem, cache_dir=cache_dir)
    fresh = dest.is_file() and dest.stat().st_mtime >= source.stat().st_mtime and dest.stat().st_size > 0
    if fresh or write_identity_still(source, dest, asset=asset):
        if dest.is_file() and dest.stat().st_size > 0:
            ledger["uploaded"] = "derived_identity_still"
            ledger["derivedPath"] = str(dest)
            ledger["useComposedSheet"] = False
            return dest, ledger
    ledger["uploaded"] = "library_file"
    ledger["derivedFailed"] = True
    return source, ledger
