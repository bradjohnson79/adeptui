"""Image Output Gate — atomic validation before asset registration (M42 W2)."""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class ImageOutputGateResult:
    ok: bool
    path: str | None = None
    width: int | None = None
    height: int | None = None
    format: str | None = None
    bytes: int | None = None
    checksum: str | None = None
    previewPath: str | None = None
    thumbnailPath: str | None = None
    errors: list[str] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "path": self.path,
            "width": self.width,
            "height": self.height,
            "format": self.format,
            "bytes": self.bytes,
            "checksum": self.checksum,
            "previewPath": self.previewPath,
            "thumbnailPath": self.thumbnailPath,
            "errors": list(self.errors),
            "checks": dict(self.checks),
        }


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def _make_preview_and_thumb(src: Path, dest_dir: Path) -> tuple[str | None, str | None]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    preview = dest_dir / f"{src.stem}_preview{src.suffix or '.png'}"
    thumb = dest_dir / f"{src.stem}_thumb.jpg"
    try:
        from PIL import Image

        with Image.open(src) as im:
            im = im.convert("RGB") if im.mode not in ("RGB", "RGBA") else im
            prev = im.copy()
            prev.thumbnail((1280, 1280))
            prev.save(preview)
            th = im.copy()
            th.thumbnail((256, 256))
            th.convert("RGB").save(thumb, quality=85)
        return str(preview), str(thumb)
    except Exception:
        # Fall back to copy as preview
        try:
            shutil.copy2(src, preview)
            return str(preview), None
        except Exception:
            return None, None


def validate_image_output(
    path: str | Path,
    *,
    expected_aspect: Optional[str] = None,
    min_width: int = 64,
    min_height: int = 64,
    generate_previews: bool = True,
    preview_dir: str | Path | None = None,
) -> ImageOutputGateResult:
    """
    Temporary output inspection → validation PASS → thumbs/checksum.
    Caller must register asset only after ok=True.
    """
    p = Path(path)
    errors: list[str] = []
    checks: dict[str, bool] = {
        "exists": p.is_file(),
        "nonzero": False,
        "decodable": False,
        "minDimensions": False,
        "aspect": True,
        "checksum": False,
        "preview": False,
    }
    if not checks["exists"]:
        errors.append("Output file does not exist.")
        return ImageOutputGateResult(ok=False, path=str(p), errors=errors, checks=checks)

    size = p.stat().st_size
    checks["nonzero"] = size > 0
    if not checks["nonzero"]:
        errors.append("Output file is empty.")

    width = height = None
    fmt = p.suffix.lstrip(".").lower() or None
    try:
        from PIL import Image

        with Image.open(p) as im:
            im.verify()
        with Image.open(p) as im2:
            width, height = im2.size
            fmt = (im2.format or fmt or "").lower() or fmt
        checks["decodable"] = True
    except Exception as exc:
        errors.append(f"Image decode failed: {exc}")
        checks["decodable"] = False

    if width is not None and height is not None:
        checks["minDimensions"] = width >= min_width and height >= min_height
        if not checks["minDimensions"]:
            errors.append(f"Dimensions {width}x{height} below minimum {min_width}x{min_height}.")
        if expected_aspect and ":" in expected_aspect:
            try:
                aw, ah = expected_aspect.split(":", 1)
                target = float(aw) / float(ah)
                actual = width / max(height, 1)
                checks["aspect"] = abs(actual - target) < 0.08
                if not checks["aspect"]:
                    errors.append(
                        f"Aspect ratio mismatch: expected {expected_aspect}, got {width}x{height}."
                    )
            except Exception:
                pass

    checksum = None
    try:
        checksum = _sha256_file(p)
        checks["checksum"] = True
    except Exception as exc:
        errors.append(f"Checksum failed: {exc}")
        checks["checksum"] = False

    preview_path = thumb_path = None
    if generate_previews and checks["decodable"]:
        pdir = Path(preview_dir) if preview_dir else p.parent / ".gate"
        preview_path, thumb_path = _make_preview_and_thumb(p, pdir)
        checks["preview"] = bool(preview_path)
    else:
        checks["preview"] = not generate_previews

    ok = all(
        checks.get(k, False)
        for k in ("exists", "nonzero", "decodable", "minDimensions", "checksum")
    ) and checks.get("aspect", True)

    return ImageOutputGateResult(
        ok=ok,
        path=str(p),
        width=width,
        height=height,
        format=fmt,
        bytes=size,
        checksum=checksum,
        previewPath=preview_path,
        thumbnailPath=thumb_path,
        errors=errors,
        checks=checks,
    )


