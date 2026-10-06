"""UI/cert contact sheet and owner review strip. Never geometry evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


def _tile(path: Path | None, label: str, height: int = 280) -> tuple[str, Image.Image]:
    if path and path.is_file():
        img = Image.open(path).convert("RGB")
    else:
        img = Image.new("RGB", (360, height), (28, 32, 40))
    scale = height / max(img.height, 1)
    return label, img.resize((max(int(img.width * scale), 1), height))


def write_strip(
    tiles: list[tuple[str, Path | None]],
    output_path: Path,
    *,
    caption: str = "",
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    prepared = [_tile(path, label) for label, path in tiles]
    gap = 14
    height = 280
    width = sum(img.width for _, img in prepared) + gap * (len(prepared) + 1)
    extra = 48 if caption else 28
    strip = Image.new("RGB", (width, height + extra), (16, 18, 22))
    draw = ImageDraw.Draw(strip)
    x = gap
    for label, img in prepared:
        strip.paste(img, (x, 26))
        draw.text((x, 6), label, fill=(230, 230, 230))
        x += img.width + gap
    if caption:
        draw.text((gap, height + 28), caption[:160], fill=(180, 184, 190))
    strip.save(output_path)
    return output_path


def write_contact_sheet(
    *,
    master: Path,
    view_a: Path | None,
    view_b: Path | None,
    output_path: Path,
) -> dict[str, Any]:
    path = write_strip(
        [("Master", master), ("View A", view_a), ("View B", view_b)],
        output_path,
    )
    return {"path": str(path), "notGeometryEvidence": True}


def write_owner_review_strip(
    *,
    master: Path,
    view_a: Path | None,
    view_b: Path | None,
    atlas: Path | None,
    output_path: Path,
    reasoning: str = "",
) -> dict[str, Any]:
    path = write_strip(
        [
            ("Observed Master", master),
            ("Qwen View A", view_a),
            ("Qwen View B", view_b),
            ("MoGe Atlas", atlas),
            ("Reasoning Summary", None),
        ],
        output_path,
        caption=reasoning
        or "Do these two additional views help understand this environment without contradicting the source?",
    )
    return {"path": str(path), "notGeometryEvidence": True}
