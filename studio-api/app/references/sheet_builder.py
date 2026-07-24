"""Composite Ingredients reference-sheet builder."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Sequence

from PIL import Image

LAYOUTS = (
    "auto",
    "character_focus",
    "two_characters_environment",
    "character_props_environment",
    "environment_focus",
    "custom_grid",
)


@dataclass
class SheetPanel:
    path: Path
    role: str
    subject_name: str = ""
    priority: str = "primary"


def _open_rgb(path: Path) -> Image.Image:
    img = Image.open(path)
    img.load()
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (0, 0, 0))
        bg.paste(img, mask=img.split()[-1])
        return bg
    return img.convert("RGB")


def _fit(img: Image.Image, box_w: int, box_h: int) -> Image.Image:
    if box_w <= 0 or box_h <= 0:
        return img
    scale = min(box_w / img.width, box_h / img.height)
    nw = max(1, int(img.width * scale))
    nh = max(1, int(img.height * scale))
    resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (box_w, box_h), (0, 0, 0))
    canvas.paste(resized, ((box_w - nw) // 2, (box_h - nh) // 2))
    return canvas


def _slots_for(layout: str, panels: Sequence[SheetPanel]) -> list[tuple[float, float, float, float, SheetPanel]]:
    """Return normalized (x,y,w,h,panel) slots on [0,1]."""
    items = list(panels)
    if not items:
        return []

    chars = [p for p in items if p.role in ("character", "costume")]
    envs = [p for p in items if p.role in ("environment", "architecture", "lighting")]
    props = [p for p in items if p.role in ("prop", "vehicle", "other", "style")]
    if layout == "auto":
        if len(chars) >= 2 and envs:
            layout = "two_characters_environment"
        elif chars and (props or envs):
            layout = "character_props_environment"
        elif envs and not chars:
            layout = "environment_focus"
        else:
            layout = "character_focus"

    slots: list[tuple[float, float, float, float, SheetPanel]] = []
    if layout == "character_focus":
        primary = chars[:1] or items[:1]
        rest = [p for p in items if p not in primary]
        slots.append((0.0, 0.0, 0.62, 1.0, primary[0]))
        for i, p in enumerate(rest[:3]):
            slots.append((0.64, i / 3, 0.36, 1 / 3, p))
    elif layout == "two_characters_environment":
        env = (envs or items)[0]
        slots.append((0.0, 0.0, 1.0, 0.38, env))
        c1 = chars[0] if chars else items[0]
        c2 = chars[1] if len(chars) > 1 else (props[0] if props else items[-1])
        slots.append((0.0, 0.4, 0.5, 0.6, c1))
        slots.append((0.5, 0.4, 0.5, 0.6, c2))
    elif layout == "character_props_environment":
        env = (envs or items)[0]
        slots.append((0.0, 0.0, 1.0, 0.34, env))
        char = chars[0] if chars else items[0]
        slots.append((0.0, 0.36, 0.5, 0.64, char))
        side = props[:2] or [p for p in items if p is not char and p is not env][:2]
        if not side:
            side = [char]
        if len(side) == 1:
            slots.append((0.5, 0.36, 0.5, 0.64, side[0]))
        else:
            slots.append((0.5, 0.36, 0.5, 0.32, side[0]))
            slots.append((0.5, 0.68, 0.5, 0.32, side[1]))
    elif layout == "environment_focus":
        env = (envs or items)[0]
        slots.append((0.0, 0.0, 1.0, 0.7, env))
        rest = [p for p in items if p is not env][:2]
        for i, p in enumerate(rest):
            slots.append((i * 0.5, 0.72, 0.5, 0.28, p))
    else:  # custom_grid / fallback
        n = len(items)
        cols = 2 if n > 1 else 1
        rows = (n + cols - 1) // cols
        for i, p in enumerate(items):
            r, c = divmod(i, cols)
            slots.append((c / cols, r / rows, 1 / cols, 1 / rows, p))
    return slots


def build_reference_sheet(
    panels: Sequence[SheetPanel],
    *,
    layout: str = "auto",
    width: int = 768,
    height: int = 448,
    out_path: Path | None = None,
) -> dict[str, Any]:
    if not panels:
        raise ValueError("At least one reference panel is required")
    layout = layout if layout in LAYOUTS else "auto"
    canvas = Image.new("RGB", (width, height), (0, 0, 0))
    used: list[dict[str, Any]] = []
    for x, y, w, h, panel in _slots_for(layout, panels):
        img = _open_rgb(panel.path)
        cell = _fit(img, max(1, int(w * width)), max(1, int(h * height)))
        canvas.paste(cell, (int(x * width), int(y * height)))
        used.append(
            {
                "path": str(panel.path),
                "role": panel.role,
                "subject_name": panel.subject_name,
                "priority": panel.priority,
                "region": {"x": x, "y": y, "w": w, "h": h},
            }
        )
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(out_path, format="PNG")
        size = out_path.stat().st_size
        return {
            "path": str(out_path),
            "width": width,
            "height": height,
            "layout": layout,
            "panels": used,
            "bytes": size,
        }
    buf = BytesIO()
    canvas.save(buf, format="PNG")
    return {
        "path": None,
        "width": width,
        "height": height,
        "layout": layout,
        "panels": used,
        "bytes": len(buf.getvalue()),
        "png_bytes": buf.getvalue(),
    }