def _file_checksum(path: Path) -> str | None:
    try:
        return _sha256_file(path)
    except Exception:
        return None


def _images_identical(path_a: Path, path_b: Path) -> bool:
    if not path_a.is_file() or not path_b.is_file():
        return False
    ca, cb = _file_checksum(path_a), _file_checksum(path_b)
    if ca and cb:
        return ca == cb
    try:
        return path_a.read_bytes() == path_b.read_bytes()
    except Exception:
        return False


def _load_rgba(path: Path):
    from PIL import Image

    with Image.open(path) as im:
        return im.convert("RGBA")


def composite_generated_into_source(
    generated: str | Path,
    source: str | Path,
    mask: str | Path,
    dest: str | Path | None = None,
    *,
    feather_px: int = 8,
) -> Path:
    """Keep source pixels outside the mask; use generated pixels inside it.

    FLUX img2img restyles the whole frame. Region-edit still requires identity,
    camera, and unmasked scene to survive. This composite is applied after
    download and does not change certified Comfy graph fingerprints.
    White/opaque mask pixels select the generated image.
    """
    from PIL import Image, ImageFilter

    gen_path = Path(generated)
    src_path = Path(source)
    mask_path = Path(mask)
    out_path = Path(dest) if dest else gen_path
    with Image.open(gen_path) as gen_im:
        gen_rgba = gen_im.convert("RGBA")
    with Image.open(src_path) as src_im:
        src_rgba = src_im.convert("RGBA")
    with Image.open(mask_path) as mask_im:
        mask_l = mask_im.convert("L")
    if gen_rgba.size != src_rgba.size:
        gen_rgba = gen_rgba.resize(src_rgba.size, Image.Resampling.LANCZOS)
    if mask_l.size != src_rgba.size:
        mask_l = mask_l.resize(src_rgba.size, Image.Resampling.LANCZOS)
    if feather_px > 0:
        mask_l = mask_l.filter(ImageFilter.GaussianBlur(radius=float(feather_px)))
    composed = Image.composite(gen_rgba, src_rgba, mask_l)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    composed.convert("RGB").save(out_path)
    return out_path


def _mask_region_mean_delta(output: Path, source: Path, mask: Path, *, threshold: float = 2.0) -> bool:
    """True when masked pixels differ meaningfully from source (R5 inpaint check)."""
    try:
        out_im = _load_rgba(output)
        src_im = _load_rgba(source)
        mask_im = _load_rgba(mask)
        if out_im.size != src_im.size:
            out_im = out_im.resize(src_im.size)
        if mask_im.size != src_im.size:
            mask_im = mask_im.resize(src_im.size)
        mask_l = mask_im.split()[-1]
        pixels = 0
        total_delta = 0.0
        out_px = out_im.load()
        src_px = src_im.load()
        mask_px = mask_l.load()
        for y in range(src_im.size[1]):
            for x in range(src_im.size[0]):
                if mask_px[x, y] < 128:
                    continue
                pixels += 1
                or_, og, ob, _ = out_px[x, y]
                sr, sg, sb, _ = src_px[x, y]
                total_delta += abs(or_ - sr) + abs(og - sg) + abs(ob - sb)
        if pixels == 0:
            return False
        mean_delta = total_delta / (pixels * 3)
        return mean_delta >= threshold
    except Exception:
        return False


def _resolution_increased(output: Path, source: Path) -> bool:
    try:
        from PIL import Image

        with Image.open(output) as out_im, Image.open(source) as src_im:
            ow, oh = out_im.size
            sw, sh = src_im.size
            return ow > sw or oh > sh
    except Exception:
        return False


def _has_transparency(path: Path) -> bool:
    try:
        im = _load_rgba(path)
        alpha = im.split()[-1]
        extrema = alpha.getextrema()
        return bool(extrema and extrema[0] < 255)
    except Exception:
        return False


def validate_edit_output(
    path: str | Path,
    *,
    operation: str,
    source_path: str | Path | None = None,
    mask_path: str | Path | None = None,
    expected_width: int | None = None,
    expected_height: int | None = None,
    require_transparency: bool = False,
    generate_previews: bool = True,
    preview_dir: str | Path | None = None,
) -> ImageOutputGateResult:
    """
    Edit-specific output gate (R5): structural validate_image_output then semantic checks.
    Semantic failure sets ok=False even when base file integrity passes.
    """
    base = validate_image_output(
        path,
        generate_previews=generate_previews,
        preview_dir=preview_dir,
    )
    checks = dict(base.checks)
    errors = list(base.errors)
    op = (operation or "").strip().lower()

    src = Path(source_path) if source_path else None
    mask = Path(mask_path) if mask_path else None

    if src and src.is_file():
        identical = _images_identical(Path(path), src)
        checks["notIdenticalToSource"] = not identical
        if identical:
            errors.append("Edit output is identical to source — no effective change detected.")

    if op in {"image.inpaint", "inpaint", "object_remove", "object_replace"}:
        if src and mask and src.is_file() and mask.is_file():
            changed = _mask_region_mean_delta(Path(path), src, mask)
            checks["maskRegionChanged"] = changed
            if not changed:
                errors.append("Inpaint output: masked region did not change meaningfully.")
        else:
            checks["maskRegionChanged"] = False
            if op.startswith("image.inpaint") or op in {"inpaint", "object_remove", "object_replace"}:
                errors.append("Inpaint validation requires source_path and mask_path.")

    if op in {"image.outpaint", "outpaint", "crop_extend"}:
        expanded = True
        if expected_width is not None and base.width is not None:
            expanded = expanded and base.width >= expected_width
        if expected_height is not None and base.height is not None:
            expanded = expanded and base.height >= expected_height
        if src and src.is_file() and base.width is not None and base.height is not None:
            try:
                from PIL import Image

                with Image.open(src) as sim:
                    sw, sh = sim.size
                expanded = expanded and (base.width > sw or base.height > sh)
            except Exception:
                pass
        checks["canvasExpanded"] = expanded
        if not expanded:
            errors.append("Outpaint output: canvas was not expanded to expected dimensions.")

    if op in {"image.upscale", "upscale"}:
        if src and src.is_file():
            increased = _resolution_increased(Path(path), src)
            checks["resolutionIncreased"] = increased
            if not increased:
                errors.append("Upscale output: resolution did not increase vs source.")
        else:
            checks["resolutionIncreased"] = False
            errors.append("Upscale validation requires source_path.")

    if require_transparency or op in {"image.background_remove", "image.transparent_extract"}:
        has_alpha = _has_transparency(Path(path))
        checks["hasTransparency"] = has_alpha
        if not has_alpha:
            errors.append("Edit output lacks required alpha transparency.")

    semantic_keys = [
        k
        for k in checks
        if k
        not in {
            "exists",
            "nonzero",
            "decodable",
            "minDimensions",
            "aspect",
            "checksum",
            "preview",
        }
    ]
    semantic_ok = all(checks.get(k, True) for k in semantic_keys)
    ok = base.ok and semantic_ok

    return ImageOutputGateResult(
        ok=ok,
        path=base.path,
        width=base.width,
        height=base.height,
        format=base.format,
        bytes=base.bytes,
        checksum=base.checksum,
        previewPath=base.previewPath,
        thumbnailPath=base.thumbnailPath,
        errors=errors,
        checks=checks,
    )
